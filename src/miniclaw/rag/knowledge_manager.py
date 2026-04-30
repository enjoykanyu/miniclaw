"""
MiniClaw Knowledge Manager — 离线知识库管理

功能:
  1. 离线文档导入: PDF/MD/TXT 批量导入
  2. 增量索引: 只处理新增/修改的文档
  3. 指纹检测: 文件变化时自动重建索引
  4. 持久化: FAISS索引 + BM25统计 + 元数据
  5. 知识库 CRUD: 创建/删除/列表/统计

使用方式:
  manager = KnowledgeManager()
  manager.create_knowledge_base("my_docs", "我的文档库")
  manager.import_directory("my_docs", "/path/to/documents")
  results = manager.search("my_docs", "查询内容")
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from pathlib import Path
import os
import json
import hashlib
import logging
from datetime import datetime

from miniclaw.config.settings import settings
from miniclaw.rag.types import Document, RetrievalResult
from miniclaw.rag.service import RAGService, KnowledgeBase, get_rag_service
from miniclaw.rag.document_loader import DocumentLoader, FileTypeRouter
from miniclaw.rag.chunking import (
    RecursiveChunker,
    MarkdownChunker,
    ThreeLevelChunker,
    ChunkingStrategy,
)
from miniclaw.rag.retriever import HybridRetriever, SearchMode, FusionMethod

logger = logging.getLogger(__name__)


@dataclass
class ImportResult:
    kb_name: str
    total_files: int
    processed_files: int
    skipped_files: int
    total_chunks: int
    errors: List[str] = field(default_factory=list)


class KnowledgeManager:
    """离线知识库管理器"""

    def __init__(self, rag_service: RAGService = None):
        self._rag_service = rag_service or get_rag_service()
        self._fingerprints: Dict[str, Dict[str, str]] = {}

    def create_knowledge_base(
        self,
        name: str,
        description: str = "",
    ) -> KnowledgeBase:
        """创建知识库"""
        return self._rag_service.create_kb(name, description)

    def delete_knowledge_base(self, name: str) -> bool:
        """删除知识库"""
        self._fingerprints.pop(name, None)
        return self._rag_service.delete_kb(name)

    def list_knowledge_bases(self) -> List[str]:
        """列出所有知识库"""
        return self._rag_service.list_kbs()

    def get_knowledge_base_stats(self, name: str) -> Dict[str, Any]:
        """获取知识库统计信息"""
        kb = self._rag_service.get_kb(name)
        if kb is None:
            return {"error": f"知识库 '{name}' 不存在"}
        return kb.get_stats()

    def import_files(
        self,
        kb_name: str,
        file_paths: List[str],
        chunk_strategy: str = "recursive",
        chunk_size: int = 512,
        chunk_overlap: int = 50,
    ) -> ImportResult:
        """
        导入文件到知识库

        Args:
            kb_name: 知识库名称
            file_paths: 文件路径列表
            chunk_strategy: 分块策略 (recursive/markdown/three_level)
            chunk_size: 分块大小
            chunk_overlap: 分块重叠

        Returns:
            ImportResult
        """
        kb = self._rag_service.get_kb(kb_name)
        if kb is None:
            kb = self._rag_service.create_kb(kb_name)

        result = ImportResult(
            kb_name=kb_name,
            total_files=len(file_paths),
            processed_files=0,
            skipped_files=0,
            total_chunks=0,
        )

        for file_path in file_paths:
            path = Path(file_path)
            if not path.exists():
                result.errors.append(f"文件不存在: {file_path}")
                result.skipped_files += 1
                continue

            file_fingerprint = self._compute_file_fingerprint(path)
            existing_fp = self._get_file_fingerprint(kb_name, str(path))

            if existing_fp == file_fingerprint:
                result.skipped_files += 1
                continue

            try:
                documents = self._load_and_chunk_file(
                    path, chunk_strategy, chunk_size, chunk_overlap
                )
                if documents:
                    count = kb.vectorstore.add_documents(documents)
                    result.total_chunks += count
                    result.processed_files += 1
                    self._set_file_fingerprint(kb_name, str(path), file_fingerprint)
                else:
                    result.skipped_files += 1
            except Exception as e:
                result.errors.append(f"处理文件 {file_path} 失败: {str(e)}")
                result.skipped_files += 1
                logger.error(f"Failed to import {file_path}: {e}")

        if result.processed_files > 0:
            kb._save_kb_meta(result.total_chunks, is_incremental=True)
            self._save_fingerprints(kb_name)

        return result

    def import_directory(
        self,
        kb_name: str,
        directory: str,
        recursive: bool = True,
        chunk_strategy: str = "recursive",
        chunk_size: int = 512,
        chunk_overlap: int = 50,
    ) -> ImportResult:
        """
        导入目录下的所有文档

        Args:
            kb_name: 知识库名称
            directory: 目录路径
            recursive: 是否递归扫描子目录
            chunk_strategy: 分块策略
            chunk_size: 分块大小
            chunk_overlap: 分块重叠

        Returns:
            ImportResult
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            return ImportResult(
                kb_name=kb_name,
                total_files=0,
                processed_files=0,
                skipped_files=0,
                total_chunks=0,
                errors=[f"目录不存在: {directory}"],
            )

        extensions = FileTypeRouter.get_supported_extensions()
        pattern = "**/*" if recursive else "*"
        file_paths = [
            str(f) for f in dir_path.glob(pattern)
            if f.is_file() and f.suffix.lower() in extensions
        ]

        return self.import_files(
            kb_name, file_paths, chunk_strategy, chunk_size, chunk_overlap
        )

    def search(
        self,
        kb_name: str,
        query: str,
        k: int = 5,
    ) -> List[RetrievalResult]:
        """搜索知识库"""
        return self._rag_service.search(query, kb_name, k)

    def get_context(
        self,
        kb_name: str,
        query: str,
        k: int = 5,
        max_length: int = 3000,
    ) -> str:
        """获取知识库上下文"""
        return self._rag_service.get_context(query, kb_name, k, max_length)

    def _load_and_chunk_file(
        self,
        path: Path,
        chunk_strategy: str,
        chunk_size: int,
        chunk_overlap: int,
    ) -> List[Document]:
        """加载文件并分块"""
        loader = DocumentLoader(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        documents = loader.load_files([str(path)])

        if chunk_strategy == "markdown" and path.suffix.lower() in (".md", ".markdown"):
            text = ""
            encodings = ["utf-8", "utf-8-sig", "gbk", "gb2312", "latin-1"]
            for encoding in encodings:
                try:
                    text = path.read_text(encoding=encoding)
                    break
                except (UnicodeDecodeError, IOError):
                    continue
            if text:
                documents = MarkdownChunker.chunk(text, chunk_size, chunk_overlap)
                for doc in documents:
                    doc.metadata["source"] = path.name
                    doc.metadata["file_path"] = str(path)
                    doc.metadata["type"] = "markdown"

        return documents

    @staticmethod
    def _compute_file_fingerprint(path: Path) -> str:
        """计算文件指纹（MD5）"""
        hasher = hashlib.md5()
        try:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return ""

    def _get_file_fingerprint(self, kb_name: str, file_path: str) -> str:
        """获取已存储的文件指纹"""
        kb_fps = self._fingerprints.get(kb_name, {})
        return kb_fps.get(file_path, "")

    def _set_file_fingerprint(self, kb_name: str, file_path: str, fingerprint: str):
        """设置文件指纹"""
        if kb_name not in self._fingerprints:
            self._fingerprints[kb_name] = {}
        self._fingerprints[kb_name][file_path] = fingerprint

    def _save_fingerprints(self, kb_name: str):
        """持久化指纹数据"""
        kb = self._rag_service.get_kb(kb_name)
        if kb is None:
            return

        fp_path = os.path.join(kb.persist_dir, "fingerprints.json")
        os.makedirs(os.path.dirname(fp_path), exist_ok=True)
        with open(fp_path, "w", encoding="utf-8") as f:
            json.dump(self._fingerprints.get(kb_name, {}), f, ensure_ascii=False, indent=2)

    def _load_fingerprints(self, kb_name: str):
        """加载指纹数据"""
        kb = self._rag_service.get_kb(kb_name)
        if kb is None:
            return

        fp_path = os.path.join(kb.persist_dir, "fingerprints.json")
        if os.path.exists(fp_path):
            try:
                with open(fp_path, "r", encoding="utf-8") as f:
                    self._fingerprints[kb_name] = json.load(f)
            except Exception:
                self._fingerprints[kb_name] = {}

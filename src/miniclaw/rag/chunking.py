"""
MiniClaw Chunking Strategies

分块策略层级:
  1. 三级分层分块 (ThreeLevelChunker) — 参考 SuperMew
     L1(大块1200+) → L2(中块600+) → L3(叶子块300+)
     仅 L3 叶子块向量化，L1/L2 存入 ParentChunkStore
     检索时 Auto-merging: 同一父块的子块≥阈值时合并为父块

  2. Markdown 结构分块 (MarkdownChunker)
     按标题层级分割，保留文档结构

  3. 递归字符分块 (RecursiveChunker)
     通用文本，支持中文分隔符优化

  4. Token 分块 (TokenChunker)
     精确控制 Token 数量
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
import re

from miniclaw.rag.types import Document, ChunkNode, ChunkLevel


class RecursiveChunker:
    """递归字符分块 — 通用文本，中文分隔符优化"""

    SEPARATORS = ["\n\n", "\n", "。", "！", "？", ".", "!", "?", "；", ";", " ", ""]

    @staticmethod
    def chunk(
        text: str,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        separators: List[str] = None,
    ) -> List[Document]:
        separators = separators or RecursiveChunker.SEPARATORS
        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter

            splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                separators=separators,
            )
            chunks = splitter.split_text(text)
            return [
                Document(content=chunk, metadata={"chunk_index": i, "chunk_strategy": "recursive"})
                for i, chunk in enumerate(chunks)
            ]
        except ImportError:
            return RecursiveChunker._fallback_chunk(text, chunk_size, chunk_overlap, separators)

    @staticmethod
    def _fallback_chunk(
        text: str,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        separators: List[str] = None,
    ) -> List[Document]:
        separators = separators or RecursiveChunker.SEPARATORS
        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size
            if end < len(text):
                best_split = end
                for sep in separators:
                    pos = text.rfind(sep, start, end)
                    if pos > start:
                        best_split = pos + len(sep)
                        break
                end = best_split

            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(
                    Document(
                        content=chunk_text,
                        metadata={"chunk_index": len(chunks), "chunk_strategy": "recursive"},
                    )
                )

            start = end - chunk_overlap
            if start < 0:
                start = 0
            if start >= len(text):
                break

        return chunks


class TokenChunker:
    """Token 分块 — 精确控制 Token 数量"""

    @staticmethod
    def chunk(
        text: str,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        encoding_name: str = "cl100k_base",
    ) -> List[Document]:
        try:
            from langchain_text_splitters import TokenTextSplitter

            splitter = TokenTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                encoding_name=encoding_name,
            )
            chunks = splitter.split_text(text)
            return [
                Document(content=chunk, metadata={"chunk_index": i, "chunk_strategy": "token"})
                for i, chunk in enumerate(chunks)
            ]
        except ImportError:
            return RecursiveChunker.chunk(text, chunk_size, chunk_overlap)


class MarkdownChunker:
    """Markdown 结构分块 — 按标题层级分割，保留文档结构"""

    HEADERS_TO_SPLIT = [
        ("#", "header1"),
        ("##", "header2"),
        ("###", "header3"),
    ]

    @staticmethod
    def chunk(text: str, chunk_size: int = 512, chunk_overlap: int = 50) -> List[Document]:
        try:
            from langchain_text_splitters import MarkdownHeaderTextSplitter

            splitter = MarkdownHeaderTextSplitter(
                headers_to_split_on=MarkdownChunker.HEADERS_TO_SPLIT,
            )
            md_docs = splitter.split_text(text)
            documents = []
            for i, md_doc in enumerate(md_docs):
                content = md_doc.page_content
                if len(content) > chunk_size:
                    sub_chunks = RecursiveChunker.chunk(content, chunk_size, chunk_overlap)
                    for j, sub in enumerate(sub_chunks):
                        meta = {**md_doc.metadata, **sub.metadata, "chunk_index": i}
                        documents.append(Document(content=sub.content, metadata=meta))
                else:
                    documents.append(
                        Document(
                            content=content,
                            metadata={**md_doc.metadata, "chunk_index": i, "chunk_strategy": "markdown"},
                        )
                    )
            return documents
        except ImportError:
            return RecursiveChunker.chunk(text, chunk_size, chunk_overlap)


class ThreeLevelChunker:
    """
    三级分层分块 — 参考 SuperMew

    L1(大块) → L2(中块) → L3(叶子块)
    仅 L3 叶子块向量化，L1/L2 存入 ParentChunkStore
    检索时 Auto-merging: 同一父块的子块≥阈值时合并为父块

    层级关系:
      root_chunk_id: 始终指向 L1 大块
      parent_chunk_id: L3→L2, L2→L1, L1→空
    """

    def __init__(
        self,
        level_1_size: int = 1200,
        level_2_size: int = 600,
        level_3_size: int = 300,
        level_1_overlap: int = 100,
        level_2_overlap: int = 50,
        level_3_overlap: int = 30,
    ):
        self.level_1_size = max(1200, level_1_size)
        self.level_2_size = max(600, level_2_size)
        self.level_3_size = max(300, level_3_size)
        self.level_1_overlap = level_1_overlap
        self.level_2_overlap = level_2_overlap
        self.level_3_overlap = level_3_overlap

    def chunk(
        self,
        text: str,
        source: str = "",
        page: int = 0,
    ) -> tuple[List[ChunkNode], List[ChunkNode], List[ChunkNode]]:
        """
        返回 (l1_nodes, l2_nodes, l3_nodes)
        l3_nodes 是叶子节点，用于向量化
        l1_nodes, l2_nodes 是父节点，用于 Auto-merging
        """
        l1_nodes = []
        l2_nodes = []
        l3_nodes = []

        l1_chunks = self._split_text(text, self.level_1_size, self.level_1_overlap)
        global_idx = 0

        for l1_idx, l1_text in enumerate(l1_chunks):
            l1_id = f"{source}::p{page}::l1::{l1_idx}" if source else f"l1::{l1_idx}"
            l1_node = ChunkNode(
                content=l1_text,
                chunk_id=l1_id,
                chunk_level=ChunkLevel.LEVEL_1,
                parent_chunk_id="",
                root_chunk_id=l1_id,
                metadata={"source": source, "page": page, "level": 1},
            )
            l1_nodes.append(l1_node)

            l2_chunks = self._split_text(l1_text, self.level_2_size, self.level_2_overlap)
            for l2_idx, l2_text in enumerate(l2_chunks):
                l2_id = f"{l1_id}::l2::{l2_idx}"
                l2_node = ChunkNode(
                    content=l2_text,
                    chunk_id=l2_id,
                    chunk_level=ChunkLevel.LEVEL_2,
                    parent_chunk_id=l1_id,
                    root_chunk_id=l1_id,
                    metadata={"source": source, "page": page, "level": 2},
                )
                l2_nodes.append(l2_node)

                l3_chunks = self._split_text(l2_text, self.level_3_size, self.level_3_overlap)
                for l3_idx, l3_text in enumerate(l3_chunks):
                    l3_id = f"{l2_id}::l3::{l3_idx}"
                    l3_node = ChunkNode(
                        content=l3_text,
                        chunk_id=l3_id,
                        chunk_level=ChunkLevel.LEVEL_3,
                        parent_chunk_id=l2_id,
                        root_chunk_id=l1_id,
                        metadata={
                            "source": source,
                            "page": page,
                            "level": 3,
                            "chunk_index": global_idx,
                        },
                    )
                    l3_nodes.append(l3_node)
                    global_idx += 1

        return l1_nodes, l2_nodes, l3_nodes

    def _split_text(self, text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
        if len(text) <= chunk_size:
            return [text] if text.strip() else []

        chunks = []
        start = 0
        separators = ["\n\n", "\n", "。", "！", "？", ".", "!", "?", "；", ";", " ", ""]

        while start < len(text):
            end = start + chunk_size
            if end < len(text):
                best_split = end
                for sep in separators:
                    pos = text.rfind(sep, start, end)
                    if pos > start:
                        best_split = pos + len(sep)
                        break
                end = best_split

            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(chunk_text)

            start = end - chunk_overlap
            if start < 0:
                start = 0
            if start >= len(text):
                break

        return chunks


class AutoMerger:
    """
    Auto-merging 检索 — 参考 SuperMew

    当同一父块的子块被检索到的数量≥阈值时，
    将这些子块合并为父块，提供更完整的上下文
    """

    def __init__(self, threshold: int = 2, parent_store: Dict[str, ChunkNode] = None):
        self.threshold = threshold
        self._parent_store: Dict[str, ChunkNode] = parent_store or {}

    def register_parents(self, nodes: List[ChunkNode]):
        for node in nodes:
            self._parent_store[node.chunk_id] = node

    def merge(self, documents: List[Document], top_k: int = 5) -> List[Document]:
        if not documents:
            return documents

        parent_groups: Dict[str, List[Document]] = {}
        ungrouped = []

        for doc in documents:
            parent_id = doc.metadata.get("parent_chunk_id", "")
            if parent_id and parent_id in self._parent_store:
                if parent_id not in parent_groups:
                    parent_groups[parent_id] = []
                parent_groups[parent_id].append(doc)
            else:
                ungrouped.append(doc)

        merged = []
        merged_ids = set()

        for parent_id, children in parent_groups.items():
            if len(children) >= self.threshold:
                parent_node = self._parent_store[parent_id]
                max_score = max(
                    float(doc.metadata.get("score", 0)) for doc in children
                )
                merged_doc = Document(
                    content=parent_node.content,
                    metadata={
                        **parent_node.metadata,
                        "merged_from_children": True,
                        "child_count": len(children),
                        "score": max_score,
                    },
                    id=parent_node.chunk_id,
                )
                merged.append(merged_doc)
                for child in children:
                    merged_ids.add(child.id or "")
            else:
                ungrouped.extend(children)

        merged.extend(ungrouped)
        merged.sort(key=lambda d: float(d.metadata.get("score", 0)), reverse=True)
        return merged[:top_k]


class ChunkingStrategy:
    """分块策略入口 — 向后兼容旧接口"""

    @staticmethod
    def recursive_chunking(
        text: str,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        separators: List[str] = None,
    ) -> List[Document]:
        return RecursiveChunker.chunk(text, chunk_size, chunk_overlap, separators)

    @staticmethod
    def token_chunking(
        text: str,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        encoding_name: str = "cl100k_base",
    ) -> List[Document]:
        return TokenChunker.chunk(text, chunk_size, chunk_overlap, encoding_name)

    @staticmethod
    def markdown_chunking(text: str, chunk_size: int = 512, chunk_overlap: int = 50) -> List[Document]:
        return MarkdownChunker.chunk(text, chunk_size, chunk_overlap)

    @staticmethod
    def three_level_chunking(
        text: str,
        source: str = "",
        page: int = 0,
        level_1_size: int = 1200,
        level_2_size: int = 600,
        level_3_size: int = 300,
    ) -> tuple[List[ChunkNode], List[ChunkNode], List[ChunkNode]]:
        chunker = ThreeLevelChunker(
            level_1_size=level_1_size,
            level_2_size=level_2_size,
            level_3_size=level_3_size,
        )
        return chunker.chunk(text, source, page)

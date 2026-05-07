"""
MiniClaw RAG Service
Unified RAG service: knowledge base management + retrieval
"""

from typing import List, Optional, Dict, Any
from pathlib import Path
import os
import json
from datetime import datetime

from loguru import logger

from miniclaw.config.settings import settings
from miniclaw.rag.types import Document, RetrievalResult
from miniclaw.rag.vectorstore import FAISSVectorStore, MilvusVectorStore, get_vectorstore
from miniclaw.rag.document_loader import DocumentLoader
from miniclaw.rag.retriever import HybridRetriever, SearchMode, FusionMethod


class KnowledgeBase:
    """知识库：管理文档索引和检索"""

    def __init__(
        self,
        name: str,
        description: str = "",
        persist_dir: str = None,
        use_milvus: bool = False,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.description = description
        self.use_milvus = use_milvus
        self.persist_dir = persist_dir or os.path.join(
            settings.DATA_DIR, "knowledge_bases", name
        )
        self.config = config or {}
        self._vectorstore = None
        self._retriever = None
        self._loader = DocumentLoader(
            chunk_size=self.config.get("chunk_size", 512),
            chunk_overlap=self.config.get("chunk_overlap", 50)
        )

    @property
    def vectorstore(self):
        if self._vectorstore is None:
            self._vectorstore = FAISSVectorStore(
                collection_name=self.name,
                persist_dir=os.path.join(self.persist_dir, "vectorstore"),
            )
        return self._vectorstore

    @property
    def retriever(self):
        if self._retriever is None:
            self._retriever = HybridRetriever(
                vectorstore=self.vectorstore,
                collection_name=self.name,
                persist_dir=os.path.join(self.persist_dir, "bm25"),
                bm25_k1=self.config.get("bm25_k1", 1.5),
                bm25_b=self.config.get("bm25_b", 0.75),
            )
        return self._retriever

    def add_files(self, file_paths: List[str]) -> int:
        documents = self._loader.load_files(file_paths)
        if not documents:
            return 0
        count = self.vectorstore.add_documents(documents)
        self.retriever.index_documents(documents)
        self._save_kb_meta(count, is_incremental=True)
        return count

    def add_directory(self, directory: str, recursive: bool = True) -> int:
        documents = self._loader.load_directory(directory, recursive)
        if not documents:
            return 0
        count = self.vectorstore.add_documents(documents)
        self.retriever.index_documents(documents)
        self._save_kb_meta(count, is_incremental=True)
        return count

    async def aadd_files(self, file_paths: List[str]) -> int:
        documents = self._loader.load_files(file_paths)
        if not documents:
            return 0
        count = await self.vectorstore.aadd_documents(documents)
        self.retriever.index_documents(documents)
        self._save_kb_meta(count, is_incremental=True)
        return count

    async def aadd_directory(self, directory: str, recursive: bool = True) -> int:
        documents = self._loader.load_directory(directory, recursive)
        if not documents:
            return 0
        count = await self.vectorstore.aadd_documents(documents)
        self.retriever.index_documents(documents)
        self._save_kb_meta(count, is_incremental=True)
        return count

    def add_texts(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> int:
        documents = []
        for i, text in enumerate(texts):
            metadata = metadatas[i] if metadatas and i < len(metadatas) else {}
            documents.append(Document(content=text, metadata=metadata))
        count = self.vectorstore.add_documents(documents)
        self.retriever.index_documents(documents)
        return count

    def search(
        self, 
        query: str, 
        k: int = 5, 
        mode: SearchMode = SearchMode.HYBRID,
        fusion_method: FusionMethod = FusionMethod.RRF,
    ) -> List[RetrievalResult]:
        logger.info(f"[KB:{self.name}] search: query='{query[:50]}...', k={k}, mode={mode}")
        results = self.retriever.retrieve(
            query, 
            mode=mode, 
            k=k, 
            fusion_method=fusion_method
        )
        logger.info(f"[KB:{self.name}] search results: count={len(results)}")
        for i, r in enumerate(results):
            logger.info(f"[KB:{self.name}]   result[{i}]: score={r.score:.4f}, source={r.source[:30]}, content={r.content[:50]}...")
        return results

    async def asearch(
        self, 
        query: str, 
        k: int = 5, 
        mode: SearchMode = SearchMode.HYBRID,
        fusion_method: FusionMethod = FusionMethod.RRF,
    ) -> List[RetrievalResult]:
        results = await self.retriever.aretrieve(
            query, 
            mode=mode, 
            k=k, 
            fusion_method=fusion_method
        )
        return results

    def get_context(self, query: str, k: int = 5, max_length: int = 3000) -> str:
        logger.info(f"[KB:{self.name}] get_context: query='{query[:50]}...', k={k}, max_length={max_length}")
        results = self.search(query, k)
        if not results:
            logger.warning(f"[KB:{self.name}] No results found for query")
            return ""

        parts = []
        current_len = 0
        for i, r in enumerate(results):
            entry = f"[来源{i+1}: {r.source} (相关度:{r.score:.2f})]\n{r.content}\n"
            if current_len + len(entry) > max_length:
                logger.info(f"[KB:{self.name}] Truncated context at {i} results (max_length reached)")
                break
            parts.append(entry)
            current_len += len(entry)

        context = "\n".join(parts)
        logger.info(f"[KB:{self.name}] Context built: {len(parts)} results, {len(context)} chars")
        return context

    def _save_kb_meta(self, added_count: int, is_incremental: bool = False):
        os.makedirs(self.persist_dir, exist_ok=True)
        meta_path = os.path.join(self.persist_dir, "kb_meta.json")

        existing = {}
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                pass

        if is_incremental:
            existing["document_count"] = existing.get("document_count", 0) + added_count
        else:
            existing["document_count"] = added_count

        existing.update(
            {
                "name": self.name,
                "description": self.description,
                "updated_at": datetime.now().isoformat(),
            }
        )
        if self.config:
            existing["config"] = self.config
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

    def get_stats(self) -> Dict[str, Any]:
        stats = self.vectorstore.get_stats()
        meta_path = os.path.join(self.persist_dir, "kb_meta.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    stats.update(json.load(f))
            except Exception:
                pass
        return stats


class RAGService:
    """统一 RAG 服务，管理多个知识库"""

    _instance: Optional["RAGService"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, kb_base_dir: str = None):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self.kb_base_dir = kb_base_dir or os.path.join(
            settings.DATA_DIR, "knowledge_bases"
        )
        self._knowledge_bases: Dict[str, KnowledgeBase] = {}

    def create_kb(self, name: str, description: str = "", config: Optional[Dict[str, Any]] = None, use_milvus: bool = False) -> KnowledgeBase:
        if name not in self._knowledge_bases:
            self._knowledge_bases[name] = KnowledgeBase(
                name=name,
                description=description,
                persist_dir=os.path.join(self.kb_base_dir, name),
                use_milvus=use_milvus,
                config=config,
            )
            self._knowledge_bases[name]._save_kb_meta(0)
        return self._knowledge_bases[name]

    def get_kb(self, name: str) -> Optional[KnowledgeBase]:
        if name in self._knowledge_bases:
            return self._knowledge_bases[name]

        kb_dir = os.path.join(self.kb_base_dir, name)
        if os.path.exists(kb_dir):
            meta_path = os.path.join(kb_dir, "kb_meta.json")
            config = None
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                        config = meta.get("config")
                except Exception:
                    pass
            kb = KnowledgeBase(name=name, persist_dir=kb_dir, config=config)
            self._knowledge_bases[name] = kb
            return kb
        return None

    def list_kbs(self) -> List[str]:
        kbs = set(self._knowledge_bases.keys())
        if os.path.exists(self.kb_base_dir):
            for item in os.listdir(self.kb_base_dir):
                item_path = os.path.join(self.kb_base_dir, item)
                if os.path.isdir(item_path) and not item.startswith((".", "__")):
                    kbs.add(item)
        return sorted(kbs)

    def delete_kb(self, name: str) -> bool:
        import shutil

        kb = self.get_kb(name)
        if kb is None:
            return False
        if os.path.exists(kb.persist_dir):
            shutil.rmtree(kb.persist_dir)
        self._knowledge_bases.pop(name, None)
        return True

    def search(
        self,
        query: str,
        kb_name: str,
        k: int = 5,
    ) -> List[RetrievalResult]:
        kb = self.get_kb(kb_name)
        if kb is None:
            return []
        return kb.search(query, k)

    async def asearch(
        self,
        query: str,
        kb_name: str,
        k: int = 5,
    ) -> List[RetrievalResult]:
        kb = self.get_kb(kb_name)
        if kb is None:
            return []
        return await kb.asearch(query, k)

    def get_context(
        self,
        query: str,
        kb_name: str,
        k: int = 5,
        max_length: int = 3000,
    ) -> str:
        kb = self.get_kb(kb_name)
        if kb is None:
            return ""
        return kb.get_context(query, k, max_length)


def get_rag_service() -> RAGService:
    return RAGService()

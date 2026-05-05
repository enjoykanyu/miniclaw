"""
MiniClaw Vector Store
Supports FAISS (local) and Milvus (production) backends

FAISS 持久化机制:
  - metadata.json: 文档内容 + 元数据
  - faiss_index.bin: FAISS 索引（二进制）
  - embeddings.npy: 向量矩阵（numpy 格式，用于 fallback 重建）

加载优先级:
  1. faiss_index.bin 存在 → 直接加载索引
  2. embeddings.npy 存在 → 从向量重建索引
  3. 都不存在 → 空索引，等待 add_documents
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import json
import os
import logging

from miniclaw.config.settings import settings
from miniclaw.rag.embeddings import get_embeddings, get_embedding_dimension
from miniclaw.rag.types import Document

logger = logging.getLogger(__name__)


class FAISSVectorStore:
    """基于 FAISS 的本地向量存储，无需外部服务依赖"""

    def __init__(
        self,
        collection_name: str = "miniclaw",
        persist_dir: str = None,
        embedding_provider: str = None,
    ):
        self.collection_name = collection_name
        self.persist_dir = persist_dir or os.path.join(
            settings.DATA_DIR, "vectorstore", collection_name
        )
        self.embedding_provider = embedding_provider
        self._embeddings = None
        self._index = None
        self._documents: List[Document] = []
        self._loaded = False

    @property
    def embeddings(self):
        if self._embeddings is None:
            self._embeddings = get_embeddings(self.embedding_provider)
        return self._embeddings

    def _ensure_loaded(self):
        if not self._loaded:
            self._load_from_disk()
            self._loaded = True

    def _load_from_disk(self):
        meta_path = os.path.join(self.persist_dir, "metadata.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._documents = [
                    Document(
                        content=d["content"],
                        metadata=d.get("metadata", {}),
                        id=d.get("id"),
                    )
                    for d in data.get("documents", [])
                ]
            except Exception as e:
                logger.error(f"Failed to load metadata: {e}")
                self._documents = []

        index_path = os.path.join(self.persist_dir, "faiss_index.bin")
        if os.path.exists(index_path):
            try:
                import faiss

                self._index = faiss.read_index(index_path)
                logger.info(
                    f"Loaded FAISS index: {self._index.ntotal} vectors, dim={self._index.d}"
                )
            except Exception as e:
                logger.error(f"Failed to load FAISS index: {e}")
                self._index = None

        embeddings_path = os.path.join(self.persist_dir, "embeddings.npy")
        if os.path.exists(embeddings_path) and self._documents:
            try:
                import numpy as np

                embeddings_np = np.load(embeddings_path)
                for i, doc in enumerate(self._documents):
                    if i < len(embeddings_np):
                        doc.embedding = embeddings_np[i].tolist()
            except Exception as e:
                logger.error(f"Failed to load embeddings: {e}")

        if self._index is None and self._documents:
            self._rebuild_index_from_embeddings()

    def _rebuild_index_from_embeddings(self):
        embeddings_list = [doc.embedding for doc in self._documents if doc.embedding]
        if not embeddings_list:
            logger.warning("No embeddings available to rebuild FAISS index")
            return
        try:
            import numpy as np
            import faiss

            vectors_np = np.array(embeddings_list, dtype=np.float32)
            dimension = vectors_np.shape[1]
            self._index = faiss.IndexFlatIP(dimension)
            self._index.add(vectors_np)
            logger.info(
                f"Rebuilt FAISS index from embeddings: {self._index.ntotal} vectors"
            )
        except Exception as e:
            logger.error(f"Failed to rebuild FAISS index: {e}")
            self._index = None

    def _save_to_disk(self):
        os.makedirs(self.persist_dir, exist_ok=True)

        meta_path = os.path.join(self.persist_dir, "metadata.json")
        data = {
            "collection_name": self.collection_name,
            "documents": [
                {
                    "content": doc.content,
                    "metadata": doc.metadata,
                    "id": doc.id,
                }
                for doc in self._documents
            ],
            "updated_at": datetime.now().isoformat(),
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        if self._index is not None:
            try:
                import faiss

                index_path = os.path.join(self.persist_dir, "faiss_index.bin")
                faiss.write_index(self._index, index_path)
            except Exception as e:
                logger.error(f"Failed to save FAISS index: {e}")

        embeddings_list = [doc.embedding for doc in self._documents if doc.embedding]
        if embeddings_list:
            try:
                import numpy as np

                embeddings_np = np.array(embeddings_list, dtype=np.float32)
                np.save(
                    os.path.join(self.persist_dir, "embeddings.npy"), embeddings_np
                )
            except Exception as e:
                logger.error(f"Failed to save embeddings: {e}")

    def add_documents(
        self,
        documents: List[Document],
        batch_size: int = 32,
    ) -> int:
        self._ensure_loaded()
        added_count = 0

        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            texts = [doc.content for doc in batch]

            try:
                vectors = self.embeddings.embed_documents(texts)
            except Exception as e:
                logger.error(f"Embedding failed for batch {i // batch_size}: {e}")
                raise

            for doc, vector in zip(batch, vectors):
                doc.embedding = vector
                doc.id = doc.id or f"{self.collection_name}_{len(self._documents)}"
                self._documents.append(doc)
                added_count += 1

            self._update_index(vectors)

        self._save_to_disk()
        return added_count

    async def aadd_documents(
        self,
        documents: List[Document],
        batch_size: int = 32,
    ) -> int:
        self._ensure_loaded()
        added_count = 0

        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            texts = [doc.content for doc in batch]

            try:
                vectors = await self.embeddings.aembed_documents(texts)
            except Exception as e:
                logger.error(f"Async embedding failed for batch {i // batch_size}: {e}")
                raise

            for doc, vector in zip(batch, vectors):
                doc.embedding = vector
                doc.id = doc.id or f"{self.collection_name}_{len(self._documents)}"
                self._documents.append(doc)
                added_count += 1

            self._update_index(vectors)

        self._save_to_disk()
        return added_count

    def add_texts(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> int:
        documents = []
        for i, text in enumerate(texts):
            metadata = metadatas[i] if metadatas and i < len(metadatas) else {}
            documents.append(Document(content=text, metadata=metadata))
        return self.add_documents(documents)

    def _update_index(self, new_vectors: List[List[float]]):
        try:
            import numpy as np

            vectors_np = np.array(new_vectors, dtype=np.float32)

            if self._index is None:
                import faiss

                dimension = vectors_np.shape[1]
                self._index = faiss.IndexFlatIP(dimension)

            self._index.add(vectors_np)
        except ImportError:
            logger.warning("faiss/numpy not available, index not updated")
            self._index = None

    def _apply_filter(
        self,
        documents: List[Document],
        filter_expr: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        if not filter_expr:
            return documents

        filtered = []
        for doc in documents:
            match = True
            for key, value in filter_expr.items():
                if doc.metadata.get(key) != value:
                    match = False
                    break
            if match:
                filtered.append(doc)
        return filtered

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter_expr: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        results_with_scores = self.similarity_search_with_score(query, k, filter_expr)
        return [doc for doc, _ in results_with_scores]

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 4,
        filter_expr: Optional[Dict[str, Any]] = None,
    ) -> List[tuple]:
        self._ensure_loaded()

        logger.info(f"[FAISS] similarity_search: query='{query[:50]}...', k={k}, docs_count={len(self._documents)}, index_size={self._index.ntotal if self._index else 0}")

        if not self._documents:
            logger.warning("[FAISS] No documents in vectorstore")
            return []

        try:
            import numpy as np
        except ImportError:
            logger.error("[FAISS] numpy not available")
            return [(doc, 0.0) for doc in self._documents[:k]]

        # Embedding 查询
        logger.info(f"[FAISS] Embedding query with provider={self.embedding_provider or 'default'}")
        query_embedding = self.embeddings.embed_query(query)
        logger.info(f"[FAISS] Query embedding shape: {len(query_embedding)}, first_5={query_embedding[:5]}")

        query_vector = np.array(query_embedding, dtype=np.float32)

        if self._index is not None and self._index.ntotal > 0:
            try:
                import faiss

                search_k = min(k * 3, self._index.ntotal) if filter_expr else min(k, self._index.ntotal)
                query_2d = query_vector.reshape(1, -1)
                logger.info(f"[FAISS] Searching index: search_k={search_k}, index_ntotal={self._index.ntotal}")
                scores, indices = self._index.search(query_2d, search_k)

                results = []
                for score, idx in zip(scores[0], indices[0]):
                    if 0 <= idx < len(self._documents):
                        doc = self._documents[idx]
                        results.append((doc, float(score)))

                if filter_expr:
                    results = [
                        (doc, score)
                        for doc, score in results
                        if self._apply_filter([doc], filter_expr)
                    ]

                logger.info(f"[FAISS] Search results: count={len(results[:k])}, scores={[round(s, 4) for _, s in results[:k]]}")
                return results[:k]
            except Exception as e:
                logger.error(f"[FAISS] FAISS search failed: {e}")

        # Fallback: brute force cosine similarity
        logger.info("[FAISS] Falling back to brute force cosine similarity")
        results = []
        for doc in self._documents:
            if doc.embedding:
                doc_vec = np.array(doc.embedding, dtype=np.float32)
                score = float(
                    np.dot(query_vector, doc_vec)
                    / (np.linalg.norm(query_vector) * np.linalg.norm(doc_vec) + 1e-8)
                )
                results.append((doc, score))

        if filter_expr:
            results = [
                (doc, score)
                for doc, score in results
                if self._apply_filter([doc], filter_expr)
            ]

        results.sort(key=lambda x: x[1], reverse=True)
        logger.info(f"[FAISS] Brute force results: count={len(results[:k])}, scores={[round(s, 4) for _, s in results[:k]]}")
        return results[:k]

    async def asimilarity_search(
        self,
        query: str,
        k: int = 4,
        filter_expr: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        results_with_scores = await self.asimilarity_search_with_score(
            query, k, filter_expr
        )
        return [doc for doc, _ in results_with_scores]

    async def asimilarity_search_with_score(
        self,
        query: str,
        k: int = 4,
        filter_expr: Optional[Dict[str, Any]] = None,
    ) -> List[tuple]:
        self._ensure_loaded()

        if not self._documents:
            return []

        try:
            import numpy as np
        except ImportError:
            return [(doc, 0.0) for doc in self._documents[:k]]

        query_vector = np.array(
            await self.embeddings.aembed_query(query), dtype=np.float32
        )

        if self._index is not None and self._index.ntotal > 0:
            try:
                import faiss

                search_k = min(k * 3, self._index.ntotal) if filter_expr else min(k, self._index.ntotal)
                query_2d = query_vector.reshape(1, -1)
                scores, indices = self._index.search(query_2d, search_k)

                results = []
                for score, idx in zip(scores[0], indices[0]):
                    if 0 <= idx < len(self._documents):
                        doc = self._documents[idx]
                        results.append((doc, float(score)))

                if filter_expr:
                    results = [
                        (doc, score)
                        for doc, score in results
                        if self._apply_filter([doc], filter_expr)
                    ]

                return results[:k]
            except Exception as e:
                logger.error(f"FAISS async search failed: {e}")

        results = []
        for doc in self._documents:
            if doc.embedding:
                doc_vec = np.array(doc.embedding, dtype=np.float32)
                score = float(
                    np.dot(query_vector, doc_vec)
                    / (np.linalg.norm(query_vector) * np.linalg.norm(doc_vec) + 1e-8)
                )
                results.append((doc, score))

        if filter_expr:
            results = [
                (doc, score)
                for doc, score in results
                if self._apply_filter([doc], filter_expr)
            ]

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:k]

    def delete_all(self) -> bool:
        self._documents = []
        self._index = None
        for fname in ["metadata.json", "faiss_index.bin", "embeddings.npy"]:
            fpath = os.path.join(self.persist_dir, fname)
            if os.path.exists(fpath):
                os.remove(fpath)
        return True

    def get_stats(self) -> Dict[str, Any]:
        self._ensure_loaded()
        return {
            "collection_name": self.collection_name,
            "document_count": len(self._documents),
            "has_index": self._index is not None,
            "index_size": self._index.ntotal if self._index is not None else 0,
            "persist_dir": self.persist_dir,
        }


class MilvusVectorStore:
    """基于 Milvus 的生产级向量存储"""

    def __init__(
        self,
        collection_name: str = "miniclaw",
        host: str = None,
        port: int = None,
        embedding_provider: str = None,
    ):
        self.collection_name = collection_name
        self.host = host or settings.MILVUS_HOST
        self.port = port or settings.MILVUS_PORT
        self.embedding_provider = embedding_provider
        self._client = None
        self._embeddings = None

    @property
    def embeddings(self):
        if self._embeddings is None:
            self._embeddings = get_embeddings(self.embedding_provider)
        return self._embeddings

    def _connect(self) -> bool:
        try:
            from pymilvus import MilvusClient

            self._client = MilvusClient(uri=f"http://{self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Milvus connection failed: {e}")
            return False

    def _ensure_collection(self, dimension: int = None) -> bool:
        if self._client is None:
            if not self._connect():
                return False
        dimension = dimension or get_embedding_dimension(self.embedding_provider)
        try:
            if not self._client.has_collection(self.collection_name):
                self._client.create_collection(
                    collection_name=self.collection_name,
                    dimension=dimension,
                    auto_id=True,
                )
            return True
        except Exception as e:
            logger.error(f"Milvus collection creation failed: {e}")
            return False

    def add_documents(self, documents: List[Document], batch_size: int = 100) -> int:
        if self._client is None:
            if not self._ensure_collection():
                return 0

        added_count = 0
        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            texts = [doc.content for doc in batch]
            try:
                embeddings = self.embeddings.embed_documents(texts)
                data = []
                for doc, emb in zip(batch, embeddings):
                    data.append(
                        {
                            "vector": emb,
                            "content": doc.content,
                            "metadata": json.dumps(doc.metadata, ensure_ascii=False),
                        }
                    )
                self._client.insert(collection_name=self.collection_name, data=data)
                added_count += len(data)
            except Exception as e:
                logger.error(f"Milvus add_documents batch failed: {e}")
                raise
        return added_count

    def add_texts(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> int:
        documents = []
        for i, text in enumerate(texts):
            metadata = metadatas[i] if metadatas and i < len(metadatas) else {}
            documents.append(Document(content=text, metadata=metadata))
        return self.add_documents(documents)

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter_expr: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        results_with_scores = self.similarity_search_with_score(query, k, filter_expr)
        return [doc for doc, _ in results_with_scores]

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 4,
        filter_expr: Optional[Dict[str, Any]] = None,
    ) -> List[tuple]:
        if self._client is None:
            if not self._ensure_collection():
                return []
        try:
            query_embedding = self.embeddings.embed_query(query)

            search_params = {
                "collection_name": self.collection_name,
                "data": [query_embedding],
                "limit": k,
                "output_fields": ["content", "metadata"],
            }

            if filter_expr:
                conditions = []
                for key, value in filter_expr.items():
                    if isinstance(value, str):
                        conditions.append(f'{key} == "{value}"')
                    else:
                        conditions.append(f"{key} == {value}")
                if conditions:
                    search_params["filter"] = " and ".join(conditions)

            results = self._client.search(**search_params)
            documents_with_scores = []
            for hits in results:
                for hit in hits:
                    entity = hit.get("entity", {})
                    content = entity.get("content", "")
                    try:
                        metadata = json.loads(entity.get("metadata", "{}"))
                    except json.JSONDecodeError:
                        metadata = {}
                    score = hit.get("distance", 0.0)
                    documents_with_scores.append(
                        (Document(content=content, metadata=metadata), float(score))
                    )
            return documents_with_scores
        except Exception as e:
            logger.error(f"Milvus similarity search failed: {e}")
            return []

    def delete_all(self) -> bool:
        if self._client is None:
            return False
        try:
            self._client.drop_collection(self.collection_name)
            return True
        except Exception as e:
            logger.error(f"Milvus delete_all failed: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        if self._client is None:
            if not self._connect():
                return {
                    "collection_name": self.collection_name,
                    "connected": False,
                }
        try:
            has_collection = self._client.has_collection(self.collection_name)
            stats = {
                "collection_name": self.collection_name,
                "connected": True,
                "has_collection": has_collection,
            }
            if has_collection:
                info = self._client.describe_collection(self.collection_name)
                stats["document_count"] = info.get("row_count", 0)
            return stats
        except Exception as e:
            logger.error(f"Milvus get_stats failed: {e}")
            return {
                "collection_name": self.collection_name,
                "connected": True,
                "error": str(e),
            }


def get_vectorstore(
    use_milvus: bool = False,
    collection_name: str = "miniclaw",
    embedding_provider: str = None,
) -> Any:
    if use_milvus:
        try:
            store = MilvusVectorStore(
                collection_name=collection_name,
                embedding_provider=embedding_provider,
            )
            if store._connect():
                store._ensure_collection()
                return store
        except Exception:
            pass

    return FAISSVectorStore(
        collection_name=collection_name,
        embedding_provider=embedding_provider,
    )

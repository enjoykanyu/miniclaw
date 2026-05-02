"""
MiniClaw Hybrid Retriever — 混合检索引擎

参考:
  - miniOpenClaw: 三模式检索 (Dense/Keyword/Hybrid) + RRF/加权求和融合
  - ragflow: 加权融合 + 降级策略 + Token权重增强
  - SuperMew: Dense+Sparse RRF + Auto-merging

检索模式:
  1. DENSE — 纯向量检索 (语义匹配)
  2. KEYWORD — 纯关键词检索 (BM25 精确匹配)
  3. HYBRID — 混合检索 (Dense + Keyword RRF 融合)

融合算法:
  - RRF (Reciprocal Rank Fusion): score = Σ 1/(k + rank_i), k=60
    优点: 不依赖绝对分数，对异构检索结果融合效果好
  - Weighted Sum: score = α * normalized_dense + β * normalized_keyword
    优点: 可调权重，需要归一化
"""

from typing import List, Optional, Dict, Any
from enum import Enum
import logging

from miniclaw.rag.types import Document, RetrievalResult
from miniclaw.rag.vectorstore import FAISSVectorStore, get_vectorstore
from miniclaw.rag.embeddings import BM25SparseEmbedding, get_embeddings

logger = logging.getLogger(__name__)


class SearchMode(str, Enum):
    DENSE = "dense"
    KEYWORD = "keyword"
    HYBRID = "hybrid"


class FusionMethod(str, Enum):
    RRF = "rrf"
    WEIGHTED_SUM = "weighted_sum"


def rrf_fusion(
    dense_results: List[tuple],
    keyword_results: List[tuple],
    k: int = 60,
    top_k: int = 10,
) -> List[tuple]:
    """
    RRF (Reciprocal Rank Fusion) 融合算法

    公式: score = Σ 1/(k + rank_i)
    k 值越大，排名靠前的结果优势越小（更平滑）

    Args:
        dense_results: [(Document, score), ...]
        keyword_results: [(Document, score), ...]
        k: RRF 参数，默认 60
        top_k: 返回前 K 个结果

    Returns:
        [(Document, fused_score), ...] 按 fused_score 降序
    """
    scores: Dict[str, float] = {}
    doc_map: Dict[str, Document] = {}

    for rank, (doc, _score) in enumerate(dense_results):
        doc_key = doc.id or doc.content[:100]
        if doc_key not in doc_map:
            doc_map[doc_key] = doc
        scores[doc_key] = scores.get(doc_key, 0.0) + 1.0 / (k + rank + 1)

    for rank, (doc, _score) in enumerate(keyword_results):
        doc_key = doc.id or doc.content[:100]
        if doc_key not in doc_map:
            doc_map[doc_key] = doc
        scores[doc_key] = scores.get(doc_key, 0.0) + 1.0 / (k + rank + 1)

    sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    return [(doc_map[key], score) for key, score in sorted_results]


def weighted_sum_fusion(
    dense_results: List[tuple],
    keyword_results: List[tuple],
    dense_weight: float = 0.6,
    keyword_weight: float = 0.4,
    top_k: int = 10,
) -> List[tuple]:
    """
    加权求和融合（归一化）

    先将两路分数归一化到 [0, 1]，再按权重加权

    Args:
        dense_results: [(Document, score), ...]
        keyword_results: [(Document, score), ...]
        dense_weight: 向量检索权重
        keyword_weight: 关键词检索权重
        top_k: 返回前 K 个结果

    Returns:
        [(Document, fused_score), ...] 按 fused_score 降序
    """
    dense_max = max((s for _, s in dense_results), default=1.0) or 1.0
    keyword_max = max((s for _, s in keyword_results), default=1.0) or 1.0

    scores: Dict[str, float] = {}
    doc_map: Dict[str, Document] = {}

    for doc, score in dense_results:
        doc_key = doc.id or doc.content[:100]
        if doc_key not in doc_map:
            doc_map[doc_key] = doc
        normalized = score / dense_max
        scores[doc_key] = scores.get(doc_key, 0.0) + dense_weight * normalized

    for doc, score in keyword_results:
        doc_key = doc.id or doc.content[:100]
        if doc_key not in doc_map:
            doc_map[doc_key] = doc
        normalized = score / keyword_max
        scores[doc_key] = scores.get(doc_key, 0.0) + keyword_weight * normalized

    sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    return [(doc_map[key], score) for key, score in sorted_results]


class HybridRetriever:
    """
    混合检索器 — Dense向量 + BM25关键词 + RRF/加权融合

    使用方式:
      retriever = HybridRetriever(vectorstore=vs)
      results = retriever.retrieve("查询", mode=SearchMode.HYBRID)
    """

    def __init__(
        self,
        vectorstore: FAISSVectorStore = None,
        collection_name: str = "miniclaw",
        bm25_k1: float = 1.5,
        bm25_b: float = 0.75,
        persist_dir: str = None,
    ):
        self._vectorstore = vectorstore
        self.collection_name = collection_name
        self._bm25 = BM25SparseEmbedding(k1=bm25_k1, b=bm25_b, persist_dir=persist_dir)
        self._bm25_documents: List[Document] = []
        self._bm25_indexed = False

    @property
    def vectorstore(self):
        if self._vectorstore is None:
            self._vectorstore = get_vectorstore(collection_name=self.collection_name)
        return self._vectorstore

    def index_documents(self, documents: List[Document]):
        """索引文档到 BM25（向量存储由 VectorStore 管理）"""
        texts = [doc.content for doc in documents]
        self._bm25.add_documents(texts)
        self._bm25_documents.extend(documents)
        self._bm25_indexed = True

    def retrieve(
        self,
        query: str,
        mode: SearchMode = SearchMode.HYBRID,
        k: int = 5,
        fusion_method: FusionMethod = FusionMethod.RRF,
        dense_weight: float = 0.6,
        keyword_weight: float = 0.4,
        rrf_k: int = 60,
    ) -> List[RetrievalResult]:
        """
        混合检索

        Args:
            query: 查询文本
            mode: 检索模式 (DENSE/KEYWORD/HYBRID)
            k: 返回结果数
            fusion_method: 融合算法 (RRF/WEIGHTED_SUM)
            dense_weight: 向量检索权重（仅 weighted_sum）
            keyword_weight: 关键词检索权重（仅 weighted_sum）
            rrf_k: RRF 参数（仅 RRF）

        Returns:
            List[RetrievalResult]
        """
        dense_results = []
        keyword_results = []

        if mode in (SearchMode.DENSE, SearchMode.HYBRID):
            dense_results = self._dense_search(query, k=k * 2)

        if mode in (SearchMode.KEYWORD, SearchMode.HYBRID):
            keyword_results = self._keyword_search(query, k=k * 2)

        if mode == SearchMode.DENSE:
            fused = dense_results[:k]
        elif mode == SearchMode.KEYWORD:
            fused = keyword_results[:k]
        else:
            if fusion_method == FusionMethod.RRF:
                fused = rrf_fusion(dense_results, keyword_results, k=rrf_k, top_k=k)
            else:
                fused = weighted_sum_fusion(
                    dense_results, keyword_results,
                    dense_weight=dense_weight,
                    keyword_weight=keyword_weight,
                    top_k=k,
                )

        return [
            RetrievalResult(
                content=doc.content,
                source=doc.metadata.get("source", "unknown"),
                score=score,
                metadata=doc.metadata,
            )
            for doc, score in fused
        ]

    async def aretrieve(
        self,
        query: str,
        mode: SearchMode = SearchMode.HYBRID,
        k: int = 5,
        fusion_method: FusionMethod = FusionMethod.RRF,
        dense_weight: float = 0.6,
        keyword_weight: float = 0.4,
        rrf_k: int = 60,
    ) -> List[RetrievalResult]:
        """异步混合检索"""
        dense_results = []
        keyword_results = []

        if mode in (SearchMode.DENSE, SearchMode.HYBRID):
            dense_results = await self._adense_search(query, k=k * 2)

        if mode in (SearchMode.KEYWORD, SearchMode.HYBRID):
            keyword_results = self._keyword_search(query, k=k * 2)

        if mode == SearchMode.DENSE:
            fused = dense_results[:k]
        elif mode == SearchMode.KEYWORD:
            fused = keyword_results[:k]
        else:
            if fusion_method == FusionMethod.RRF:
                fused = rrf_fusion(dense_results, keyword_results, k=rrf_k, top_k=k)
            else:
                fused = weighted_sum_fusion(
                    dense_results, keyword_results,
                    dense_weight=dense_weight,
                    keyword_weight=keyword_weight,
                    top_k=k,
                )

        return [
            RetrievalResult(
                content=doc.content,
                source=doc.metadata.get("source", "unknown"),
                score=score,
                metadata=doc.metadata,
            )
            for doc, score in fused
        ]

    def _dense_search(self, query: str, k: int = 10) -> List[tuple]:
        try:
            return self.vectorstore.similarity_search_with_score(query, k=k)
        except Exception as e:
            logger.error(f"Dense search failed: {e}")
            return []

    async def _adense_search(self, query: str, k: int = 10) -> List[tuple]:
        try:
            return await self.vectorstore.asimilarity_search_with_score(query, k=k)
        except Exception as e:
            logger.error(f"Async dense search failed: {e}")
            return []

    def _keyword_search(self, query: str, k: int = 10) -> List[tuple]:
        if not self._bm25_indexed or not self._bm25_documents:
            return []

        try:
            query_sparse = self._bm25.get_sparse_embedding(query)
            if not query_sparse:
                return []

            scored_docs = []
            for doc in self._bm25_documents:
                doc_sparse = self._bm25.get_sparse_embedding(doc.content)
                score = self._sparse_cosine_similarity(query_sparse, doc_sparse)
                if score > 0:
                    scored_docs.append((doc, score))

            scored_docs.sort(key=lambda x: x[1], reverse=True)
            return scored_docs[:k]
        except Exception as e:
            logger.error(f"Keyword search failed: {e}")
            return []

    @staticmethod
    def _sparse_cosine_similarity(
        vec_a: Dict[int, float],
        vec_b: Dict[int, float],
    ) -> float:
        common_keys = set(vec_a.keys()) & set(vec_b.keys())
        if not common_keys:
            return 0.0

        dot_product = sum(vec_a[k] * vec_b[k] for k in common_keys)
        norm_a = sum(v * v for v in vec_a.values()) ** 0.5
        norm_b = sum(v * v for v in vec_b.values()) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

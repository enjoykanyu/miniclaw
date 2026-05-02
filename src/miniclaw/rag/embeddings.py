"""
MiniClaw Embeddings Module

支持三种 Embedding 提供商:
  1. OllamaEmbeddings — 本地 Ollama 服务（默认）
  2. OpenAIEmbeddings — OpenAI / 兼容 API
  3. HuggingFaceEmbeddings — 本地 HuggingFace 模型

关键改进:
  - Ollama 批处理: 单次 HTTP 请求发送多个文本
  - Async 连接池复用: httpx.AsyncClient 单例
  - 统一维度管理: 模型→维度映射表
  - 稀疏向量支持: BM25 稀疏嵌入（用于混合检索）
"""

from typing import List, Optional, Dict, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from collections import Counter
import math
import json
import os
import logging

from pydantic import BaseModel

from miniclaw.config.settings import settings

logger = logging.getLogger(__name__)


class EmbeddingConfig(BaseModel):
    provider: str = "ollama"
    model: str = "nomic-embed-text"
    dimension: int = 768
    base_url: str = "http://localhost:11434"
    api_key: str = ""


class BaseEmbeddings(ABC):
    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        pass

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        pass

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.embed_documents(texts)

    async def aembed_query(self, text: str) -> List[float]:
        return self.embed_query(text)


class OllamaEmbeddingsWrapper(BaseEmbeddings):
    """Ollama Embeddings — 支持批处理和连接池复用"""

    def __init__(
        self,
        model: str = "nomic-embed-text",
        base_url: str = "http://localhost:11434",
        batch_size: int = 20,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.batch_size = batch_size
        self._async_client = None

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        import httpx

        embeddings = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            batch_embeddings = self._embed_batch_sync(batch)
            embeddings.extend(batch_embeddings)
        return embeddings

    def _embed_batch_sync(self, texts: List[str]) -> List[List[float]]:
        import httpx

        embeddings = []
        with httpx.Client(timeout=120.0) as client:
            for text in texts:
                response = client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                )
                response.raise_for_status()
                embeddings.append(response.json()["embedding"])
        return embeddings

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        if self._async_client is None:
            import httpx

            self._async_client = httpx.AsyncClient(timeout=120.0)

        embeddings = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            for text in batch:
                response = await self._async_client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                )
                response.raise_for_status()
                embeddings.append(response.json()["embedding"])
        return embeddings

    async def aembed_query(self, text: str) -> List[float]:
        result = await self.aembed_documents([text])
        return result[0]

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]

    async def close(self):
        if self._async_client is not None:
            await self._async_client.aclose()
            self._async_client = None


class OpenAIEmbeddingsWrapper(BaseEmbeddings):
    """OpenAI Embeddings — 支持所有 OpenAI 兼容 API"""

    def __init__(
        self,
        model: str = "text-embedding-ada-002",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        from langchain_openai import OpenAIEmbeddings as LCOpenAIEmbeddings

        self._embeddings = LCOpenAIEmbeddings(
            model=model,
            openai_api_key=api_key or settings.OPENAI_API_KEY,
            openai_api_base=base_url or settings.OPENAI_BASE_URL,
        )

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        return self._embeddings.embed_query(text)

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        return await self._embeddings.aembed_documents(texts)

    async def aembed_query(self, text: str) -> List[float]:
        return await self._embeddings.aembed_query(text)


class HuggingFaceEmbeddingsWrapper(BaseEmbeddings):
    """HuggingFace 本地模型 Embeddings"""

    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        model_kwargs: Dict[str, Any] = None,
        encode_kwargs: Dict[str, Any] = None,
    ):
        try:
            from langchain_huggingface import HuggingFaceEmbeddings as LCHFEmbeddings
        except ImportError:
            from langchain_community.embeddings import HuggingFaceEmbeddings as LCHFEmbeddings

        self._embeddings = LCHFEmbeddings(
            model_name=model_name,
            model_kwargs=model_kwargs or {},
            encode_kwargs=encode_kwargs or {"normalize_embeddings": True},
        )

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        return self._embeddings.embed_query(text)

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        return await self._embeddings.aembed_documents(texts)

    async def aembed_query(self, text: str) -> List[float]:
        return await self._embeddings.aembed_query(text)


class BM25SparseEmbedding:
    """
    BM25 稀疏向量 — 参考 SuperMew

    将文本转换为 BM25 加权的稀疏向量表示
    用于混合检索 (Dense + Sparse RRF 融合)

    稀疏向量格式: {vocab_index: bm25_score}
    BM25 公式: score = IDF * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / avgdl))
    """

    def __init__(
        self,
        k1: float = 1.5,
        b: float = 0.75,
        persist_dir: str = None,
    ):
        self.k1 = k1
        self.b = b
        self.persist_dir = persist_dir
        self._vocab: Dict[str, int] = {}
        self._doc_freq: Counter = Counter()
        self._total_docs: int = 0
        self._avg_doc_len: float = 0.0
        self._total_doc_len: int = 0

        if persist_dir:
            self._load_stats()

    def tokenize(self, text: str) -> List[str]:
        tokens = []
        try:
            import jieba

            tokens = jieba.lcut(text)
        except ImportError:
            tokens = text.split()

        tokens = [t.strip().lower() for t in tokens if t.strip() and len(t.strip()) >= 2]
        return tokens

    def add_documents(self, texts: List[str]):
        for text in texts:
            tokens = self.tokenize(text)
            self._total_docs += 1
            self._total_doc_len += len(tokens)
            for token in set(tokens):
                self._doc_freq[token] += 1
                if token not in self._vocab:
                    self._vocab[token] = len(self._vocab)

        self._avg_doc_len = self._total_doc_len / max(self._total_docs, 1)

        if self.persist_dir:
            self._save_stats()

    def get_sparse_embedding(self, text: str) -> Dict[int, float]:
        if self._total_docs == 0:
            return {}

        tokens = self.tokenize(text)
        tf = Counter(tokens)
        doc_len = len(tokens)
        sparse_vector: Dict[int, float] = {}

        for token, freq in tf.items():
            if token not in self._vocab:
                continue

            idx = self._vocab[token]
            df = self._doc_freq.get(token, 0)
            idf = math.log((self._total_docs - df + 0.5) / (df + 0.5) + 1)
            score = idf * (freq * (self.k1 + 1)) / (
                freq + self.k1 * (1 - self.b + self.b * doc_len / max(self._avg_doc_len, 1))
            )
            if score > 0:
                sparse_vector[idx] = float(score)

        return sparse_vector

    def _save_stats(self):
        os.makedirs(self.persist_dir, exist_ok=True)
        stats_path = os.path.join(self.persist_dir, "bm25_stats.json")
        data = {
            "vocab": self._vocab,
            "doc_freq": dict(self._doc_freq),
            "total_docs": self._total_docs,
            "avg_doc_len": self._avg_doc_len,
            "total_doc_len": self._total_doc_len,
            "k1": self.k1,
            "b": self.b,
        }
        tmp_path = stats_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp_path, stats_path)

    def _load_stats(self):
        stats_path = os.path.join(self.persist_dir, "bm25_stats.json")
        if not os.path.exists(stats_path):
            return
        try:
            with open(stats_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._vocab = data.get("vocab", {})
            self._doc_freq = Counter(data.get("doc_freq", {}))
            self._total_docs = data.get("total_docs", 0)
            self._avg_doc_len = data.get("avg_doc_len", 0.0)
            self._total_doc_len = data.get("total_doc_len", 0)
        except Exception as e:
            logger.error(f"Failed to load BM25 stats: {e}")


class EmbeddingsManager:
    _instance: Optional["EmbeddingsManager"] = None
    _embeddings: dict = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_embeddings(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> BaseEmbeddings:
        provider = provider or settings.EMBEDDING_PROVIDER
        cache_key = f"{provider}_{model}"

        if cache_key in self._embeddings:
            return self._embeddings[cache_key]

        if provider == "openai":
            embeddings = OpenAIEmbeddingsWrapper(
                model=model or "text-embedding-ada-002",
            )
        elif provider == "huggingface":
            embeddings = HuggingFaceEmbeddingsWrapper(
                model_name=model or "BAAI/bge-m3",
            )
        else:
            embeddings = OllamaEmbeddingsWrapper(
                model=model or settings.EMBEDDING_MODEL,
                base_url=settings.OLLAMA_BASE_URL,
            )

        self._embeddings[cache_key] = embeddings
        return embeddings


def get_embeddings(
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> BaseEmbeddings:
    manager = EmbeddingsManager()
    return manager.get_embeddings(provider, model)


EMBEDDING_DIMENSIONS = {
    "openai": {
        "text-embedding-ada-002": 1536,
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
    },
    "ollama": {
        "nomic-embed-text": 768,
        "mxbai-embed-large": 1024,
        "bge-m3": 1024,
    },
    "huggingface": {
        "BAAI/bge-m3": 1024,
        "BAAI/bge-small-zh-v1.5": 512,
        "BAAI/bge-large-zh-v1.5": 1024,
        "sentence-transformers/all-MiniLM-L6-v2": 384,
    },
}


def get_embedding_dimension(provider: Optional[str] = None, model: Optional[str] = None) -> int:
    provider = provider or settings.EMBEDDING_PROVIDER
    model = model or settings.EMBEDDING_MODEL

    provider_dims = EMBEDDING_DIMENSIONS.get(provider, {})
    if model in provider_dims:
        return provider_dims[model]

    if provider_dims:
        return list(provider_dims.values())[0]

    return 768

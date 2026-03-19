"""
MiniClaw Embeddings Module
Supports multiple embedding providers: OpenAI, Ollama, HuggingFace
"""

from typing import List, Optional
from abc import ABC, abstractmethod

from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings
from pydantic import BaseModel

from miniclaw.config.settings import settings


class EmbeddingConfig(BaseModel):
    provider: str = "openai"
    model: str = "text-embedding-ada-002"
    dimension: int = 1536


class BaseEmbeddings(ABC):
    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        pass
    
    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        pass


class OpenAIEmbeddingsWrapper(BaseEmbeddings):
    def __init__(
        self,
        model: str = "text-embedding-ada-002",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self._embeddings = OpenAIEmbeddings(
            model=model,
            openai_api_key=api_key or settings.OPENAI_API_KEY,
            openai_api_base=base_url or settings.OPENAI_BASE_URL,
        )
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._embeddings.embed_documents(texts)
    
    def embed_query(self, text: str) -> List[float]:
        return self._embeddings.embed_query(text)


class OllamaEmbeddingsWrapper(BaseEmbeddings):
    def __init__(
        self,
        model: str = "nomic-embed-text",
        base_url: str = "http://localhost:11434",
    ):
        self.model = model
        self.base_url = base_url
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        import httpx
        
        embeddings = []
        for text in texts:
            response = httpx.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
                timeout=30.0,
            )
            response.raise_for_status()
            embeddings.append(response.json()["embedding"])
        
        return embeddings
    
    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]


class HuggingFaceEmbeddingsWrapper(BaseEmbeddings):
    def __init__(self, model: str = "sentence-transformers/all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(model)
        except ImportError:
            raise ImportError("Please install sentence-transformers: pip install sentence-transformers")
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._model.encode(texts).tolist()
    
    def embed_query(self, text: str) -> List[float]:
        return self._model.encode([text]).tolist()[0]


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
        provider = provider or settings.LLM_PROVIDER
        cache_key = f"{provider}_{model}"
        
        if cache_key in self._embeddings:
            return self._embeddings[cache_key]
        
        if provider == "openai":
            embeddings = OpenAIEmbeddingsWrapper(
                model=model or "text-embedding-ada-002",
            )
        elif provider == "ollama":
            embeddings = OllamaEmbeddingsWrapper(
                model=model or "nomic-embed-text",
                base_url=settings.OLLAMA_BASE_URL,
            )
        elif provider == "huggingface":
            embeddings = HuggingFaceEmbeddingsWrapper(
                model=model or "sentence-transformers/all-MiniLM-L6-v2",
            )
        else:
            embeddings = OllamaEmbeddingsWrapper()
        
        self._embeddings[cache_key] = embeddings
        return embeddings


def get_embeddings(
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> BaseEmbeddings:
    manager = EmbeddingsManager()
    return manager.get_embeddings(provider, model)


def get_embedding_dimension(provider: Optional[str] = None) -> int:
    dimensions = {
        "openai": {"text-embedding-ada-002": 1536, "text-embedding-3-small": 1536, "text-embedding-3-large": 3072},
        "ollama": {"nomic-embed-text": 768, "mxbai-embed-large": 1024},
        "huggingface": {"sentence-transformers/all-MiniLM-L6-v2": 384},
    }
    
    provider = provider or settings.LLM_PROVIDER
    provider_dims = dimensions.get(provider, {})
    
    return list(provider_dims.values())[0] if provider_dims else 768

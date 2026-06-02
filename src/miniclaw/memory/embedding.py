import hashlib
from typing import List, Optional

from miniclaw.config.settings import settings


class EmbeddingProvider:
    def __init__(self, model: str = "", dims: int = 0):
        self.model = model
        self.dims = dims

    async def embed_query(self, text: str) -> List[float]:
        raise NotImplementedError

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [await self.embed_query(t) for t in texts]

    async def close(self):
        pass


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "text-embedding-3-small",
        dims: int = 1536,
    ):
        super().__init__(model=model, dims=dims)
        self._api_key = api_key
        self._base_url = base_url
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self._api_key or settings.effective_api_key,
                base_url=self._base_url or settings.effective_base_url,
            )
        return self._client

    async def embed_query(self, text: str) -> List[float]:
        client = self._get_client()
        response = client.embeddings.create(input=text, model=self.model)
        return response.data[0].embedding

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        client = self._get_client()
        batch_size = 100
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = client.embeddings.create(input=batch, model=self.model)
            all_embeddings.extend([d.embedding for d in response.data])
        return all_embeddings


class LocalEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", dims: int = 384):
        super().__init__(model=model_name, dims=dims)
        self._model = None
        self._model_name = model_name

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self._model_name)
                self.dims = self._model.get_sentence_embedding_dimension() or self.dims
            except ImportError:
                raise RuntimeError(
                    "sentence-transformers not installed. "
                    "Install with: pip install sentence-transformers"
                )
        return self._model

    async def embed_query(self, text: str) -> List[float]:
        model = self._get_model()
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        model = self._get_model()
        embeddings = model.encode(texts, normalize_embeddings=True, batch_size=32)
        return embeddings.tolist()


def create_embedding_provider(
    provider: str = "auto",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Optional[EmbeddingProvider]:
    if provider == "openai":
        return OpenAIEmbeddingProvider(
            api_key=api_key,
            base_url=base_url,
            model=model or "text-embedding-3-small",
        )
    elif provider == "local":
        return LocalEmbeddingProvider(model_name=model or "all-MiniLM-L6-v2")
    elif provider == "auto":
        effective_key = api_key or settings.effective_api_key
        if effective_key:
            return OpenAIEmbeddingProvider(
                api_key=effective_key,
                base_url=base_url or settings.effective_base_url,
                model=model or "text-embedding-3-small",
            )
        try:
            import sentence_transformers
            return LocalEmbeddingProvider(model_name=model or "all-MiniLM-L6-v2")
        except ImportError:
            return None
    elif provider == "none":
        return None
    return None


def compute_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

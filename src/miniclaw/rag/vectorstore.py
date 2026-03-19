"""
MiniClaw Milvus Vector Store
Provides vector storage and retrieval using Milvus
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import json

from miniclaw.config.settings import settings
from miniclaw.rag.embeddings import get_embeddings, get_embedding_dimension


@dataclass
class Document:
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    id: Optional[str] = None


class MilvusVectorStore:
    def __init__(
        self,
        collection_name: str = "miniclaw",
        host: str = "localhost",
        port: int = 19530,
        embedding_provider: str = None,
    ):
        self.collection_name = collection_name
        self.host = host or settings.MILVUS_HOST if hasattr(settings, 'MILVUS_HOST') else "localhost"
        self.port = port or settings.MILVUS_PORT if hasattr(settings, 'MILVUS_PORT') else 19530
        self.embedding_provider = embedding_provider
        self._collection = None
        self._client = None
        self._embeddings = None
    
    @property
    def embeddings(self):
        if self._embeddings is None:
            self._embeddings = get_embeddings(self.embedding_provider)
        return self._embeddings
    
    def connect(self) -> bool:
        try:
            from pymilvus import MilvusClient
            
            self._client = MilvusClient(
                uri=f"http://{self.host}:{self.port}"
            )
            return True
        except ImportError:
            return False
        except Exception:
            return False
    
    def create_collection(self, dimension: int = None) -> bool:
        if self._client is None:
            if not self.connect():
                return False
        
        dimension = dimension or get_embedding_dimension(self.embedding_provider)
        
        try:
            if self._client.has_collection(self.collection_name):
                self._collection = self._client.get_collection(self.collection_name)
            else:
                self._client.create_collection(
                    collection_name=self.collection_name,
                    dimension=dimension,
                    auto_id=True,
                )
                self._collection = self._client.get_collection(self.collection_name)
            return True
        except Exception:
            return False
    
    def add_documents(
        self,
        documents: List[Document],
        batch_size: int = 100,
    ) -> int:
        if self._client is None:
            if not self.create_collection():
                return 0
        
        added_count = 0
        texts = [doc.content for doc in documents]
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_docs = documents[i:i + batch_size]
            
            try:
                embeddings = self.embeddings.embed_documents(batch_texts)
                
                data = []
                for j, (doc, emb) in enumerate(zip(batch_docs, embeddings)):
                    data.append({
                        "vector": emb,
                        "content": doc.content,
                        "metadata": json.dumps(doc.metadata),
                        "created_at": datetime.now().isoformat(),
                    })
                
                self._client.insert(
                    collection_name=self.collection_name,
                    data=data,
                )
                added_count += len(data)
            except Exception:
                continue
        
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
        filter_expr: Optional[str] = None,
    ) -> List[Document]:
        if self._client is None:
            if not self.create_collection():
                return []
        
        try:
            query_embedding = self.embeddings.embed_query(query)
            
            search_params = {
                "collection_name": self.collection_name,
                "data": [query_embedding],
                "limit": k,
                "output_fields": ["content", "metadata", "created_at"],
            }
            
            if filter_expr:
                search_params["filter"] = filter_expr
            
            results = self._client.search(**search_params)
            
            documents = []
            for hits in results:
                for hit in hits:
                    entity = hit.get("entity", {})
                    content = entity.get("content", "")
                    metadata_str = entity.get("metadata", "{}")
                    
                    try:
                        metadata = json.loads(metadata_str)
                    except json.JSONDecodeError:
                        metadata = {}
                    
                    documents.append(Document(
                        content=content,
                        metadata=metadata,
                        id=str(hit.get("id", "")),
                    ))
            
            return documents
        except Exception:
            return []
    
    def similarity_search_with_score(
        self,
        query: str,
        k: int = 4,
    ) -> List[tuple]:
        if self._client is None:
            if not self.create_collection():
                return []
        
        try:
            query_embedding = self.embeddings.embed_query(query)
            
            results = self._client.search(
                collection_name=self.collection_name,
                data=[query_embedding],
                limit=k,
                output_fields=["content", "metadata"],
            )
            
            documents_with_scores = []
            for hits in results:
                for hit in hits:
                    entity = hit.get("entity", {})
                    content = entity.get("content", "")
                    metadata_str = entity.get("metadata", "{}")
                    
                    try:
                        metadata = json.loads(metadata_str)
                    except json.JSONDecodeError:
                        metadata = {}
                    
                    score = hit.get("distance", 0)
                    doc = Document(content=content, metadata=metadata)
                    documents_with_scores.append((doc, score))
            
            return documents_with_scores
        except Exception:
            return []
    
    def delete_collection(self) -> bool:
        if self._client is None:
            return False
        
        try:
            self._client.drop_collection(self.collection_name)
            return True
        except Exception:
            return False
    
    def get_collection_stats(self) -> Dict[str, Any]:
        if self._client is None:
            return {"error": "Not connected"}
        
        try:
            stats = self._client.get_collection_stats(self.collection_name)
            return stats
        except Exception as e:
            return {"error": str(e)}


class InMemoryVectorStore:
    def __init__(self, embedding_provider: str = None):
        self.embedding_provider = embedding_provider
        self._documents: List[Document] = []
        self._embeddings = None
    
    @property
    def embeddings(self):
        if self._embeddings is None:
            self._embeddings = get_embeddings(self.embedding_provider)
        return self._embeddings
    
    def add_documents(self, documents: List[Document]) -> int:
        texts = [doc.content for doc in documents]
        embeddings = self.embeddings.embed_documents(texts)
        
        for doc, emb in zip(documents, embeddings):
            doc.embedding = emb
            self._documents.append(doc)
        
        return len(documents)
    
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
    
    def similarity_search(self, query: str, k: int = 4) -> List[Document]:
        import numpy as np
        
        if not self._documents:
            return []
        
        query_embedding = np.array(self.embeddings.embed_query(query))
        
        scores = []
        for doc in self._documents:
            if doc.embedding:
                doc_embedding = np.array(doc.embedding)
                score = np.dot(query_embedding, doc_embedding) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(doc_embedding)
                )
                scores.append((doc, score))
        
        scores.sort(key=lambda x: x[1], reverse=True)
        
        return [doc for doc, _ in scores[:k]]


def get_vectorstore(
    use_milvus: bool = True,
    collection_name: str = "miniclaw",
    embedding_provider: str = None,
) -> Any:
    if use_milvus:
        try:
            store = MilvusVectorStore(
                collection_name=collection_name,
                embedding_provider=embedding_provider,
            )
            if store.connect():
                store.create_collection()
                return store
        except Exception:
            pass
    
    return InMemoryVectorStore(embedding_provider=embedding_provider)

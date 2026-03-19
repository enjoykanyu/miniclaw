"""
MiniClaw RAG (Retrieval Augmented Generation) Module
Provides vector search, PDF knowledge base, and memory retrieval
"""

from miniclaw.rag.embeddings import EmbeddingsManager, get_embeddings
from miniclaw.rag.vectorstore import MilvusVectorStore
from miniclaw.rag.pdf_loader import PDFLoader
from miniclaw.rag.memory_store import MemoryStore
from miniclaw.rag.news_enhancer import NewsEnhancer
from miniclaw.rag.retriever import RAGRetriever

__all__ = [
    "EmbeddingsManager",
    "get_embeddings",
    "MilvusVectorStore",
    "PDFLoader",
    "MemoryStore",
    "NewsEnhancer",
    "RAGRetriever",
]

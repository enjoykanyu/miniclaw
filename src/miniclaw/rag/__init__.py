"""
MiniClaw RAG (Retrieval Augmented Generation) Module
Provides vector search, document indexing, and knowledge base retrieval
"""

from miniclaw.rag.types import Document, ChunkNode, ChunkLevel, RetrievalResult
from miniclaw.rag.embeddings import (
    EmbeddingsManager, get_embeddings, get_embedding_dimension,
    BM25SparseEmbedding, BaseEmbeddings,
)
from miniclaw.rag.vectorstore import FAISSVectorStore, MilvusVectorStore, get_vectorstore
from miniclaw.rag.document_loader import DocumentLoader, FileTypeRouter
from miniclaw.rag.chunking import (
    RecursiveChunker, TokenChunker, MarkdownChunker,
    ThreeLevelChunker, AutoMerger, ChunkingStrategy,
)
from miniclaw.rag.retriever import (
    HybridRetriever, SearchMode, FusionMethod,
    rrf_fusion, weighted_sum_fusion,
)
from miniclaw.rag.service import RAGService, KnowledgeBase, get_rag_service
from miniclaw.rag.rag_node import (
    rag_detect_node, rag_retrieve_node, rag_generate_node,
    detect_rag_need, should_retrieve,
)

__all__ = [
    "Document",
    "ChunkNode",
    "ChunkLevel",
    "RetrievalResult",
    "EmbeddingsManager",
    "get_embeddings",
    "get_embedding_dimension",
    "BM25SparseEmbedding",
    "BaseEmbeddings",
    "FAISSVectorStore",
    "MilvusVectorStore",
    "get_vectorstore",
    "DocumentLoader",
    "FileTypeRouter",
    "RecursiveChunker",
    "TokenChunker",
    "MarkdownChunker",
    "ThreeLevelChunker",
    "AutoMerger",
    "ChunkingStrategy",
    "HybridRetriever",
    "SearchMode",
    "FusionMethod",
    "rrf_fusion",
    "weighted_sum_fusion",
    "RAGService",
    "KnowledgeBase",
    "get_rag_service",
    "rag_detect_node",
    "rag_retrieve_node",
    "rag_generate_node",
    "detect_rag_need",
    "should_retrieve",
]

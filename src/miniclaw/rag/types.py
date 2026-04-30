from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum


class ChunkLevel(int, Enum):
    LEVEL_1 = 1
    LEVEL_2 = 2
    LEVEL_3 = 3


@dataclass
class Document:
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    id: Optional[str] = None

    def to_langchain(self):
        from langchain_core.documents import Document as LCDocument
        return LCDocument(page_content=self.content, metadata=self.metadata)

    @classmethod
    def from_langchain(cls, lc_doc):
        return cls(content=lc_doc.page_content, metadata=dict(lc_doc.metadata))


@dataclass
class ChunkNode:
    content: str
    chunk_id: str
    chunk_level: ChunkLevel = ChunkLevel.LEVEL_3
    parent_chunk_id: str = ""
    root_chunk_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None

    def to_document(self) -> Document:
        meta = {
            **self.metadata,
            "chunk_id": self.chunk_id,
            "chunk_level": self.chunk_level.value,
            "parent_chunk_id": self.parent_chunk_id,
            "root_chunk_id": self.root_chunk_id,
        }
        return Document(
            content=self.content,
            metadata=meta,
            embedding=self.embedding,
            id=self.chunk_id,
        )


@dataclass
class RetrievalResult:
    content: str
    source: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)

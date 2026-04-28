"""
MiniClaw PDF Loader
Handles PDF document parsing and knowledge base creation
"""

from typing import List, Optional, Dict, Any
from pathlib import Path
from dataclasses import dataclass, field
import re

from miniclaw.config.settings import settings
from miniclaw.rag.types import Document
from miniclaw.rag.vectorstore import get_vectorstore


@dataclass
class PDFChunk:
    content: str
    page_number: int
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class PDFLoader:
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def load_pdf(self, file_path: str) -> List[PDFChunk]:
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")
        
        if path.suffix.lower() != ".pdf":
            raise ValueError(f"File is not a PDF: {file_path}")
        
        chunks = []
        
        try:
            import pypdf
            
            with open(path, "rb") as f:
                reader = pypdf.PdfReader(f)
                
                for page_num, page in enumerate(reader.pages, 1):
                    text = page.extract_text()
                    
                    if text and text.strip():
                        page_chunks = self._split_text(
                            text,
                            page_num,
                            path.name,
                        )
                        chunks.extend(page_chunks)
        except ImportError:
            try:
                import pdfplumber
                
                with pdfplumber.open(path) as pdf:
                    for page_num, page in enumerate(pdf.pages, 1):
                        text = page.extract_text()
                        
                        if text and text.strip():
                            page_chunks = self._split_text(
                                text,
                                page_num,
                                path.name,
                            )
                            chunks.extend(page_chunks)
            except ImportError:
                raise ImportError(
                    "Please install pypdf or pdfplumber: "
                    "pip install pypdf or pip install pdfplumber"
                )
        
        return chunks
    
    def _split_text(
        self,
        text: str,
        page_number: int,
        source: str,
    ) -> List[PDFChunk]:
        text = self._clean_text(text)
        
        if len(text) <= self.chunk_size:
            return [PDFChunk(
                content=text,
                page_number=page_number,
                source=source,
            )]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            
            if end < len(text):
                last_period = text.rfind("。", start, end)
                last_newline = text.rfind("\n", start, end)
                last_space = text.rfind(" ", start, end)
                
                split_point = max(last_period, last_newline, last_space)
                
                if split_point > start:
                    end = split_point + 1
            
            chunk_text = text[start:end].strip()
            
            if chunk_text:
                chunks.append(PDFChunk(
                    content=chunk_text,
                    page_number=page_number,
                    source=source,
                    metadata={
                        "start_char": start,
                        "end_char": end,
                    },
                ))
            
            start = end - self.chunk_overlap
            
            if start < 0:
                start = 0
        
        return chunks
    
    def _clean_text(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)
        return text.strip()
    
    def load_directory(
        self,
        directory: str,
        recursive: bool = True,
    ) -> List[PDFChunk]:
        dir_path = Path(directory)
        
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        all_chunks = []
        
        pattern = "**/*.pdf" if recursive else "*.pdf"
        
        for pdf_file in dir_path.glob(pattern):
            try:
                chunks = self.load_pdf(str(pdf_file))
                all_chunks.extend(chunks)
            except Exception:
                continue
        
        return all_chunks


class PDFKnowledgeBase:
    def __init__(
        self,
        knowledge_dir: str = None,
        collection_name: str = "pdf_knowledge",
    ):
        self.knowledge_dir = knowledge_dir or settings.KNOWLEDGE_DIR
        self.collection_name = collection_name
        self._loader = PDFLoader()
        self._vectorstore = None
    
    @property
    def vectorstore(self):
        if self._vectorstore is None:
            self._vectorstore = get_vectorstore(collection_name=self.collection_name)
        return self._vectorstore
    
    def add_pdf(self, file_path: str) -> int:
        chunks = self._loader.load_pdf(file_path)
        
        documents = [
            Document(
                content=chunk.content,
                metadata={
                    "page": chunk.page_number,
                    "source": chunk.source,
                    **chunk.metadata,
                },
            )
            for chunk in chunks
        ]
        
        return self.vectorstore.add_documents(documents)
    
    def add_directory(self, directory: str = None) -> int:
        directory = directory or self.knowledge_dir
        chunks = self._loader.load_directory(directory)
        
        documents = [
            Document(
                content=chunk.content,
                metadata={
                    "page": chunk.page_number,
                    "source": chunk.source,
                    **chunk.metadata,
                },
            )
            for chunk in chunks
        ]
        
        return self.vectorstore.add_documents(documents)
    
    def query(
        self,
        question: str,
        k: int = 4,
    ) -> List[Dict[str, Any]]:
        results = self.vectorstore.similarity_search(question, k=k)
        
        return [
            {
                "content": doc.content,
                "source": doc.metadata.get("source", "Unknown"),
                "page": doc.metadata.get("page", 0),
            }
            for doc in results
        ]
    
    def query_with_context(
        self,
        question: str,
        k: int = 4,
    ) -> str:
        results = self.query(question, k)
        
        if not results:
            return "未找到相关内容"
        
        context_parts = []
        for i, result in enumerate(results, 1):
            context_parts.append(
                f"[文档{i}] 来源: {result['source']} 第{result['page']}页\n"
                f"{result['content']}\n"
            )
        
        return "\n".join(context_parts)

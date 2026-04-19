# src/miniclaw/rag/chunking.py

from typing import List, Dict, Any, Optional
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    TokenTextSplitter,
    MarkdownHeaderTextSplitter,
)
from langchain_core.documents import Document

class ChunkingStrategy:
    """分块策略"""
    
    @staticmethod
    def recursive_chunking(
        text: str,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        separators: List[str] = None,
    ) -> List[Document]:
        """
        递归字符分块
        
        优点：保持语义完整性
        适用：通用文本
        """
        separators = separators or ["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""]
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators,
        )
        
        chunks = splitter.split_text(text)
        return [Document(page_content=chunk, metadata={"chunk_index": i}) 
                for i, chunk in enumerate(chunks)]
    
    @staticmethod
    def token_chunking(
        text: str,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        encoding_name: str = "cl100k_base",
    ) -> List[Document]:
        """
        Token 分块
        
        优点：精确控制 Token 数量
        适用：LLM 上下文控制
        """
        splitter = TokenTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            encoding_name=encoding_name,
        )
        
        chunks = splitter.split_text(text)
        return [Document(page_content=chunk, metadata={"chunk_index": i}) 
                for i, chunk in enumerate(chunks)]
    
    @staticmethod
    def markdown_chunking(text: str) -> List[Document]:
        """
        Markdown 结构分块
        
        优点：保持文档结构
        适用：Markdown 文档
        """
        headers_to_split_on = [
            ("#", "header1"),
            ("##", "header2"),
            ("###", "header3"),
        ]
        
        splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=headers_to_split_on,
        )
        
        return splitter.split_text(text)
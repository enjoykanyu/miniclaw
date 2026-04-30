"""
MiniClaw Document Loader
Handles file parsing for PDF, TXT, MD, and code files
"""

from typing import List, Optional, Dict, Any
from pathlib import Path
from dataclasses import dataclass, field
import re

from miniclaw.rag.types import Document


@dataclass
class FileClassification:
    parser_files: List[str]
    text_files: List[str]
    unsupported: List[str]


class FileTypeRouter:
    PARSER_EXTENSIONS = {".pdf"}
    TEXT_EXTENSIONS = {
        ".txt", ".text", ".log", ".md", ".markdown", ".rst",
        ".json", ".yaml", ".yml", ".toml", ".csv", ".tsv",
        ".py", ".js", ".ts", ".jsx", ".tsx", ".java",
        ".c", ".cpp", ".h", ".hpp", ".go", ".rs", ".rb",
        ".html", ".htm", ".xml", ".css", ".sh", ".bash",
        ".sql", ".tex", ".latex",
    }

    @classmethod
    def classify_files(cls, file_paths: List[str]) -> FileClassification:
        parser_files = []
        text_files = []
        unsupported = []

        for path in file_paths:
            ext = Path(path).suffix.lower()
            if ext in cls.PARSER_EXTENSIONS:
                parser_files.append(path)
            elif ext in cls.TEXT_EXTENSIONS:
                text_files.append(path)
            else:
                unsupported.append(path)

        return FileClassification(
            parser_files=parser_files,
            text_files=text_files,
            unsupported=unsupported,
        )

    @classmethod
    def get_supported_extensions(cls) -> set:
        return cls.PARSER_EXTENSIONS | cls.TEXT_EXTENSIONS


class DocumentLoader:
    """统一文档加载器，参考 DeepTutor 的 FileTypeRouter 设计"""

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def load_files(self, file_paths: List[str]) -> List[Document]:
        classification = FileTypeRouter.classify_files(file_paths)
        documents = []

        for pdf_path in classification.parser_files:
            docs = self._load_pdf(pdf_path)
            documents.extend(docs)

        for text_path in classification.text_files:
            docs = self._load_text(text_path)
            documents.extend(docs)

        return documents

    def load_directory(self, directory: str, recursive: bool = True) -> List[Document]:
        dir_path = Path(directory)
        if not dir_path.exists():
            return []

        extensions = FileTypeRouter.get_supported_extensions()
        file_paths = []
        pattern = "**/*" if recursive else "*"
        for f in dir_path.glob(pattern):
            if f.is_file() and f.suffix.lower() in extensions:
                file_paths.append(str(f))

        return self.load_files(file_paths)

    def _load_pdf(self, file_path: str) -> List[Document]:
        path = Path(file_path)
        if not path.exists():
            return []

        text = ""
        try:
            import fitz
            doc = fitz.open(path)
            for page in doc:
                text += page.get_text() + "\n\n"
            doc.close()
        except ImportError:
            try:
                import pypdf
                with open(path, "rb") as f:
                    reader = pypdf.PdfReader(f)
                    for page in reader.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n\n"
            except ImportError:
                return []

        if not text.strip():
            return []

        return self._split_to_documents(
            text,
            metadata={"source": path.name, "file_path": str(path), "type": "pdf"},
        )

    def _load_text(self, file_path: str) -> List[Document]:
        path = Path(file_path)
        if not path.exists():
            return []

        encodings = ["utf-8", "utf-8-sig", "gbk", "gb2312", "latin-1"]
        text = ""
        for encoding in encodings:
            try:
                text = path.read_text(encoding=encoding)
                break
            except (UnicodeDecodeError, IOError):
                continue

        if not text.strip():
            return []

        return self._split_to_documents(
            text,
            metadata={"source": path.name, "file_path": str(path), "type": "text"},
        )

    def _split_to_documents(
        self,
        text: str,
        metadata: Dict[str, Any],
    ) -> List[Document]:
        text = self._clean_text(text)
        chunks = self._chunk_text(text)

        documents = []
        for i, chunk in enumerate(chunks):
            doc_meta = {**metadata, "chunk_index": i}
            documents.append(Document(content=chunk, metadata=doc_meta))

        return documents

    def _chunk_text(self, text: str) -> List[str]:
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0
        separators = ["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""]

        while start < len(text):
            end = start + self.chunk_size

            if end < len(text):
                best_split = end
                for sep in separators:
                    pos = text.rfind(sep, start, end)
                    if pos > start:
                        best_split = pos + len(sep)
                        break
                end = best_split

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - self.chunk_overlap
            if start <= 0 and end >= len(text):
                break
            if start < 0:
                start = 0

        return chunks

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)
        return text.strip()

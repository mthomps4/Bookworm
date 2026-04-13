"""Pydantic models for configuration, extraction, chunking, and manifest."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


# --- Configuration ---


class EmbeddingProvider(str, Enum):
    LOCAL = "local"
    OPENAI = "openai"


class LibraryConfig(BaseModel):
    books_dir: Path = Path("./books/inbox")
    manifest_path: Path = Path("./books/.manifest.json")
    db_path: Path = Path("./db")
    allowed_formats: list[str] = Field(default_factory=lambda: ["pdf", "epub", "mobi", "md", "txt", "html"])


class ChunkingConfig(BaseModel):
    target_tokens: int = 600
    max_tokens: int = 800
    overlap_tokens: int = 75
    respect_paragraphs: bool = True
    respect_sections: bool = True


class EmbeddingsConfig(BaseModel):
    provider: EmbeddingProvider = EmbeddingProvider.LOCAL
    model: str = "all-MiniLM-L6-v2"
    batch_size: int = 64


class SearchConfig(BaseModel):
    default_top_k: int = 5
    max_top_k: int = 20
    relevance_threshold: float = 0.3


class ServerConfig(BaseModel):
    name: str = "bookworm"
    transport: str = "stdio"


class AppConfig(BaseModel):
    library: LibraryConfig = LibraryConfig()
    chunking: ChunkingConfig = ChunkingConfig()
    embeddings: EmbeddingsConfig = EmbeddingsConfig()
    search: SearchConfig = SearchConfig()
    server: ServerConfig = ServerConfig()


# --- Text Extraction ---


class BookFormat(str, Enum):
    PDF = "pdf"
    EPUB = "epub"
    MOBI = "mobi"
    MARKDOWN = "md"
    TXT = "txt"
    HTML = "html"


class Section(BaseModel):
    title: str
    text: str
    page_start: int | None = None
    page_end: int | None = None


class ExtractedBook(BaseModel):
    title: str
    author: str
    format: BookFormat
    sections: list[Section]


# --- Chunking ---


class Chunk(BaseModel):
    text: str
    book_title: str
    author: str
    section_title: str
    chunk_index: int
    page_number: int | None = None
    token_count: int = 0


# --- Manifest ---


class ManifestEntry(BaseModel):
    file_hash: str
    title: str
    author: str
    chunk_count: int
    version_tag: str | None = None
    ingested_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    file_size_bytes: int = 0
    ocr: bool = False
    source_dir: str = ""


class Manifest(BaseModel):
    books: dict[str, ManifestEntry] = Field(default_factory=dict)
    last_full_ingest: str | None = None
    db_path: str = "./db"
    embedding_model: str = "all-MiniLM-L6-v2"


# --- Search Results ---


class SearchResult(BaseModel):
    text: str
    book_title: str
    author: str
    section: str
    page: int | None = None
    relevance_score: float

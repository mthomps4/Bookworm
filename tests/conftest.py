"""Shared fixtures for the test suite."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from library_mcp.models import (
    AppConfig,
    Chunk,
    ChunkingConfig,
    EmbeddingsConfig,
    ExtractedBook,
    BookFormat,
    LibraryConfig,
    Manifest,
    ManifestEntry,
    SearchConfig,
    Section,
)


@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a clean temp directory."""
    return tmp_path


@pytest.fixture
def sample_sections():
    """A few realistic sections for testing."""
    return [
        Section(
            title="Chapter 1: Introduction",
            text=(
                "Software design is the art of managing complexity. "
                "Good design makes systems easier to understand, modify, and extend. "
                "This book explores the principles that separate well-designed software "
                "from the tangled messes that too many projects become.\n\n"
                "The first principle is simplicity. Every line of code has a cost — "
                "not just the cost to write it, but the cost to read, understand, "
                "test, and maintain it over the lifetime of the project."
            ),
            page_start=1,
            page_end=5,
        ),
        Section(
            title="Chapter 2: Naming",
            text=(
                "Names matter. A good name communicates intent and makes code self-documenting. "
                "Variable names should reveal their purpose. Function names should describe "
                "what the function does, not how it does it.\n\n"
                "Avoid abbreviations unless they are universally understood. "
                "Prefer 'customer_address' over 'cust_addr'. Prefer 'calculate_total' "
                "over 'calc_tot'. The few extra characters are a tiny cost compared to "
                "the clarity they provide.\n\n"
                "Class names should be nouns. Method names should be verbs. "
                "Boolean variables should read as predicates: 'is_valid', 'has_permission'."
            ),
            page_start=6,
            page_end=15,
        ),
    ]


@pytest.fixture
def sample_book(sample_sections):
    """An ExtractedBook for testing."""
    return ExtractedBook(
        title="Clean Design",
        author="Test Author",
        format=BookFormat.PDF,
        sections=sample_sections,
    )


@pytest.fixture
def sample_chunks():
    """Pre-built chunks for DB testing."""
    return [
        Chunk(
            text="Software design is the art of managing complexity.",
            book_title="Clean Design",
            author="Test Author",
            section_title="Chapter 1: Introduction",
            chunk_index=0,
            page_number=1,
            token_count=9,
        ),
        Chunk(
            text="Names matter. A good name communicates intent.",
            book_title="Clean Design",
            author="Test Author",
            section_title="Chapter 2: Naming",
            chunk_index=1,
            page_number=6,
            token_count=9,
        ),
        Chunk(
            text="Class names should be nouns. Method names should be verbs.",
            book_title="Clean Design",
            author="Test Author",
            section_title="Chapter 2: Naming",
            chunk_index=2,
            page_number=10,
            token_count=11,
        ),
    ]


@pytest.fixture
def test_config(tmp_dir):
    """AppConfig pointing at temp directories."""
    books_dir = tmp_dir / "books"
    books_dir.mkdir()
    db_dir = tmp_dir / "db"
    manifest_path = tmp_dir / "manifest.json"

    return AppConfig(
        library=LibraryConfig(
            books_dir=books_dir,
            db_path=db_dir,
            manifest_path=manifest_path,
        ),
        chunking=ChunkingConfig(target_tokens=100, max_tokens=200, overlap_tokens=20),
        embeddings=EmbeddingsConfig(provider="local", model="all-MiniLM-L6-v2"),
        search=SearchConfig(default_top_k=5, max_top_k=20, relevance_threshold=0.0),
    )


@pytest.fixture
def sample_manifest():
    """A manifest with one book already indexed."""
    return Manifest(
        books={
            "test-book.pdf": ManifestEntry(
                file_hash="sha256:abc123",
                title="Test Book",
                author="Author One",
                chunk_count=10,
                ingested_at="2025-01-01T00:00:00",
                file_size_bytes=1000,
            )
        },
        embedding_model="all-MiniLM-L6-v2",
    )

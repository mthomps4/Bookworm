"""End-to-end tests for search functionality."""

import pytest

from library_mcp.db import VectorDB
from library_mcp.embeddings import create_embedder
from library_mcp.models import Chunk, EmbeddingsConfig


@pytest.fixture
def search_db(tmp_path):
    """A DB pre-loaded with chunks using real embeddings."""
    config = EmbeddingsConfig(provider="local", model="all-MiniLM-L6-v2")
    embedder = create_embedder(config)
    db = VectorDB(tmp_path / "search_db")

    chunks = [
        Chunk(
            text="Error handling should be explicit. Never swallow exceptions silently. "
                 "Always log errors with enough context to diagnose the problem.",
            book_title="Clean Code",
            author="Robert Martin",
            section_title="Chapter 7: Error Handling",
            chunk_index=0,
            page_number=105,
            token_count=25,
        ),
        Chunk(
            text="Dependency injection decouples components by providing dependencies "
                 "from the outside rather than creating them internally. This makes "
                 "code more testable and flexible.",
            book_title="Clean Architecture",
            author="Robert Martin",
            section_title="Chapter 11: DIP",
            chunk_index=1,
            page_number=130,
            token_count=30,
        ),
        Chunk(
            text="Database indexes speed up read queries but slow down writes. "
                 "Choose indexes based on your actual query patterns, not theoretical ones.",
            book_title="Database Internals",
            author="Alex Petrov",
            section_title="Chapter 4: Indexes",
            chunk_index=2,
            page_number=78,
            token_count=25,
        ),
        Chunk(
            text="Recursion is a technique where a function calls itself. "
                 "Every recursive function needs a base case to prevent infinite loops.",
            book_title="SICP",
            author="Abelson & Sussman",
            section_title="Chapter 1: Procedures",
            chunk_index=3,
            page_number=20,
            token_count=20,
        ),
    ]

    texts = [c.text for c in chunks]
    embeddings = embedder.embed(texts)
    db.add_chunks(chunks, embeddings, file_hash="sha256:searchtest")

    return db, embedder


def test_search_returns_relevant_results(search_db):
    db, embedder = search_db
    query_emb = embedder.embed(["how to handle errors properly"])[0]
    results = db.search(query_emb, top_k=2)

    assert len(results) > 0
    # The error handling chunk should rank highly
    titles = [r.section for r in results]
    assert any("Error" in t for t in titles)


def test_search_book_filter(search_db):
    db, embedder = search_db
    query_emb = embedder.embed(["software design"])[0]
    results = db.search(query_emb, top_k=10, book_filter="Clean Code")

    assert all(r.book_title == "Clean Code" for r in results)


def test_search_returns_metadata(search_db):
    db, embedder = search_db
    query_emb = embedder.embed(["database performance"])[0]
    results = db.search(query_emb, top_k=1)

    assert len(results) == 1
    r = results[0]
    assert r.text is not None
    assert r.book_title is not None
    assert r.author is not None
    assert r.section is not None
    assert isinstance(r.relevance_score, float)


def test_search_relevance_ordering(search_db):
    db, embedder = search_db
    query_emb = embedder.embed(["dependency injection patterns"])[0]
    results = db.search(query_emb, top_k=4)

    # Results should be in descending relevance order
    scores = [r.relevance_score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_search_top_k_limits(search_db):
    db, embedder = search_db
    query_emb = embedder.embed(["programming"])[0]

    results_1 = db.search(query_emb, top_k=1)
    results_3 = db.search(query_emb, top_k=3)

    assert len(results_1) == 1
    assert len(results_3) == 3


def test_get_chapter_end_to_end(search_db):
    db, _ = search_db
    chapter = db.get_chapter("Clean Code", "Chapter 7: Error Handling")
    assert len(chapter) == 1
    assert "exceptions" in chapter[0]["text"]

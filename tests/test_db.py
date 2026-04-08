"""Tests for the ChromaDB wrapper."""

import pytest

from library_mcp.db import VectorDB
from library_mcp.models import Chunk


@pytest.fixture
def db(tmp_path):
    return VectorDB(tmp_path / "test_db")


@pytest.fixture
def fake_embeddings():
    """Simple deterministic embeddings for testing (384 dimensions to match MiniLM)."""
    import hashlib

    def _embed(text: str) -> list[float]:
        # Deterministic pseudo-embedding from text hash
        h = hashlib.sha256(text.encode()).digest()
        # Repeat to fill 384 dimensions, normalize
        raw = [b / 255.0 for b in h] * 12  # 32 * 12 = 384
        norm = sum(x * x for x in raw) ** 0.5
        return [x / norm for x in raw]

    return _embed


def test_db_starts_empty(db):
    assert db.count() == 0
    assert db.get_all_book_titles() == []


def test_add_and_count(db, sample_chunks, fake_embeddings):
    embeddings = [fake_embeddings(c.text) for c in sample_chunks]
    db.add_chunks(sample_chunks, embeddings, file_hash="sha256:test123")
    assert db.count() == 3


def test_add_and_search(db, sample_chunks, fake_embeddings):
    embeddings = [fake_embeddings(c.text) for c in sample_chunks]
    db.add_chunks(sample_chunks, embeddings, file_hash="sha256:test123")

    query_emb = fake_embeddings("software design complexity")
    results = db.search(query_emb, top_k=2)
    assert len(results) <= 2
    assert all(r.book_title == "Clean Design" for r in results)
    assert all(r.relevance_score is not None for r in results)


def test_search_with_book_filter(db, fake_embeddings):
    chunks_a = [
        Chunk(text="Python is great", book_title="Book A", author="A",
              section_title="Ch1", chunk_index=0, token_count=3),
    ]
    chunks_b = [
        Chunk(text="Java is fine", book_title="Book B", author="B",
              section_title="Ch1", chunk_index=0, token_count=3),
    ]

    db.add_chunks(chunks_a, [fake_embeddings(c.text) for c in chunks_a], "sha256:aaa")
    db.add_chunks(chunks_b, [fake_embeddings(c.text) for c in chunks_b], "sha256:bbb")

    query_emb = fake_embeddings("programming language")
    results = db.search(query_emb, top_k=5, book_filter="Book A")
    assert all(r.book_title == "Book A" for r in results)


def test_search_empty_db(db, fake_embeddings):
    results = db.search(fake_embeddings("anything"), top_k=5)
    assert results == []


def test_delete_by_hash(db, sample_chunks, fake_embeddings):
    embeddings = [fake_embeddings(c.text) for c in sample_chunks]
    db.add_chunks(sample_chunks, embeddings, file_hash="sha256:test123")
    assert db.count() == 3

    deleted = db.delete_by_hash("sha256:test123")
    assert deleted == 3
    assert db.count() == 0


def test_delete_by_hash_nonexistent(db):
    deleted = db.delete_by_hash("sha256:nope")
    assert deleted == 0


def test_get_chapter(db, sample_chunks, fake_embeddings):
    embeddings = [fake_embeddings(c.text) for c in sample_chunks]
    db.add_chunks(sample_chunks, embeddings, file_hash="sha256:test123")

    chapter = db.get_chapter("Clean Design", "Chapter 2: Naming")
    assert len(chapter) == 2
    # Should be in reading order
    assert chapter[0]["chunk_index"] < chapter[1]["chunk_index"]


def test_get_chapter_not_found(db):
    result = db.get_chapter("Nonexistent", "Chapter 99")
    assert result == []


def test_get_all_book_titles(db, fake_embeddings):
    chunks = [
        Chunk(text="A text", book_title="Alpha", author="A",
              section_title="Ch1", chunk_index=0, token_count=2),
        Chunk(text="B text", book_title="Beta", author="B",
              section_title="Ch1", chunk_index=0, token_count=2),
    ]
    embeddings = [fake_embeddings(c.text) for c in chunks]
    db.add_chunks(chunks[:1], [embeddings[0]], "sha256:a")
    db.add_chunks(chunks[1:], [embeddings[1]], "sha256:b")

    titles = db.get_all_book_titles()
    assert titles == ["Alpha", "Beta"]


def test_reset(db, sample_chunks, fake_embeddings):
    embeddings = [fake_embeddings(c.text) for c in sample_chunks]
    db.add_chunks(sample_chunks, embeddings, file_hash="sha256:test123")
    assert db.count() == 3

    db.reset()
    assert db.count() == 0


def test_page_number_none_handling(db, fake_embeddings):
    """Chunks with page_number=None should store as -1 and come back as None."""
    chunk = Chunk(
        text="No page info",
        book_title="Book",
        author="Author",
        section_title="Section",
        chunk_index=0,
        page_number=None,
        token_count=3,
    )
    db.add_chunks([chunk], [fake_embeddings(chunk.text)], "sha256:nopg")

    results = db.search(fake_embeddings("page"), top_k=1)
    assert len(results) == 1
    assert results[0].page is None


def test_add_empty_chunks(db):
    """Adding empty list should be a no-op."""
    db.add_chunks([], [], "sha256:empty")
    assert db.count() == 0

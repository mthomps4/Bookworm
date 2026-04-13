"""Tests for manifest management."""

import json
from pathlib import Path

import pytest

from library_mcp.manifest import (
    compute_file_hash,
    load_manifest,
    save_manifest,
    scan_books_dir,
    diff_manifest,
    check_embedding_model_changed,
    update_manifest_entry,
    remove_manifest_entry,
)
from library_mcp.models import Manifest, ManifestEntry


def test_compute_file_hash(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello world")
    h = compute_file_hash(f)
    assert h.startswith("sha256:")
    assert len(h) == len("sha256:") + 64


def test_compute_file_hash_deterministic(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("same content")
    assert compute_file_hash(f) == compute_file_hash(f)


def test_compute_file_hash_different_content(tmp_path):
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f1.write_text("content a")
    f2.write_text("content b")
    assert compute_file_hash(f1) != compute_file_hash(f2)


def test_load_manifest_missing(tmp_path):
    m = load_manifest(tmp_path / "nope.json")
    assert m.books == {}
    assert m.embedding_model == "all-MiniLM-L6-v2"


def test_save_and_load_manifest(tmp_path):
    path = tmp_path / "manifest.json"
    manifest = Manifest(embedding_model="test-model")
    manifest.books["book.pdf"] = ManifestEntry(
        file_hash="sha256:abc",
        title="Test",
        author="Author",
        chunk_count=5,
        file_size_bytes=1000,
    )
    save_manifest(manifest, path)

    loaded = load_manifest(path)
    assert loaded.embedding_model == "test-model"
    assert "book.pdf" in loaded.books
    assert loaded.books["book.pdf"].title == "Test"


def test_save_manifest_creates_parent_dirs(tmp_path):
    path = tmp_path / "deep" / "nested" / "manifest.json"
    save_manifest(Manifest(), path)
    assert path.exists()


def test_scan_books_dir(tmp_path):
    (tmp_path / "book1.pdf").write_bytes(b"pdf")
    (tmp_path / "book2.epub").write_bytes(b"epub")
    (tmp_path / "book3.mobi").write_bytes(b"mobi")
    (tmp_path / "book4.md").write_bytes(b"md")
    (tmp_path / "notes.txt").write_bytes(b"txt")
    (tmp_path / "page.html").write_bytes(b"html")
    (tmp_path / "ignore.docx").write_bytes(b"docx")

    books = scan_books_dir(tmp_path)
    assert set(books.keys()) == {"book1.pdf", "book2.epub", "book3.mobi", "book4.md", "notes.txt", "page.html"}


def test_scan_books_dir_empty(tmp_path):
    assert scan_books_dir(tmp_path) == {}


def test_scan_books_dir_nonexistent(tmp_path):
    assert scan_books_dir(tmp_path / "nope") == {}


def test_diff_manifest_new_files(tmp_path):
    (tmp_path / "new_book.pdf").write_bytes(b"new content")
    manifest = Manifest()
    actions = diff_manifest(manifest, tmp_path)

    assert len(actions) == 1
    assert actions[0].action == "add"
    assert actions[0].filename == "new_book.pdf"


def test_diff_manifest_removed_files(tmp_path):
    manifest = Manifest(
        books={
            "gone.pdf": ManifestEntry(
                file_hash="sha256:old",
                title="Gone",
                author="Author",
                chunk_count=1,
                file_size_bytes=100,
            )
        }
    )
    actions = diff_manifest(manifest, tmp_path)

    assert len(actions) == 1
    assert actions[0].action == "remove"
    assert actions[0].old_hash == "sha256:old"


def test_diff_manifest_changed_files(tmp_path):
    f = tmp_path / "book.pdf"
    f.write_bytes(b"new content")

    manifest = Manifest(
        books={
            "book.pdf": ManifestEntry(
                file_hash="sha256:stale_hash",
                title="Book",
                author="Author",
                chunk_count=1,
                file_size_bytes=100,
            )
        }
    )
    actions = diff_manifest(manifest, tmp_path)

    assert len(actions) == 1
    assert actions[0].action == "update"
    assert actions[0].old_hash == "sha256:stale_hash"


def test_diff_manifest_unchanged_files(tmp_path):
    f = tmp_path / "book.pdf"
    f.write_bytes(b"content")

    from library_mcp.manifest import compute_file_hash

    file_hash = compute_file_hash(f)
    manifest = Manifest(
        books={
            "book.pdf": ManifestEntry(
                file_hash=file_hash,
                title="Book",
                author="Author",
                chunk_count=1,
                file_size_bytes=100,
            )
        }
    )
    actions = diff_manifest(manifest, tmp_path)
    assert actions == []


def test_check_embedding_model_changed():
    manifest = Manifest(embedding_model="model-a")
    manifest.books["x.pdf"] = ManifestEntry(
        file_hash="sha256:x", title="X", author="A", chunk_count=1, file_size_bytes=1
    )
    assert check_embedding_model_changed(manifest, "model-b") is True
    assert check_embedding_model_changed(manifest, "model-a") is False


def test_check_embedding_model_changed_empty():
    """No books means no conflict, even if model differs."""
    manifest = Manifest(embedding_model="model-a")
    assert check_embedding_model_changed(manifest, "model-b") is False


def test_update_manifest_entry():
    manifest = Manifest()
    update_manifest_entry(
        manifest, "book.pdf", "sha256:abc", "Title", "Author", 10, 5000, "v1"
    )
    assert "book.pdf" in manifest.books
    assert manifest.books["book.pdf"].title == "Title"
    assert manifest.books["book.pdf"].version_tag == "v1"


def test_remove_manifest_entry():
    manifest = Manifest()
    manifest.books["book.pdf"] = ManifestEntry(
        file_hash="sha256:x", title="X", author="A", chunk_count=1, file_size_bytes=1
    )
    remove_manifest_entry(manifest, "book.pdf")
    assert "book.pdf" not in manifest.books


def test_remove_manifest_entry_nonexistent():
    manifest = Manifest()
    remove_manifest_entry(manifest, "nope.pdf")  # Should not raise

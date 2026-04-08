"""Tests for the ingestion pipeline."""

import pytest

from library_mcp.ingest import run_ingest
from library_mcp.manifest import load_manifest
from library_mcp.db import VectorDB


@pytest.fixture
def populated_inbox(test_config):
    """Create a test PDF in the inbox directory."""
    try:
        import fitz
    except ImportError:
        pytest.skip("pymupdf not available")

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Chapter 1: Introduction to Testing")
    page.insert_text((72, 100), "Testing is a critical part of software development.")
    page.insert_text((72, 128), "Good tests give confidence to make changes.")

    page2 = doc.new_page()
    page2.insert_text((72, 72), "Chapter 2: Unit Tests")
    page2.insert_text((72, 100), "Unit tests verify individual components in isolation.")
    page2.insert_text((72, 128), "They should be fast and deterministic.")

    pdf_path = test_config.library.books_dir / "testing-guide.pdf"
    doc.save(str(pdf_path))
    doc.close()

    return test_config


def test_ingest_empty_inbox(test_config, capsys):
    """Ingest with no books should report nothing to do."""
    run_ingest(config=test_config)
    # Should not raise — just reports "up to date"


def test_ingest_new_book(populated_inbox):
    """Ingest a new book and verify it ends up in manifest and DB."""
    config = populated_inbox
    run_ingest(config=config)

    manifest = load_manifest(config.library.manifest_path)
    assert len(manifest.books) == 1
    assert "testing-guide.pdf" in manifest.books
    entry = manifest.books["testing-guide.pdf"]
    assert entry.chunk_count > 0
    assert entry.file_hash.startswith("sha256:")

    db = VectorDB(config.library.db_path)
    assert db.count() == entry.chunk_count


def test_ingest_idempotent(populated_inbox):
    """Running ingest twice should not duplicate chunks."""
    config = populated_inbox
    run_ingest(config=config)
    first_count = VectorDB(config.library.db_path).count()

    run_ingest(config=config)
    second_count = VectorDB(config.library.db_path).count()

    assert first_count == second_count


def test_ingest_detects_removal(populated_inbox):
    """Removing a file should purge it from manifest and DB."""
    config = populated_inbox
    run_ingest(config=config)

    # Remove the file
    (config.library.books_dir / "testing-guide.pdf").unlink()

    run_ingest(config=config)
    manifest = load_manifest(config.library.manifest_path)
    assert len(manifest.books) == 0
    assert VectorDB(config.library.db_path).count() == 0


def test_ingest_detects_change(populated_inbox):
    """Modifying a file should trigger re-ingest."""
    import fitz

    config = populated_inbox
    run_ingest(config=config)
    old_manifest = load_manifest(config.library.manifest_path)
    old_hash = old_manifest.books["testing-guide.pdf"].file_hash

    # Modify the file — create a new PDF to avoid save-over-open issues
    pdf_path = config.library.books_dir / "testing-guide.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Completely rewritten content.")
    page.insert_text((72, 100), "This version is different from the original.")
    doc.save(str(pdf_path))
    doc.close()

    run_ingest(config=config)
    new_manifest = load_manifest(config.library.manifest_path)
    new_hash = new_manifest.books["testing-guide.pdf"].file_hash

    assert old_hash != new_hash


def test_ingest_full_rebuild(populated_inbox):
    """Full rebuild should clear and recreate everything."""
    config = populated_inbox
    run_ingest(config=config)
    run_ingest(full=True, config=config)

    manifest = load_manifest(config.library.manifest_path)
    assert len(manifest.books) == 1
    assert manifest.last_full_ingest is not None


def test_ingest_single_file(populated_inbox):
    """Ingest a single file by name."""
    config = populated_inbox
    run_ingest(file="testing-guide.pdf", config=config)

    manifest = load_manifest(config.library.manifest_path)
    assert len(manifest.books) == 1


def test_ingest_single_file_not_found(test_config, capsys):
    """Ingest a nonexistent file should report error without crashing."""
    run_ingest(file="nonexistent.pdf", config=test_config)
    # Should not raise


def test_ingest_with_version_tag(populated_inbox):
    """Version tag should be stored in manifest."""
    config = populated_inbox
    run_ingest(file="testing-guide.pdf", tag="v2", config=config)

    manifest = load_manifest(config.library.manifest_path)
    assert manifest.books["testing-guide.pdf"].version_tag == "v2"

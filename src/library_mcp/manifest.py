"""Manifest management — tracks ingested books, hashes, and supports incremental reindexing."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .models import Manifest, ManifestEntry

logger = logging.getLogger(__name__)

ALL_SUPPORTED_EXTENSIONS = {".pdf", ".epub", ".mobi", ".md"}


def _allowed_extensions(allowed_formats: list[str] | None = None) -> set[str]:
    """Build the set of extensions to scan for, based on config."""
    if allowed_formats:
        return {f".{fmt.lower().lstrip('.')}" for fmt in allowed_formats} & ALL_SUPPORTED_EXTENSIONS
    return ALL_SUPPORTED_EXTENSIONS


def compute_file_hash(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            sha256.update(block)
    return f"sha256:{sha256.hexdigest()}"


def load_manifest(manifest_path: Path) -> Manifest:
    """Load manifest from disk, or return empty manifest if not found."""
    if manifest_path.exists():
        data = json.loads(manifest_path.read_text())
        return Manifest.model_validate(data)
    return Manifest()


def save_manifest(manifest: Manifest, manifest_path: Path) -> None:
    """Persist manifest to disk."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(manifest.model_dump_json(indent=2))
    logger.info(f"Manifest saved to {manifest_path}")


def scan_books_dir(books_dir: Path, allowed_formats: list[str] | None = None) -> dict[str, Path]:
    """Scan directory for supported book files. Returns {filename: path}.

    If allowed_formats is provided, only files matching those formats are returned.
    """
    extensions = _allowed_extensions(allowed_formats)
    books: dict[str, Path] = {}
    if not books_dir.exists():
        logger.warning(f"Books directory does not exist: {books_dir}")
        return books

    for path in books_dir.iterdir():
        if path.is_file() and path.suffix.lower() in extensions:
            books[path.name] = path

    return books


class IngestAction:
    """Represents what needs to happen for a single file."""

    def __init__(self, filename: str, action: str, path: Path | None = None, old_hash: str | None = None):
        self.filename = filename
        self.action = action  # "add", "update", "remove"
        self.path = path
        self.old_hash = old_hash

    def __repr__(self) -> str:
        return f"IngestAction({self.filename!r}, {self.action!r})"


def diff_manifest(
    manifest: Manifest,
    books_dir: Path,
    allowed_formats: list[str] | None = None,
    detect_removals: bool = True,
) -> list[IngestAction]:
    """Compare manifest against files on disk. Returns list of actions needed.

    If detect_removals is False, only additions and updates are returned.
    This is used when ingesting from an ad-hoc path — we don't want to purge
    books that came from other directories.
    """
    resolved_dir = str(books_dir.resolve())
    on_disk = scan_books_dir(books_dir, allowed_formats)
    actions: list[IngestAction] = []

    # Check files on disk against manifest
    for filename, path in on_disk.items():
        file_hash = compute_file_hash(path)
        if filename not in manifest.books:
            actions.append(IngestAction(filename, "add", path=path))
        elif manifest.books[filename].file_hash != file_hash:
            actions.append(IngestAction(
                filename, "update", path=path,
                old_hash=manifest.books[filename].file_hash,
            ))
        # else: unchanged, skip

    # Check manifest for removed files — only for books from this directory
    if detect_removals:
        for filename, entry in manifest.books.items():
            if filename not in on_disk:
                # Only flag removal if the book came from this directory
                # (empty source_dir means legacy entry — treat as belonging to default dir)
                if not entry.source_dir or entry.source_dir == resolved_dir:
                    actions.append(IngestAction(
                        filename, "remove",
                        old_hash=entry.file_hash,
                    ))

    return actions


def check_embedding_model_changed(manifest: Manifest, current_model: str) -> bool:
    """Check if the embedding model has changed since last ingest."""
    if not manifest.books:
        return False  # No existing data, no conflict
    return manifest.embedding_model != current_model


def update_manifest_entry(
    manifest: Manifest,
    filename: str,
    file_hash: str,
    title: str,
    author: str,
    chunk_count: int,
    file_size_bytes: int,
    version_tag: str | None = None,
    ocr: bool = False,
    source_dir: str = "",
) -> None:
    """Add or update a manifest entry."""
    manifest.books[filename] = ManifestEntry(
        file_hash=file_hash,
        title=title,
        author=author,
        chunk_count=chunk_count,
        version_tag=version_tag,
        ingested_at=datetime.now(timezone.utc).isoformat(),
        file_size_bytes=file_size_bytes,
        ocr=ocr,
        source_dir=source_dir,
    )


def remove_manifest_entry(manifest: Manifest, filename: str) -> None:
    """Remove a book from the manifest."""
    manifest.books.pop(filename, None)

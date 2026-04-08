"""Ingestion pipeline — orchestrates scan, diff, extract, chunk, embed, store."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .chunker import chunk_book
from .config import load_config
from .db import VectorDB
from .embeddings import EmbeddingFunc, create_embedder, embed_in_batches
from .extract import extract_book
from .manifest import (
    IngestAction,
    check_embedding_model_changed,
    compute_file_hash,
    diff_manifest,
    load_manifest,
    remove_manifest_entry,
    save_manifest,
    scan_books_dir,
    update_manifest_entry,
)
from .models import AppConfig, Manifest

logger = logging.getLogger(__name__)
console = Console()


def run_ingest(
    full: bool = False,
    file: str | None = None,
    tag: str | None = None,
    config: AppConfig | None = None,
) -> None:
    """Run the ingestion pipeline."""
    if config is None:
        config = load_config()

    manifest_path = config.library.manifest_path
    manifest = load_manifest(manifest_path)

    # Check for embedding model change
    if check_embedding_model_changed(manifest, config.embeddings.model):
        console.print(
            f"[yellow]Warning:[/yellow] Embedding model changed "
            f"({manifest.embedding_model} -> {config.embeddings.model}). "
            f"Existing vectors are invalidated."
        )
        if not full:
            console.print("[yellow]Run with --full to rebuild all embeddings.[/yellow]")
            return
        console.print("[bold]Full rebuild requested — proceeding.[/bold]")

    db = VectorDB(config.library.db_path)
    embedder = create_embedder(config.embeddings)

    if full:
        _full_rebuild(config, manifest, manifest_path, db, embedder, tag)
    elif file:
        _ingest_single_file(config, manifest, manifest_path, db, embedder, file, tag)
    else:
        _incremental_ingest(config, manifest, manifest_path, db, embedder, tag)


def _full_rebuild(
    config: AppConfig,
    manifest: Manifest,
    manifest_path: Path,
    db: VectorDB,
    embedder: EmbeddingFunc,
    tag: str | None,
) -> None:
    """Wipe DB and re-ingest everything."""
    console.print("[bold]Full rebuild — clearing database...[/bold]")
    db.reset()
    manifest.books.clear()

    on_disk = scan_books_dir(config.library.books_dir, config.library.allowed_formats)
    if not on_disk:
        console.print("[yellow]No books found in inbox.[/yellow]")
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Ingesting books...", total=len(on_disk))
        for filename, path in on_disk.items():
            progress.update(task, description=f"Ingesting {filename}")
            _process_book(config, manifest, db, embedder, path, filename, tag)
            # Save after each book so partial progress survives crashes
            save_manifest(manifest, manifest_path)
            progress.advance(task)

    manifest.last_full_ingest = datetime.now(timezone.utc).isoformat()
    manifest.embedding_model = config.embeddings.model
    manifest.db_path = str(config.library.db_path)
    save_manifest(manifest, manifest_path)
    console.print(f"[green]Full rebuild complete.[/green] {len(manifest.books)} books indexed.")


def _incremental_ingest(
    config: AppConfig,
    manifest: Manifest,
    manifest_path: Path,
    db: VectorDB,
    embedder: EmbeddingFunc,
    tag: str | None,
) -> None:
    """Ingest only new/changed books, remove deleted ones."""
    actions = diff_manifest(manifest, config.library.books_dir, config.library.allowed_formats)

    if not actions:
        console.print("[green]Everything is up to date.[/green]")
        return

    adds = [a for a in actions if a.action == "add"]
    updates = [a for a in actions if a.action == "update"]
    removes = [a for a in actions if a.action == "remove"]

    console.print(
        f"Found: [green]+{len(adds)} new[/green], "
        f"[yellow]~{len(updates)} changed[/yellow], "
        f"[red]-{len(removes)} removed[/red]"
    )

    # Handle removals
    for action in removes:
        console.print(f"  Removing: {action.filename}")
        if action.old_hash:
            db.delete_by_hash(action.old_hash)
        remove_manifest_entry(manifest, action.filename)

    # Handle updates (delete old, then re-add)
    for action in updates:
        console.print(f"  Updating: {action.filename}")
        if action.old_hash:
            db.delete_by_hash(action.old_hash)
        remove_manifest_entry(manifest, action.filename)

    # Process adds and updates
    to_process = adds + updates
    if to_process:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Ingesting...", total=len(to_process))
            for action in to_process:
                progress.update(task, description=f"Ingesting {action.filename}")
                _process_book(config, manifest, db, embedder, action.path, action.filename, tag)
                save_manifest(manifest, manifest_path)
                progress.advance(task)

    manifest.embedding_model = config.embeddings.model
    manifest.db_path = str(config.library.db_path)
    save_manifest(manifest, manifest_path)
    console.print(f"[green]Ingest complete.[/green] {len(manifest.books)} books indexed.")


def _ingest_single_file(
    config: AppConfig,
    manifest: Manifest,
    manifest_path: Path,
    db: VectorDB,
    embedder: EmbeddingFunc,
    filename: str,
    tag: str | None,
) -> None:
    """Ingest a specific file by name."""
    path = config.library.books_dir / filename
    if not path.exists():
        console.print(f"[red]File not found:[/red] {path}")
        return

    # Remove old version if it exists
    if filename in manifest.books:
        old_hash = manifest.books[filename].file_hash
        db.delete_by_hash(old_hash)
        remove_manifest_entry(manifest, filename)

    with console.status(f"Ingesting {filename}..."):
        _process_book(config, manifest, db, embedder, path, filename, tag)

    manifest.embedding_model = config.embeddings.model
    manifest.db_path = str(config.library.db_path)
    save_manifest(manifest, manifest_path)
    console.print(f"[green]Done.[/green] {filename} ingested.")


def _process_book(
    config: AppConfig,
    manifest: Manifest,
    db: VectorDB,
    embedder: EmbeddingFunc,
    path: Path,
    filename: str,
    tag: str | None,
) -> None:
    """Extract, chunk, embed, and store a single book."""
    file_hash = compute_file_hash(path)
    ingested_at = datetime.now(timezone.utc).isoformat()

    # Extract
    try:
        book = extract_book(path)
    except Exception as e:
        console.print(f"[red]Failed to extract {filename}:[/red] {e}")
        logger.exception(f"Extraction failed for {filename}")
        return

    if not book.sections:
        console.print(f"[yellow]Warning:[/yellow] No text extracted from {filename}")
        return

    # Chunk
    try:
        chunks = chunk_book(book, config.chunking)
    except Exception as e:
        console.print(f"[red]Failed to chunk {filename}:[/red] {e}")
        logger.exception(f"Chunking failed for {filename}")
        return

    if not chunks:
        console.print(f"[yellow]Warning:[/yellow] No chunks produced from {filename}")
        return

    # Embed
    try:
        texts = [c.text for c in chunks]
        embeddings = embed_in_batches(embedder, texts, config.embeddings.batch_size)
    except Exception as e:
        console.print(f"[red]Failed to generate embeddings for {filename}:[/red] {e}")
        logger.exception(f"Embedding failed for {filename}")
        return

    # Store
    try:
        db.add_chunks(chunks, embeddings, file_hash, version_tag=tag, ingested_at=ingested_at)
    except Exception as e:
        console.print(f"[red]Failed to store {filename} in database:[/red] {e}")
        logger.exception(f"DB storage failed for {filename}")
        return

    # Update manifest
    update_manifest_entry(
        manifest,
        filename=filename,
        file_hash=file_hash,
        title=book.title,
        author=book.author,
        chunk_count=len(chunks),
        file_size_bytes=path.stat().st_size,
        version_tag=tag,
    )

    logger.info(f"Processed {filename}: {len(book.sections)} sections, {len(chunks)} chunks")

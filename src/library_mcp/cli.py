"""CLI entry point for library management commands."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .config import load_config
from .db import VectorDB
from .embeddings import create_embedder
from .ingest import run_ingest
from .logging_config import setup_logging
from .manifest import load_manifest, remove_manifest_entry, save_manifest

app = typer.Typer(name="library", help="Library MCP — manage your ebook knowledge base.")
console = Console()


@app.command()
def ingest(
    full: bool = typer.Option(False, "--full", help="Force full rebuild of the index"),
    file: Optional[str] = typer.Option(None, "--file", help="Ingest a specific file"),
    tag: Optional[str] = typer.Option(None, "--tag", help="Version tag for the ingested book"),
) -> None:
    """Scan inbox and ingest new or changed books."""
    setup_logging()
    run_ingest(full=full, file=file, tag=tag)


@app.command(name="list")
def list_books() -> None:
    """List all indexed books."""
    config = load_config()
    manifest = load_manifest(config.library.manifest_path)

    if not manifest.books:
        console.print("[yellow]No books indexed yet.[/yellow] Run `library ingest` first.")
        return

    table = Table(title="Indexed Books")
    table.add_column("Title", style="bold")
    table.add_column("Author")
    table.add_column("Chunks", justify="right")
    table.add_column("Tag")
    table.add_column("Ingested At")

    for filename, entry in sorted(manifest.books.items()):
        table.add_row(
            entry.title,
            entry.author,
            str(entry.chunk_count),
            entry.version_tag or "—",
            entry.ingested_at[:19],
        )

    console.print(table)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    book: Optional[str] = typer.Option(None, "--book", help="Filter by book title"),
    top_k: int = typer.Option(5, "--top-k", help="Number of results"),
) -> None:
    """Search the library for relevant passages."""
    setup_logging()
    config = load_config()
    db = VectorDB(config.library.db_path)
    embedder = create_embedder(config.embeddings)

    if db.count() == 0:
        console.print("[yellow]Library is empty.[/yellow] Run `library ingest` first.")
        return

    query_embedding = embedder.embed([query])[0]
    results = db.search(query_embedding, top_k=top_k, book_filter=book)

    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return

    for i, r in enumerate(results, 1):
        console.print(f"\n[bold]── Result {i} (score: {r.relevance_score}) ──[/bold]")
        console.print(f"[dim]{r.book_title}[/dim] by {r.author} | {r.section}", end="")
        if r.page:
            console.print(f" | p.{r.page}", end="")
        console.print()
        # Show a trimmed preview
        preview = r.text[:500] + "..." if len(r.text) > 500 else r.text
        console.print(preview)


@app.command()
def remove(
    title: str = typer.Argument(..., help="Book title to remove"),
) -> None:
    """Remove a book from the index."""
    config = load_config()
    manifest = load_manifest(config.library.manifest_path)
    db = VectorDB(config.library.db_path)

    # Find the book by title
    found_filename = None
    for filename, entry in manifest.books.items():
        if entry.title.lower() == title.lower():
            found_filename = filename
            break

    if not found_filename:
        console.print(f"[red]Book not found:[/red] {title}")
        console.print("Indexed books:")
        for entry in manifest.books.values():
            console.print(f"  • {entry.title}")
        return

    entry = manifest.books[found_filename]
    db.delete_by_hash(entry.file_hash)
    remove_manifest_entry(manifest, found_filename)
    save_manifest(manifest, config.library.manifest_path)
    console.print(f"[green]Removed:[/green] {entry.title} ({entry.chunk_count} chunks)")


@app.command()
def stats() -> None:
    """Show index statistics."""
    config = load_config()
    manifest = load_manifest(config.library.manifest_path)
    db = VectorDB(config.library.db_path)

    total_chunks = db.count()
    total_books = len(manifest.books)
    total_size = sum(e.file_size_bytes for e in manifest.books.values())

    console.print(f"[bold]Library Stats[/bold]")
    console.print(f"  Books indexed:    {total_books}")
    console.print(f"  Total chunks:     {total_chunks}")
    console.print(f"  Source file size:  {total_size / (1024*1024):.1f} MB")
    console.print(f"  Embedding model:  {manifest.embedding_model}")
    console.print(f"  DB path:          {config.library.db_path}")
    if manifest.last_full_ingest:
        console.print(f"  Last full ingest: {manifest.last_full_ingest[:19]}")


@app.command()
def rebuild() -> None:
    """Rebuild the entire index from scratch."""
    setup_logging()
    console.print("[bold red]This will delete the entire database and re-ingest all books.[/bold red]")
    confirm = typer.confirm("Continue?")
    if not confirm:
        raise typer.Abort()
    run_ingest(full=True)


def main() -> None:
    app()


if __name__ == "__main__":
    main()

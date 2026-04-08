"""MCP server — exposes library search tools over stdio transport."""

from __future__ import annotations

import json
import logging
from functools import wraps
from typing import Callable

from mcp.server.fastmcp import FastMCP

from .config import load_config
from .db import VectorDB
from .embeddings import create_embedder
from .logging_config import setup_logging
from .manifest import load_manifest

logger = logging.getLogger(__name__)

# Initialize server
mcp = FastMCP("library-mcp")

# Lazy-init globals — created on first tool call
_config = None
_db = None
_embedder = None
_manifest_path = None


def _init():
    """Lazy initialization of config, DB, and embedder."""
    global _config, _db, _embedder, _manifest_path
    if _config is None:
        _config = load_config()
        _db = VectorDB(_config.library.db_path)
        _embedder = create_embedder(_config.embeddings)
        _manifest_path = _config.library.manifest_path
        logger.info("Library MCP server initialized")


def _safe_tool(fn: Callable) -> Callable:
    """Wrap an MCP tool so unhandled exceptions return error JSON instead of crashing."""
    @wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except Exception as e:
            logger.exception(f"Tool {fn.__name__} failed")
            return json.dumps({"error": str(e), "tool": fn.__name__})
    return wrapper


@mcp.tool()
@_safe_tool
async def list_books() -> str:
    """List all books in the knowledge base with their titles, authors, and chunk counts.

    Use this to understand what reference material is available before searching.
    """
    _init()
    manifest = load_manifest(_manifest_path)

    if not manifest.books:
        return json.dumps({"books": [], "message": "No books indexed yet."})

    books = [
        {
            "title": entry.title,
            "author": entry.author,
            "chunk_count": entry.chunk_count,
            "version_tag": entry.version_tag,
            "ingested_at": entry.ingested_at,
        }
        for entry in manifest.books.values()
    ]

    return json.dumps({"books": books, "total": len(books)}, indent=2)


@mcp.tool()
@_safe_tool
async def search_library(query: str, book_filter: str | None = None, top_k: int = 5) -> str:
    """Search all reference books for passages relevant to the query.

    Returns the most semantically similar text chunks with source info.
    Use book_filter to restrict search to a specific book title.
    Use this tool whenever you need best practices, patterns,
    or authoritative guidance on a topic covered by the library.

    Args:
        query: The search query describing what you're looking for.
        book_filter: Optional book title to restrict search to a specific book.
        top_k: Number of results to return (default 5).
    """
    _init()

    if _db.count() == 0:
        return json.dumps({"results": [], "message": "Library is empty. Run ingest first."})

    top_k = max(1, min(top_k, _config.search.max_top_k))
    query_embedding = _embedder.embed([query])[0]
    results = _db.search(query_embedding, top_k=top_k, book_filter=book_filter)

    # Filter by relevance threshold
    threshold = _config.search.relevance_threshold
    filtered = [r for r in results if r.relevance_score >= threshold]

    return json.dumps(
        {
            "results": [r.model_dump() for r in filtered],
            "query": query,
            "total": len(filtered),
        },
        indent=2,
    )


@mcp.tool()
@_safe_tool
async def get_chapter(book_title: str, section_title: str) -> str:
    """Retrieve all chunks from a specific chapter or section of a book.

    Use this when you need deeper context from a section that
    search_library identified as relevant. Results are returned
    in reading order.

    Args:
        book_title: The exact title of the book.
        section_title: The exact title of the chapter or section.
    """
    _init()

    chunks = _db.get_chapter(book_title, section_title)

    if not chunks:
        return json.dumps({
            "chunks": [],
            "message": f"No chunks found for '{section_title}' in '{book_title}'.",
        })

    return json.dumps(
        {
            "chunks": chunks,
            "book_title": book_title,
            "section_title": section_title,
            "total_chunks": len(chunks),
        },
        indent=2,
    )


def main():
    setup_logging()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

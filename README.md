# BookWorm

A local MCP server that turns your ebook library into a searchable knowledge base. Drop books into a folder, run ingest, and Claude Code automatically searches relevant passages when it needs reference material.

Supports PDF, EPUB, and MOBI. Runs entirely locally -- no external API required.

---

## Getting Started

### 1. Install

```bash
git clone <repo-url> && cd BookWorm
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

This installs the `bookworm` CLI and all dependencies (pymupdf, chromadb, sentence-transformers, etc). First run will download the embedding model (~80MB).

### 2. Add Your Books

Copy or symlink books into the inbox:

```bash
cp ~/Books/clean-code.epub books/inbox/
cp ~/Books/designing-data-intensive-apps.pdf books/inbox/
```

**Duplicate formats:** If you have the same book as `clean-code.pdf`, `clean-code.epub`, and `clean-code.mobi`, only add **one** to the inbox. Indexing the same book in multiple formats produces duplicate search results.

When choosing which format to keep, prefer in this order:

| Priority | Format | Why |
|----------|--------|-----|
| 1st | **EPUB** | Cleanest text extraction, chapter boundaries from TOC, smallest files |
| 2nd | **PDF** | Good with TOC-based chapter detection; OCR fallback for scanned pages |
| 3rd | **MOBI** | Gets converted to EPUB internally -- if you have the EPUB, use that instead |

### 3. Ingest

```bash
bookworm ingest
```

This scans `books/inbox/`, extracts text, chunks it, generates embeddings, and stores everything in a local ChromaDB database. You'll see a progress bar for each book.

Verify it worked:

```bash
bookworm stats      # How many books/chunks are indexed
bookworm list       # Table of all indexed books
```

Test a search from the command line:

```bash
bookworm search "error handling best practices"
bookworm search "dependency injection" --book "Clean Code" --top-k 3
```

### 4. Shell Alias

Add the alias to your shell config so you can run `bookworm` from anywhere:

```bash
# ~/.zshrc or ~/.bashrc
alias bookworm="$HOME/Code/BookWorm/.venv/bin/bookworm"
```

Then reload: `source ~/.zshrc`

### 5. Connect to Claude Code

BookWorm runs as an MCP server -- Claude Code spawns it as a local subprocess and communicates over stdio.

Add the MCP config to **one** of these locations:

| Scope | File | When to use |
|-------|------|-------------|
| Global (all projects) | `~/.mcp.json` | You want your library everywhere |
| Project-only | `<project>/.mcp.json` | Scoped to one codebase |

```json
{
  "mcpServers": {
    "bookworm": {
      "command": "/absolute/path/to/BookWorm/.venv/bin/python",
      "args": ["-m", "library_mcp.server"],
      "cwd": "/absolute/path/to/BookWorm",
      "env": {
        "PYTHONPATH": "/absolute/path/to/BookWorm/src"
      }
    }
  }
}
```

Replace `/absolute/path/to/BookWorm` with the actual path on your machine. A template is provided in `claude-code-config.json`.

**Restart Claude Code** (or start a new session). The `bookworm` MCP tools become available automatically.

### Claude Code MCP Tools

These are the tools Claude can call autonomously during a session:

| Tool | What it does |
|------|--------------|
| `list_books()` | Shows what's in the library |
| `search_library(query, book_filter?, top_k?)` | Semantic search across all books |
| `get_chapter(book_title, section_title)` | Retrieves a full chapter for deeper reading |
| `ingest_path(path, file?, tag?)` | Ingest books mid-session from any directory |

Claude calls these on its own when it thinks your library has relevant material. You can also ask directly -- e.g. "search my books for GenServer patterns" or "ingest the books at ~/Downloads/elixir-books".

### Common Workflows

**From the terminal (CLI):**

```bash
bookworm ingest                              # Scan inbox, process new/changed books
bookworm ingest --path ~/Books/elixir        # Ingest from a specific directory
bookworm list                                # See what's indexed
bookworm search "pattern matching"           # Quick search
bookworm stats                               # Index health check
```

**From a Claude Code session (MCP tools):**

- "What books do I have indexed?" -- calls `list_books`
- "Search my library for Ecto multi-tenancy" -- calls `search_library`
- "Pull up the chapter on GenServers from that Elixir book" -- calls `get_chapter`
- "Ingest the PDFs at ~/Downloads/phoenix-books" -- calls `ingest_path`

The MCP tools and CLI share the same database, so books ingested from either side are immediately available to both.

### 6. Keep It Updated

BookWorm tracks file hashes, so re-running ingest is fast -- it only processes what changed.

```bash
# After adding or updating books:
bookworm ingest

# After removing a book file from inbox:
bookworm ingest          # Detects the removal, purges from DB

# Remove a specific book by title (without deleting the file):
bookworm remove "Clean Code"

# Add a new edition alongside the old:
bookworm ingest --file "clean-code-3rd.pdf" --tag "3rd-edition"

# Ingest from another folder (GDrive, Dropbox, NAS, etc):
bookworm ingest --path ~/Google\ Drive/Books
bookworm ingest --path /mnt/nas/tech-library
```

**Multi-folder ingestion:** Using `--path` accumulates books from multiple directories into the same DB. Books from other directories are never removed -- only additions and updates are processed. Each book tracks which directory it came from.

**Full reindex** (when you want to start fresh):

```bash
bookworm rebuild         # Interactive confirmation, then wipes DB and re-ingests everything
bookworm ingest --full   # Same thing, no confirmation prompt
```

**When is a full reindex required?**
- You changed the embedding model in config (e.g. switched from local to OpenAI)
- You changed chunking settings and want them applied to existing books
- Something feels off and you want a clean slate

BookWorm will warn you and refuse to do an incremental ingest if it detects an embedding model change -- it'll tell you to use `--full`.

---

## Configuration

### config.yaml

```yaml
library:
  books_dir: "./books/inbox"              # Where to scan for books
  manifest_path: "./books/.manifest.json" # Tracks what's been indexed
  db_path: "./db"                         # ChromaDB storage
  allowed_formats: ["pdf", "epub", "mobi"] # Remove formats to skip them

chunking:
  target_tokens: 600        # Target chunk size
  max_tokens: 800           # Hard max per chunk
  overlap_tokens: 75        # Overlap between chunks for context continuity
  respect_paragraphs: true  # Never split mid-paragraph
  respect_sections: true    # Prefer chapter/section boundaries

embeddings:
  provider: "local"             # "local" (free, no network) or "openai" (better, costs money)
  model: "all-MiniLM-L6-v2"    # Local: all-MiniLM-L6-v2, all-mpnet-base-v2
  batch_size: 64                # OpenAI: text-embedding-3-small

search:
  default_top_k: 5          # Default results per query
  max_top_k: 20             # Max allowed
  relevance_threshold: 0.3  # Minimum similarity score (0-1)
```

### Environment Variables

All config values can be overridden via environment variables (ENV takes precedence):

| Variable | Default | Description |
|----------|---------|-------------|
| `BOOKS_PATH` | `./books/inbox` | Where to scan for books |
| `CHROMA_PATH` | `./db` | ChromaDB storage location |
| `MANIFEST_PATH` | `./books/.manifest.json` | Manifest file location |
| `ALLOWED_FORMATS` | `pdf,epub,mobi` | Comma-separated list of formats to index |
| `EMBEDDING_PROVIDER` | `local` | `local` or `openai` |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Embedding model name |
| `OPENAI_API_KEY` | -- | Required only if provider is `openai` |
| `CHUNK_TARGET_TOKENS` | `600` | Target chunk size |
| `CHUNK_OVERLAP_TOKENS` | `75` | Overlap between chunks |
| `SEARCH_DEFAULT_TOP_K` | `5` | Default search results |
| `LOG_LEVEL` | `info` | `debug`, `info`, `warning`, `error` |

---

## CLI Reference

```bash
bookworm ingest                              # Incremental: process new/changed, remove deleted
bookworm ingest --full                       # Full rebuild from scratch
bookworm ingest --file "book.pdf"            # Ingest one specific file
bookworm ingest --file "book.pdf" --tag "v2" # With a version tag
bookworm ingest --path ~/GDrive/Books        # Ingest from an external folder
bookworm ingest --path ~/GDrive/Books --file "specific.epub"  # One file from external folder
bookworm list                                # Table of indexed books
bookworm search "query"                      # Semantic search
bookworm search "query" --book "Title"       # Search within one book
bookworm search "query" --top-k 10           # More results
bookworm remove "Book Title"                 # Remove from index by title
bookworm stats                               # Chunk counts, DB size, model info
bookworm rebuild                             # Wipe and rebuild (with confirmation)
```

---

## How It Works

```
Books (PDF/EPUB/MOBI)
  -> Extract text (pymupdf, ebooklib, OCR fallback)
  -> Chunk (500-800 tokens, overlap, paragraph-aware)
  -> Embed (sentence-transformers locally, or OpenAI)
  -> Store in ChromaDB with metadata (title, author, section, page)
  -> Serve via MCP tools over stdio to Claude Code
```

Incremental reindexing via SHA-256 file hashing -- only new or changed books are processed. The manifest tracks what's been ingested so repeated runs are fast.

---

## Testing

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

---

## Project Structure

```
BookWorm/
├── src/library_mcp/
│   ├── server.py          # MCP server -- tool definitions
│   ├── ingest.py          # Ingestion pipeline orchestrator
│   ├── extract.py         # PDF, EPUB, MOBI text extraction
│   ├── chunker.py         # Text chunking with overlap
│   ├── embeddings.py      # Pluggable embedding providers
│   ├── db.py              # ChromaDB wrapper
│   ├── manifest.py        # Change detection and tracking
│   ├── models.py          # Pydantic data models
│   ├── config.py          # Config loading (YAML + ENV)
│   ├── cli.py             # Typer CLI commands
│   └── logging_config.py  # Centralized logging
├── books/inbox/           # Drop books here
├── tests/                 # Test suite
├── config.yaml            # Default configuration
└── claude-code-config.json # MCP config template
```

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

This installs the `library` CLI and all dependencies (pymupdf, chromadb, sentence-transformers, etc). First run will download the embedding model (~80MB).

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
| -- | **Markdown** | Native support -- splits on headings for sections, no conversion needed |

### 3. Ingest

```bash
library ingest
```

This scans `books/inbox/`, extracts text, chunks it, generates embeddings, and stores everything in a local ChromaDB database. You'll see a progress bar for each book.

Verify it worked:

```bash
library stats      # How many books/chunks are indexed
library list       # Table of all indexed books
```

Test a search from the command line:

```bash
library search "error handling best practices"
library search "dependency injection" --book "Clean Code" --top-k 3
```

### 4. Connect to Claude Code

This is what makes it useful -- Claude will automatically search your library when it needs reference material.

Add the MCP server config to **one** of these locations:

| Scope | File | When to use |
|-------|------|-------------|
| Global (all projects) | `~/.claude/settings.json` | You want your library everywhere |
| Project-only | `<project>/.claude/settings.json` | Scoped to one codebase |

Add the `mcpServers` block (create the file if it doesn't exist):

```json
{
  "mcpServers": {
    "library-mcp": {
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

Replace `/absolute/path/to/BookWorm` with the actual path on your machine. Using the venv's Python ensures dependencies are available.

> **Note:** The bundled `claude-code-config.json` and `claude-code-config-docker.json` templates contain `CHANGE_ME` placeholders -- update the paths for your machine before copying into your Claude Code settings.

**Restart Claude Code** (or start a new session). You should see the `library-mcp` tools become available. Claude now has access to:

| Tool | What it does |
|------|--------------|
| `list_books()` | Shows what's in the library |
| `search_library(query, book_filter?, top_k?)` | Semantic search across all books |
| `get_chapter(book_title, section_title)` | Retrieves a full chapter for deeper reading |

Claude will call these autonomously when it thinks your library has relevant material.

### 5. Keep It Updated

BookWorm tracks file hashes, so re-running ingest is fast -- it only processes what changed.

```bash
# After adding or updating books:
library ingest

# After removing a book file from inbox:
library ingest          # Detects the removal, purges from DB

# Remove a specific book by title (without deleting the file):
library remove "Clean Code"

# Add a new edition alongside the old:
library ingest --file "clean-code-3rd.pdf" --tag "3rd-edition"
```

**Full reindex** (when you want to start fresh):

```bash
library rebuild         # Interactive confirmation, then wipes DB and re-ingests everything
library ingest --full   # Same thing, no confirmation prompt
```

**When is a full reindex required?**
- You changed the embedding model in config (e.g. switched from local to OpenAI)
- You changed chunking settings and want them applied to existing books
- Something feels off and you want a clean slate

BookWorm will warn you and refuse to do an incremental ingest if it detects an embedding model change -- it'll tell you to use `--full`.

---

## Docker Setup

For a more portable setup, or if you don't want to install Python dependencies on the host:

```bash
cp .env.example .env    # Edit paths to match your machine
docker compose build    # First build downloads the embedding model into the image

# Ingest
docker compose run --rm ingest
docker compose run --rm ingest --full

# Other CLI commands
docker compose run --rm ingest list
docker compose run --rm ingest search "error handling" --top-k 5
docker compose run --rm ingest stats
```

### Docker + Claude Code

```json
{
  "mcpServers": {
    "library-mcp": {
      "command": "docker",
      "args": ["compose", "-f", "/absolute/path/to/BookWorm/docker-compose.yml", "run", "--rm", "-T", "library-mcp"]
    }
  }
}
```

The `-T` flag is required -- it disables TTY allocation for stdio transport.

### Multi-Machine Workflow

1. Push repo to GitHub (books and DB are gitignored)
2. On new machine: `git clone` then `cp .env.example .env`
3. Edit `.env` to point `BOOKS_PATH` at your local books folder (iCloud, Dropbox, NAS, wherever)
4. `docker compose build && docker compose run --rm ingest`
5. Add MCP config to Claude Code settings
6. Done -- same image, different books, different machine

---

## Configuration Reference

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

All config values can be overridden via environment variables (ENV takes precedence). Copy `.env.example` to `.env`:

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
library ingest                              # Incremental: process new/changed, remove deleted
library ingest --full                       # Full rebuild from scratch
library ingest --file "book.pdf"            # Ingest one specific file
library ingest --file "book.pdf" --tag "v2" # With a version tag
library list                                # Table of indexed books
library search "query"                      # Semantic search
library search "query" --book "Title"       # Search within one book
library search "query" --top-k 10           # More results
library remove "Book Title"                 # Remove from index by title
library stats                               # Chunk counts, DB size, model info
library rebuild                             # Wipe and rebuild (with confirmation)
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

71 tests covering extraction, chunking, DB operations, manifest diffing, ingest pipeline, and end-to-end search.

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
├── Dockerfile             # Multi-stage build
└── docker-compose.yml     # Server + ingest services
```

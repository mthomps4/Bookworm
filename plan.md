# Library MCP — Project Specification

## Overview

Build a local MCP (Model Context Protocol) server that acts as a searchable knowledge base over a personal library of ebooks. The system ingests PDF, EPUB, and MOBI files, extracts and chunks their text, generates vector embeddings, stores them in a local vector database, and exposes semantic search via MCP tools that Claude can call autonomously during development workflows.

The goal: drop books into a folder, run an ingest command, and Claude Code automatically searches relevant passages when it needs reference material or best-practice guidance — with zero manual prompting.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Claude Code                                        │
│  (MCP Client — calls tools automatically)           │
└──────────────┬──────────────────────────────────────┘
               │ JSON-RPC (stdio transport)
               ▼
┌─────────────────────────────────────────────────────┐
│  MCP Server  (Python)                               │
│                                                     │
│  Tools exposed:                                     │
│    • list_books()                                   │
│    • search_library(query, book_filter?, top_k?)    │
│    • get_chapter(book_title, chapter_or_section)     │
│                                                     │
│  Reads from:                                        │
│    • ChromaDB (local persistent vector DB)          │
│    • Manifest file (book metadata + hashes)         │
└──────────────┬──────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────┐
│  ChromaDB (persistent, file-based)                  │
│                                                     │
│  Collection: "library"                              │
│  Each document = one text chunk                     │
│  Metadata per chunk:                                │
│    • book_title                                     │
│    • author                                         │
│    • chapter / section                              │
│    • chunk_index                                    │
│    • page_number (if available)                     │
│    • file_hash                                      │
│    • version_tag (optional)                         │
│    • ingested_at (ISO timestamp)                    │
└─────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
library-mcp/
├── README.md                    # Setup and usage instructions
├── pyproject.toml               # Project config, dependencies
├── .env.example                 # Environment variable template
├── .env                         # Local overrides (gitignored)
│
├── Dockerfile                   # Multi-stage build
├── docker-compose.yml           # Full stack: server + ingest
├── .dockerignore                # Exclude db/, .env, .git, etc.
│
├── books/                       # Default local books dir (overridden by ENV)
│   ├── inbox/                   # Drop new books here
│   └── .manifest.json           # Auto-generated: tracks file hashes, metadata
│
├── db/                          # ChromaDB persistent storage (gitignored)
│
├── src/
│   └── library_mcp/
│       ├── __init__.py
│       ├── server.py            # MCP server — tool definitions and startup
│       ├── ingest.py            # Book ingestion pipeline
│       ├── extract.py           # Text extraction (PDF, EPUB, MOBI)
│       ├── chunker.py           # Text chunking logic
│       ├── embeddings.py        # Embedding generation (pluggable provider)
│       ├── db.py                # ChromaDB wrapper / query interface
│       ├── manifest.py          # Manifest management (hashing, diffing)
│       └── models.py            # Pydantic models for metadata, config
│
├── cli.py                       # CLI entry point for ingest commands
│
├── config.yaml                  # User-editable configuration
│
├── claude-code-config.json      # MCP server config for Claude Code
│
└── tests/
    ├── test_extract.py
    ├── test_chunker.py
    ├── test_ingest.py
    └── test_search.py
```

---

## Core Components

### 1. Text Extraction (`extract.py`)

Extract raw text from three file formats. Preserve chapter/section structure where possible.

**PDF:**
- Primary: `pymupdf` (fitz) — fast, handles most PDFs well
- Fallback: `pdfplumber` for scanned/image-heavy PDFs with OCR via `pytesseract`
- Extract page numbers and map them to chunks

**EPUB:**
- Use `ebooklib` to parse EPUB structure
- Extract chapter boundaries from the table of contents / spine
- Strip HTML tags, preserve paragraph structure

**MOBI:**
- Convert MOBI → EPUB using `mobi` library or Calibre's `ebook-convert` CLI
- Then process as EPUB

**Output format per book:**
```python
@dataclass
class ExtractedBook:
    title: str
    author: str
    format: str  # pdf, epub, mobi
    sections: list[Section]

@dataclass
class Section:
    title: str          # Chapter or section name
    text: str           # Full text content
    page_start: int | None
    page_end: int | None
```

### 2. Text Chunking (`chunker.py`)

Split extracted text into embedding-friendly chunks.

**Strategy: Semantic chunking with overlap**
- Target chunk size: 500–800 tokens
- Overlap: 50–100 tokens (maintains context across boundaries)
- Respect paragraph boundaries — never split mid-sentence
- Prefer splitting at section/chapter boundaries when possible
- If a section is shorter than the target chunk size, keep it as one chunk

**Each chunk carries metadata:**
```python
@dataclass
class Chunk:
    text: str
    book_title: str
    author: str
    section_title: str
    chunk_index: int          # Sequential within the book
    page_number: int | None
    token_count: int
```

### 3. Embedding Generation (`embeddings.py`)

Generate vector embeddings for each chunk. Make the provider pluggable.

**Default: Sentence Transformers (local, free, no API key)**
- Model: `all-MiniLM-L6-v2` (fast, good quality, 384 dimensions)
- Runs entirely locally — no network dependency
- Alternative for better quality: `all-mpnet-base-v2` (768 dimensions, slower)

**Optional: OpenAI embeddings**
- Model: `text-embedding-3-small`
- Requires `OPENAI_API_KEY` in `.env`
- Better semantic quality, costs money

**Config in `config.yaml`:**
```yaml
embeddings:
  provider: "local"          # "local" or "openai"
  model: "all-MiniLM-L6-v2" # or "text-embedding-3-small"
```

### 4. Vector Database (`db.py`)

ChromaDB in persistent file-based mode.

**Why ChromaDB:**
- Zero infrastructure — just files on disk
- Built-in embedding function support
- Metadata filtering (search within a specific book)
- Simple Python API

**Collection schema:**
```python
collection = client.get_or_create_collection(
    name="library",
    metadata={"hnsw:space": "cosine"}
)

# Adding a chunk:
collection.add(
    ids=[f"{book_hash}_{chunk_index}"],
    documents=[chunk.text],
    metadatas=[{
        "book_title": chunk.book_title,
        "author": chunk.author,
        "section_title": chunk.section_title,
        "chunk_index": chunk.chunk_index,
        "page_number": chunk.page_number,
        "file_hash": file_hash,
        "version_tag": version_tag,
        "ingested_at": datetime.utcnow().isoformat()
    }]
)
```

**Key query patterns:**
```python
# Semantic search across all books
results = collection.query(
    query_texts=["form validation best practices"],
    n_results=10
)

# Search within a specific book
results = collection.query(
    query_texts=["error handling"],
    n_results=5,
    where={"book_title": "Clean Code"}
)
```

### 5. Manifest / Change Detection (`manifest.py`)

Track what's been ingested to support incremental reindexing.

**Manifest structure (`.manifest.json`):**
```json
{
  "books": {
    "clean-code.pdf": {
      "file_hash": "sha256:abc123...",
      "title": "Clean Code",
      "author": "Robert C. Martin",
      "chunk_count": 342,
      "version_tag": null,
      "ingested_at": "2025-04-03T10:30:00Z",
      "file_size_bytes": 4521390
    }
  },
  "last_full_ingest": "2025-04-03T10:30:00Z",
  "db_path": "./db",
  "embedding_model": "all-MiniLM-L6-v2"
}
```

**Reindex logic:**
1. Scan all files in `books/inbox/`
2. Compute SHA-256 hash for each file
3. Compare against manifest:
   - **New file** (not in manifest) → extract, chunk, embed, add to DB
   - **Changed file** (hash differs) → delete old chunks from DB by `file_hash`, re-ingest
   - **Removed file** (in manifest but not on disk) → purge chunks from DB, remove from manifest
   - **Unchanged file** (hash matches) → skip
4. Write updated manifest
5. **Embedding model change detection**: if `config.yaml` embedding model differs from manifest's `embedding_model`, prompt for full rebuild (all embeddings are invalidated)

### 6. MCP Server (`server.py`)

The MCP server exposes tools over stdio transport for Claude Code.

**Tools:**

#### `list_books()`
Returns all indexed books with metadata.
```python
@server.tool()
def list_books() -> list[dict]:
    """List all books in the knowledge base with their titles,
    authors, topics, and chunk counts. Use this to understand
    what reference material is available before searching."""
    manifest = load_manifest()
    return [
        {
            "title": book["title"],
            "author": book["author"],
            "chunk_count": book["chunk_count"],
            "version_tag": book["version_tag"],
            "ingested_at": book["ingested_at"]
        }
        for book in manifest["books"].values()
    ]
```

#### `search_library(query, book_filter?, top_k?)`
Semantic search across the entire library or a specific book.
```python
@server.tool()
def search_library(
    query: str,
    book_filter: str | None = None,
    top_k: int = 5
) -> list[dict]:
    """Search all reference books for passages relevant to the query.
    Returns the most semantically similar text chunks with source info.
    Use book_filter to restrict search to a specific book title.
    Use this tool whenever you need best practices, patterns,
    or authoritative guidance on a topic covered by the library."""
    where = {"book_title": book_filter} if book_filter else None
    results = collection.query(
        query_texts=[query],
        n_results=top_k,
        where=where
    )
    return [
        {
            "text": doc,
            "book_title": meta["book_title"],
            "author": meta["author"],
            "section": meta["section_title"],
            "page": meta.get("page_number"),
            "relevance_score": round(1 - dist, 3)
        }
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        )
    ]
```

#### `get_chapter(book_title, section_title)`
Retrieve a full chapter or section for deeper reading.
```python
@server.tool()
def get_chapter(
    book_title: str,
    section_title: str
) -> list[dict]:
    """Retrieve all chunks from a specific chapter/section of a book.
    Use this when you need deeper context from a section that
    search_library identified as relevant. Results are returned
    in reading order."""
    results = collection.get(
        where={
            "$and": [
                {"book_title": book_title},
                {"section_title": section_title}
            ]
        }
    )
    # Sort by chunk_index for reading order
    paired = sorted(
        zip(results["documents"], results["metadatas"]),
        key=lambda x: x[1]["chunk_index"]
    )
    return [
        {"text": doc, "chunk_index": meta["chunk_index"]}
        for doc, meta in paired
    ]
```

---

## CLI Interface (`cli.py`)

```bash
# Ingest: scan inbox, process new/changed books
library ingest

# Ingest with forced full rebuild
library ingest --full

# Ingest a specific file with a version tag
library ingest --file "clean-code-3rd-ed.pdf" --tag "3rd-edition"

# List indexed books
library list

# Search from the command line (for testing)
library search "dependency injection patterns" --top-k 5

# Search within a specific book
library search "error handling" --book "Clean Code" --top-k 3

# Remove a book from the index
library remove "Old Book Title"

# Show index stats (total chunks, DB size, etc.)
library stats

# Rebuild DB from scratch (resets everything)
library rebuild
```

Use `click` or `typer` for the CLI framework.

---

## Configuration (`config.yaml`)

All values below can be overridden by environment variables (ENV takes precedence). This is how Docker and `.env` control the runtime without editing this file.

```yaml
# Library MCP Configuration

library:
  books_dir: "./books/inbox"        # Where to scan for books
  manifest_path: "./books/.manifest.json"
  db_path: "./db"

chunking:
  target_tokens: 600                # Target chunk size in tokens
  max_tokens: 800                   # Hard max per chunk
  overlap_tokens: 75                # Token overlap between chunks
  respect_paragraphs: true          # Never split mid-paragraph
  respect_sections: true            # Prefer section boundaries

embeddings:
  provider: "local"                 # "local" or "openai"
  model: "all-MiniLM-L6-v2"        # Local model name or OpenAI model
  batch_size: 64                    # Chunks per embedding batch

search:
  default_top_k: 5                  # Default results per search
  max_top_k: 20                     # Maximum allowed results
  relevance_threshold: 0.3          # Minimum similarity score (0-1)

server:
  name: "library-mcp"
  transport: "stdio"                # stdio for Claude Code
```

---

## Claude Code Integration

### MCP Config — Native Mode (`claude-code-config.json`)

For running without Docker (bare Python install):

```json
{
  "mcpServers": {
    "library-mcp": {
      "command": "python",
      "args": ["-m", "library_mcp.server"],
      "cwd": "/path/to/library-mcp",
      "env": {
        "OPENAI_API_KEY": ""
      }
    }
  }
}
```

Claude Code will auto-start this server and make the three tools available in every conversation within the project. See the Docker section below for the Docker-based config alternative.

---

## Docker Setup

The entire system runs as a Docker container. Books and the vector DB live on mounted volumes so nothing is lost when the container restarts.

### Environment Variables (`.env.example`)

```env
# === REQUIRED ===
BOOKS_PATH=./books/inbox              # Host path to your book files
CHROMA_PATH=./db                      # Host path for persistent ChromaDB storage
MANIFEST_PATH=./books/.manifest.json  # Host path for manifest file

# === OPTIONAL ===
EMBEDDING_PROVIDER=local              # "local" or "openai"
EMBEDDING_MODEL=all-MiniLM-L6-v2     # Model name (local or OpenAI)
OPENAI_API_KEY=                       # Required only if EMBEDDING_PROVIDER=openai
CHUNK_TARGET_TOKENS=600               # Target chunk size
CHUNK_OVERLAP_TOKENS=75               # Overlap between chunks
SEARCH_DEFAULT_TOP_K=5                # Default search results
LOG_LEVEL=info                        # debug, info, warning, error
```

All `config.yaml` values should be overridable by ENV vars. ENV takes precedence over config file. This lets you run the same image with different book libraries by just changing `BOOKS_PATH`.

### Dockerfile

```dockerfile
# ---- Stage 1: Build ----
FROM python:3.12-slim AS builder

WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir build && \
    pip install --no-cache-dir .

# ---- Stage 2: Runtime ----
FROM python:3.12-slim AS runtime

# System deps for PDF/OCR extraction
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY src/ ./src/
COPY cli.py config.yaml ./

# Pre-download the default embedding model into the image
# so first run doesn't trigger a large download
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Volume mount points
VOLUME ["/data/books", "/data/db", "/data/manifest"]

ENV BOOKS_PATH=/data/books
ENV CHROMA_PATH=/data/db
ENV MANIFEST_PATH=/data/manifest/.manifest.json

# Default: run MCP server over stdio
ENTRYPOINT ["python", "-m", "library_mcp.server"]
```

### docker-compose.yml

```yaml
services:
  library-mcp:
    build: .
    container_name: library-mcp
    env_file: .env
    volumes:
      - ${BOOKS_PATH:-./books/inbox}:/data/books:ro    # Books are read-only
      - ${CHROMA_PATH:-./db}:/data/db                  # DB persists here
      - ${MANIFEST_PATH:-./books}:/data/manifest        # Manifest persists here
    environment:
      - EMBEDDING_PROVIDER=${EMBEDDING_PROVIDER:-local}
      - EMBEDDING_MODEL=${EMBEDDING_MODEL:-all-MiniLM-L6-v2}
      - OPENAI_API_KEY=${OPENAI_API_KEY:-}
      - LOG_LEVEL=${LOG_LEVEL:-info}
    # Default: MCP server (stdio). Override for CLI commands.
    # entrypoint is set in Dockerfile

  # One-shot ingest service — run manually
  ingest:
    build: .
    container_name: library-ingest
    env_file: .env
    volumes:
      - ${BOOKS_PATH:-./books/inbox}:/data/books:ro
      - ${CHROMA_PATH:-./db}:/data/db
      - ${MANIFEST_PATH:-./books}:/data/manifest
    environment:
      - EMBEDDING_PROVIDER=${EMBEDDING_PROVIDER:-local}
      - EMBEDDING_MODEL=${EMBEDDING_MODEL:-all-MiniLM-L6-v2}
      - OPENAI_API_KEY=${OPENAI_API_KEY:-}
      - LOG_LEVEL=${LOG_LEVEL:-info}
    entrypoint: ["python", "cli.py", "ingest"]
    profiles: ["cli"]                # Only runs when explicitly called
```

### Docker Usage

```bash
# Build the image
docker compose build

# Ingest books (one-shot, then exits)
docker compose run --rm ingest

# Ingest with full rebuild
docker compose run --rm ingest --full

# Ingest a specific file
docker compose run --rm ingest --file "clean-code.pdf" --tag "3rd-edition"

# Run other CLI commands
docker compose run --rm ingest list
docker compose run --rm ingest search "error handling" --top-k 5
docker compose run --rm ingest stats

# Start the MCP server (for Claude Code)
docker compose up library-mcp

# Tear everything down (volumes persist)
docker compose down

# Nuclear option: tear down and delete the DB
docker compose down -v
```

### Claude Code Integration (Docker mode)

When running via Docker, update the MCP config to launch via `docker compose`:

```json
{
  "mcpServers": {
    "library-mcp": {
      "command": "docker",
      "args": ["compose", "-f", "/path/to/library-mcp/docker-compose.yml", "run", "--rm", "-T", "library-mcp"],
      "env": {
        "OPENAI_API_KEY": ""
      }
    }
  }
}
```

The `-T` flag disables pseudo-TTY allocation, which is required for stdio transport over Docker.

### .dockerignore

```
db/
.env
.git
.gitignore
__pycache__
*.pyc
books/inbox/*
tests/
.venv/
```

### Multi-Machine Workflow with Docker

1. Push repo to GitHub (books and db are gitignored)
2. On new machine: `git clone` → `cp .env.example .env`
3. Edit `.env` to point `BOOKS_PATH` at your local books folder (iCloud, Dropbox, wherever)
4. `docker compose build`
5. `docker compose run --rm ingest`
6. `docker compose up library-mcp`
7. Done — same image, different books, different machine

---

## Dependencies

```
# Core
mcp[cli]                  # MCP SDK for Python
chromadb                  # Vector database
sentence-transformers     # Local embeddings
pydantic                  # Data models and config

# Text extraction
pymupdf                   # PDF extraction
pdfplumber                # PDF fallback
ebooklib                  # EPUB parsing
mobi                      # MOBI → EPUB conversion
beautifulsoup4            # HTML stripping from EPUB
pytesseract               # OCR fallback for scanned PDFs

# CLI
typer                     # CLI framework
rich                      # Terminal output formatting

# Utilities
tiktoken                  # Token counting (for chunking)
pyyaml                    # Config file parsing
python-dotenv             # Environment variables

# Optional
openai                    # OpenAI embeddings (if not using local)
watchdog                  # File watcher for auto-ingest (future)
```

---

## Implementation Order

Build in this order. Each step is independently testable.

### Phase 1: Core Pipeline
1. **`models.py`** — Define Pydantic models for `ExtractedBook`, `Section`, `Chunk`, `Config`
2. **`extract.py`** — Text extraction for PDF, EPUB, MOBI. Test with one file of each type
3. **`chunker.py`** — Implement chunking with overlap and paragraph respect. Test with extracted text
4. **`embeddings.py`** — Embedding generation with local model. Test that vectors have correct dimensions
5. **`db.py`** — ChromaDB wrapper: add, query, delete by hash. Test round-trip: add chunks → query → verify results
6. **`manifest.py`** — Hash computation, manifest CRUD, diff logic. Test change detection with modified files

### Phase 2: Ingest Pipeline
7. **`ingest.py`** — Orchestrate: scan → diff → extract → chunk → embed → store → update manifest
8. **`cli.py`** — Wire up CLI commands: `ingest`, `list`, `search`, `remove`, `stats`, `rebuild`
9. Test full pipeline: drop 2-3 books in inbox → `library ingest` → `library search`

### Phase 3: MCP Server
10. **`server.py`** — Implement three MCP tools using the db module
11. **`claude-code-config.json`** — Wire up to Claude Code
12. End-to-end test: ask Claude Code a question that requires book knowledge → verify it calls the tools

### Phase 4: Docker
13. **`Dockerfile`** — Multi-stage build, pre-bake embedding model
14. **`docker-compose.yml`** — Services for server and one-shot ingest
15. **`.env.example`** — Document all environment variables
16. **`.dockerignore`** — Exclude db, books, env, git
17. Test: `docker compose build` → `docker compose run --rm ingest` → `docker compose up library-mcp`
18. Test Claude Code integration with Docker-based MCP config

### Phase 5: Polish
19. Add logging throughout (use `rich` for CLI, standard logging for server)
20. Error handling: corrupt files, empty extractions, DB connection issues
21. Progress bars for ingest (large books take time)
22. Write tests

---

## Edge Cases and Design Decisions

**Scanned PDFs:** Detect pages with little or no extractable text. Fall back to OCR via `pytesseract`. Flag these books in the manifest as `ocr: true` since text quality may be lower.

**Very large books (1000+ pages):** Process in streaming fashion — extract, chunk, and embed one section at a time rather than loading the entire book into memory.

**Duplicate content:** If the same book exists in multiple formats (PDF + EPUB), the manifest should detect this by title/author and warn. Let the user decide which to keep.

**Embedding model changes:** If the user switches embedding models in config, all existing vectors are invalidated. The ingest command should detect this (model name stored in manifest) and prompt for a full rebuild.

**Chunk ID stability:** Chunk IDs are derived from `file_hash + chunk_index`. This means a re-ingested book gets entirely new chunk IDs, which is correct — old IDs are purged, new ones added.

**Concurrent access:** ChromaDB handles concurrent reads fine. Writes during ingest should not run while the MCP server is actively querying. For v1, this is fine — ingest is a manual CLI step. Future: add a file lock.

**Docker volume permissions:** The container writes to `/data/db` and `/data/manifest`. Ensure the host directories exist and are writable by the container's user. The books volume is mounted read-only — the container never modifies source files.

**Container resource limits:** Embedding generation and OCR can be CPU/memory intensive. For large libraries (50+ books), consider setting memory limits in docker-compose (`mem_limit: 4g`) and monitoring during ingest. The pre-baked embedding model in the image avoids a large download on first run.

**Version management:** When `--tag` is used during ingest, the version tag is stored in chunk metadata. Claude can see which edition a passage comes from. Multiple versions of the same book CAN coexist in the DB if desired — use `library ingest --file book.pdf --tag "2nd-edition"` without removing the old version.

---

## Future Enhancements (Out of Scope for v1)

- **File watcher:** Auto-ingest when books are added to `inbox/` using `watchdog`
- **Web UI:** Simple local web interface showing indexed books, search testing, chunk previews
- **Cross-reference tool:** A fourth MCP tool that finds connections between books on a topic
- **Highlight/annotation import:** Ingest Kindle highlights or PDF annotations as high-priority chunks
- **Summarization:** Pre-generate chapter summaries during ingest, store as special chunks with high retrieval priority
- **Multi-collection support:** Separate collections for different projects or topics

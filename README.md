# BookWorm

A local MCP server that turns your ebook library into a searchable knowledge base. Drop books into a folder, run ingest, and Claude Code automatically searches relevant passages when it needs reference material.

Supports PDF, EPUB, MOBI, Markdown, plain text, and HTML. Runs entirely locally -- no external API required.

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

**Supported formats:** EPUB, PDF, MOBI, Markdown (.md), plain text (.txt), HTML (.html/.htm)

**Duplicate formats:** If you have the same book as `clean-code.pdf`, `clean-code.epub`, and `clean-code.mobi`, only add **one** to the inbox. Indexing the same book in multiple formats produces duplicate search results.

When choosing which format to keep, prefer in this order:

| Priority | Format | Why |
|----------|--------|-----|
| 1st | **EPUB** | Cleanest text extraction, chapter boundaries from TOC, smallest files |
| 2nd | **PDF** | Good with TOC-based chapter detection; OCR fallback for scanned pages |
| 3rd | **MOBI** | Gets converted to EPUB internally -- if you have the EPUB, use that instead |
| 4th | **Markdown** | Split on heading levels (# ## ###) |
| 5th | **HTML** | Split on heading elements (h1/h2/h3), extracts title and author meta |
| 6th | **TXT** | Detects chapter headings or falls back to fixed-size sections |

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

**Restart the MCP server** by running `/mcp` in Claude Code and selecting the bookworm server to restart, or start a new session.

### 6. Install the Plugin (Skills & Slash Commands)

BookWorm includes a Claude Code plugin with slash commands for interactive library use.

**Quick start (load for one session only):**

```bash
claude --plugin-dir /path/to/BookWorm
```

**Permanent install** — add these two entries to `~/.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "bookworm-local": {
      "source": {
        "source": "directory",
        "path": "/absolute/path/to/BookWorm"
      }
    }
  },
  "enabledPlugins": {
    "bookworm@bookworm-local": true
  }
}
```

Replace `/absolute/path/to/BookWorm` with the actual path on your machine. Start a new Claude Code session to pick up the plugin (a simple restart is all it takes — no separate MCP restart needed either, since both the MCP server and plugin load on session start).

### 7. Auto-Allow Bookworm Tools (optional)

By default, Claude Code will prompt for permission each time it calls a Bookworm MCP tool. Since these are all read-only operations against your local library, you can auto-allow them. Add this to `~/.claude/settings.json`:

```json
{
  "permissions": {
    "allow": [
      "mcp__bookworm__list_books",
      "mcp__bookworm__search_library",
      "mcp__bookworm__get_chapter",
      "mcp__bookworm__list_sections",
      "mcp__bookworm__get_stats",
      "mcp__bookworm__ingest_path",
      "mcp__bookworm__remove_book"
    ]
  }
}
```

All three snippets (MCP server, plugin registration, and permissions) are available in `claude-code-config.json` for easy reference.

This makes the following slash commands available:

| Command | What it does |
|---------|--------------|
| `/bw <query>` | Smart search — groups results by book, auto-drills into top matches, suggests follow-ups |
| `/bw-research <topic>` | Deep multi-pass research — 3-5 query reformulations, chapter retrieval, synthesized report with citations |
| `/bw-read <book>` | Browse a book — shows TOC, navigate chapters, get summaries |
| `/bw-ingest [path]` | Interactive ingestion — shows pending books, ingests, confirms results |

There's also a **model-invoked skill** (`bookworm-assist`) that fires automatically when your conversation involves topics covered by your library (Elixir, Phoenix, Vim, etc). No slash command needed — Claude uses it on its own.

---

## MCP Tools

These are the tools Claude can call autonomously during a session:

| Tool | What it does |
|------|--------------|
| `list_books()` | Shows what's in the library |
| `search_library(query, book_filter?, top_k?)` | Semantic search across all books |
| `get_chapter(book_title, section_title)` | Retrieves a full chapter for deeper reading |
| `list_sections(book_title)` | Returns the table of contents for a book (section names, chunk counts, page numbers) |
| `get_stats()` | Library statistics: book count, chunks, storage size, pending files |
| `remove_book(book_title)` | Remove a book from the index by title |
| `ingest_path(path, file?, tag?)` | Ingest books mid-session from any directory |

Claude calls these on its own when it thinks your library has relevant material. You can also ask directly -- e.g. "search my books for GenServer patterns" or "ingest the books at ~/Downloads/elixir-books".

---

## Common Workflows

**From the terminal (CLI):**

```bash
bookworm ingest                              # Scan inbox, process new/changed books
bookworm ingest --path ~/Books/elixir        # Ingest from a specific directory
bookworm list                                # See what's indexed
bookworm search "pattern matching"           # Quick search
bookworm toc "Programming Phoenix ≥ 1.4"    # Show table of contents for a book
bookworm status                              # Indexed vs pending, DB size, health info
bookworm stats                               # Chunk counts, DB size, model info
```

**From a Claude Code session (MCP tools):**

- "What books do I have indexed?" -- calls `list_books`
- "Search my library for Ecto multi-tenancy" -- calls `search_library`
- "Show me the chapters in that Phoenix book" -- calls `list_sections`
- "Pull up the chapter on GenServers from that Elixir book" -- calls `get_chapter`
- "Ingest the PDFs at ~/Downloads/phoenix-books" -- calls `ingest_path`
- "How big is my library?" -- calls `get_stats`
- "Remove that outdated Vim book" -- calls `remove_book`

**From Claude Code slash commands (plugin):**

- `/bw GenServer patterns` -- smart search with auto-drill
- `/bw-research "testing in Elixir"` -- deep research across multiple books
- `/bw-read "Practical Vim"` -- browse a book's TOC and chapters
- `/bw-ingest` -- see what's pending and ingest interactively

The MCP tools, CLI, and slash commands all share the same database, so books ingested from any side are immediately available to all.

---

## Keep It Updated

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
  allowed_formats: ["pdf", "epub", "mobi", "md", "txt", "html"]

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
| `ALLOWED_FORMATS` | `pdf,epub,mobi,md,txt,html` | Comma-separated list of formats to index |
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
bookworm toc "Book Title"                    # Show table of contents for a book
bookworm status                              # Indexed vs pending, health dashboard
bookworm remove "Book Title"                 # Remove from index by title
bookworm stats                               # Chunk counts, DB size, model info
bookworm rebuild                             # Wipe and rebuild (with confirmation)
```

---

## How It Works

```
Books (PDF/EPUB/MOBI/MD/TXT/HTML)
  -> Extract text (pymupdf, ebooklib, BeautifulSoup, OCR fallback)
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
│   ├── server.py          # MCP server -- tool definitions (7 tools)
│   ├── ingest.py          # Ingestion pipeline orchestrator
│   ├── extract.py         # PDF, EPUB, MOBI, MD, TXT, HTML text extraction
│   ├── chunker.py         # Text chunking with overlap
│   ├── embeddings.py      # Pluggable embedding providers
│   ├── db.py              # ChromaDB wrapper
│   ├── manifest.py        # Change detection and tracking
│   ├── models.py          # Pydantic data models
│   ├── config.py          # Config loading (YAML + ENV)
│   ├── cli.py             # Typer CLI commands
│   └── logging_config.py  # Centralized logging
├── skills/                # Claude Code plugin skills
│   ├── bw/                # /bw — smart library search
│   ├── bw-research/       # /bw-research — deep multi-pass research
│   ├── bw-read/           # /bw-read — browse and read a book
│   ├── bw-ingest/         # /bw-ingest — interactive ingestion
│   └── bookworm-assist/   # Auto-invoked when topics match library
├── .claude-plugin/        # Claude Code plugin metadata
├── books/inbox/           # Drop books here
├── tests/                 # Test suite (79 tests)
├── config.yaml            # Default configuration
└── claude-code-config.json # MCP config template
```

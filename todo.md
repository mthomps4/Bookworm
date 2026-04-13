# Bookworm Improvement Punchlist

## Phase 1 — Core MCP Tools (highest leverage)

- [x] `list_sections(book_title)` — Return TOC/section titles for a book so Claude can navigate before calling `get_chapter`
- [x] `remove_book(book_title)` — Expose existing CLI remove as MCP tool
- [x] `get_stats()` — Expose existing CLI stats as MCP tool
- [ ] `search_by_metadata(author?, tag?, format?)` — Filter library by metadata, not just semantic search
- [ ] `get_page_range(book_title, start_page, end_page)` — Retrieve content by page number
- [ ] `multi_search(queries[], book_filter?, top_k?)` — Batch multiple queries in one round-trip

## Phase 2 — Skills (slash commands for Claude Code)

- [x] `/bw` — Smart search: search library, group results by book, auto-drill into promising chapters
- [x] `/bw-research <topic>` — Multi-pass deep research: reformulate queries, gather chapters, synthesize with citations
- [x] `/bw-ingest` — Interactive ingestion: show pending books, pick, ingest, confirm
- [x] `/bw-read <book>` — Guided reading: show TOC, navigate chapters, provide summaries
- [x] `bookworm-assist` — Model-invoked skill: auto-searches library when conversation topics match indexed books
- [ ] `/bw-cite` — Search + format results as proper citations (title, author, chapter, page)
- [ ] `/bw-compare <topic>` — Compare coverage of a topic across multiple books

## Phase 3 — Search Quality

- [ ] Hybrid search (BM25 + semantic) — Add keyword precision alongside semantic similarity (e.g. SQLite FTS5 or rank_bm25)
- [ ] Cross-encoder reranking — Rerank initial results with `cross-encoder/ms-marco-MiniLM-L-6-v2`
- [ ] Cached section summaries — Pre-compute 2-3 sentence summary per section at ingest time, store in manifest
- [ ] Configurable token budget — "give me up to N tokens" instead of fixed top_k

## Phase 4 — Format Support

- [x] Plain text (.txt)
- [x] HTML (.html/.htm)
- [ ] reStructuredText (.rst)
- [ ] AsciiDoc (.adoc)
- [ ] Code files (.ex, .py, .js, etc.) — index annotated source as searchable reference

## Phase 5 — CLI Enhancements

- [x] `bookworm toc <book_title>` — Print table of contents
- [x] `bookworm status` — Dashboard: indexed vs pending, DB size, last ingest
- [ ] `bookworm config [show|set|reset]` — View/edit config without touching YAML
- [ ] `bookworm import <url>` — Download and ingest from URL
- [ ] `bookworm export <book> [--format md|json]` — Export extracted text
- [ ] `bookworm validate` — Check DB integrity, find orphaned chunks
- [ ] `bookworm tag <book> <tag>` — Add/update version tags post-ingest

## Phase 6 — Architecture

- [ ] MCP Resources — Expose books/sections as MCP Resources for native browsing
- [ ] Streaming for large chapter results
- [ ] Collection/shelf support — Group books by topic for scoped search
- [ ] Search session context — Track what's been retrieved to avoid re-fetching

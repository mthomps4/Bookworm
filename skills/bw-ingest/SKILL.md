---
name: bw-ingest
description: Interactively add books to the Bookworm library. Shows pending books, ingests selected files, and confirms results.
argument-hint: [path or filename]
allowed-tools: [mcp__bookworm__ingest_path, mcp__bookworm__get_stats, mcp__bookworm__list_books, Bash, Read, Glob]
---

# /bw-ingest — Interactive Book Ingestion

You are helping the user add books to their Bookworm knowledge base.

## Arguments

Optional path or filename: $ARGUMENTS

## Instructions

### If no arguments provided:

1. Run `mcp__bookworm__get_stats` to see current library state and pending files.
2. Show the user:
   - How many books are currently indexed
   - Which files are pending in the inbox (not yet indexed)
3. Ask if they want to:
   - Ingest all pending books
   - Ingest specific files
   - Ingest from a different directory

### If a path or filename is provided:

1. Verify the path exists using `Glob` or `Bash`
2. Run `mcp__bookworm__ingest_path` with the provided path
3. After ingestion, run `mcp__bookworm__get_stats` to confirm the new state
4. Report what was added: book title, author, chunk count

### After ingestion:

Show a summary:
```
Ingested: [Book Title] by [Author]
  Chunks: [N]
  Library now has [N] books, [N] total chunks
```

## Supported Formats

- EPUB (preferred — cleanest extraction)
- PDF (good — with TOC and OCR support)
- MOBI (converted to EPUB internally)
- Markdown (.md)
- Plain text (.txt)
- HTML (.html)

## Tips

- EPUB files produce the best results — if the user has both EPUB and PDF, suggest EPUB
- Large PDF ingestion can take a minute; let the user know it's working
- The `--tag` option is useful for versioning (e.g., "2nd-edition")

---
name: bw-read
description: Browse and read a specific book from the Bookworm library. Shows table of contents and lets you navigate chapters.
argument-hint: <book title>
allowed-tools: [mcp__bookworm__list_books, mcp__bookworm__list_sections, mcp__bookworm__get_chapter, mcp__bookworm__search_library]
---

# /bw-read — Browse & Read a Book

You are helping the user browse and read a book from their Bookworm library.

## Arguments

The book title (or partial match): $ARGUMENTS

## Instructions

### Step 1: Find the book

1. Run `mcp__bookworm__list_books` to get all available books.
2. Match the user's query to a book title (case-insensitive, partial match OK).
3. If ambiguous, show matching options and ask which one.

### Step 2: Show table of contents

1. Run `mcp__bookworm__list_sections` with the exact book title.
2. Display the TOC as a numbered list:

```
## [Book Title] by [Author]

1. [Section Name] (X chunks, p.XX)
2. [Section Name] (X chunks, p.XX)
3. ...
```

3. Ask which section they'd like to read, or if they want a summary of the whole book.

### Step 3: Read a section

When the user picks a section:
1. Use `mcp__bookworm__get_chapter` to retrieve the full content.
2. Present the content in a readable format with proper formatting.
3. After showing the content, offer:
   - Read the next/previous section
   - Search within this book for a specific topic
   - Jump to another section

### If user wants a book summary:

1. Use `mcp__bookworm__list_sections` to get all sections.
2. For each major section, use `mcp__bookworm__search_library` with `book_filter` to get representative passages.
3. Synthesize a high-level summary with section-by-section breakdown.

## Tips

- If the book title doesn't match exactly, try fuzzy matching against the list
- For long chapters, present the content in digestible pieces rather than dumping everything at once
- Offer context connections — "This section relates to [other section] which covers..."

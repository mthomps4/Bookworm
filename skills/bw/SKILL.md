---
name: bw
description: Search the Bookworm ebook library for relevant passages and guidance. Use when you need to look up best practices, patterns, or reference material from indexed technical books.
argument-hint: <search query>
allowed-tools: [mcp__bookworm__search_library, mcp__bookworm__list_books, mcp__bookworm__get_chapter, mcp__bookworm__list_sections]
---

# /bw — Smart Library Search

You are performing a search of the user's personal ebook library using the Bookworm MCP tools.

## Arguments

The user's search query: $ARGUMENTS

## Instructions

1. **Search the library** using `mcp__bookworm__search_library` with the user's query. Use `top_k: 8` for broader coverage.

2. **Group and present results** by book. For each book that appears in results:
   - Show the book title and author
   - Show the section name and relevance score
   - Show a concise excerpt (2-3 key sentences from each result, not the full chunk)

3. **Auto-drill into the best match**: If the top result has a relevance score >= 0.6, automatically call `mcp__bookworm__get_chapter` to retrieve the full section for deeper context. Summarize the key insights from that chapter.

4. **Offer next steps**: After presenting results, suggest:
   - Other sections worth reading (use `mcp__bookworm__list_sections` if a specific book looks promising)
   - Refined queries if results seem off-target
   - Related topics the user might want to explore

## Output Format

Present results in a scannable format:

```
### [Book Title] by [Author]

**[Section Name]** (score: 0.XX)
> Key excerpt from the passage...

**[Section Name]** (score: 0.XX)
> Key excerpt from the passage...
```

If no results are found, run `mcp__bookworm__list_books` to show what's available and suggest alternative queries.

## Tips

- If the query is vague, try 2-3 reformulations to catch different angles
- For code-related queries, search for both the concept and the specific function/module name
- If the user mentions a specific book, use `book_filter` to scope the search

---
name: bw-research
description: Deep multi-pass research across the Bookworm ebook library. Use when you need a thorough literature review, synthesis across multiple books, or comprehensive coverage of a topic.
argument-hint: <research topic>
allowed-tools: [mcp__bookworm__search_library, mcp__bookworm__list_books, mcp__bookworm__get_chapter, mcp__bookworm__list_sections, mcp__bookworm__get_stats, Agent]
---

# /bw-research — Deep Library Research

You are conducting deep research across the user's personal ebook library using Bookworm. This is a multi-pass process that synthesizes knowledge from multiple books and sections.

## Arguments

The research topic: $ARGUMENTS

## Research Process

### Phase 1: Reconnaissance

1. Run `mcp__bookworm__list_books` to understand the available library.
2. Identify which books are most likely to cover the topic.

### Phase 2: Multi-Query Search

Generate 3-5 different search queries that approach the topic from different angles:

- **Direct query**: The topic as stated
- **Conceptual query**: The underlying concept or principle
- **Practical query**: "how to" or implementation-focused angle
- **Related concepts**: Adjacent topics that might provide context
- **Specific terms**: Technical terms, function names, or patterns related to the topic

Run `mcp__bookworm__search_library` for each query with `top_k: 6`. Collect all unique results.

### Phase 3: Deep Dive

For the top 3-5 most relevant sections found across all queries:
1. Use `mcp__bookworm__list_sections` to see the TOC of relevant books
2. Use `mcp__bookworm__get_chapter` to retrieve full chapter content
3. Extract key insights, patterns, code examples, and recommendations

### Phase 4: Synthesis

Produce a structured research report:

```markdown
## Research: [Topic]

### Summary
[2-3 sentence overview of what the library says about this topic]

### Key Findings

#### [Finding 1 — theme or concept]
[Synthesis of what multiple sources say]
— *[Book Title]*, [Chapter] (p.XX)
— *[Book Title]*, [Chapter] (p.XX)

#### [Finding 2 — theme or concept]
...

### Code Examples
[If applicable, include the most relevant code examples found]

### Recommendations
[Actionable takeaways based on what the sources recommend]

### Sources Consulted
- *[Book Title]* by [Author] — [Sections read]
- *[Book Title]* by [Author] — [Sections read]
```

## Guidelines

- **Cite sources**: Always attribute findings to specific books and sections
- **Synthesize, don't summarize**: Compare what different authors say about the same concept. Note agreements and disagreements.
- **Prioritize practical advice**: Focus on actionable patterns and code examples over theory
- **Be honest about coverage gaps**: If the library doesn't cover an aspect of the topic, say so
- **Parallel queries**: Use the Agent tool to run multiple searches in parallel for speed when the queries are independent

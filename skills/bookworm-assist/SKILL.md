---
name: bookworm-assist
description: This skill should be used when the user asks about Elixir, Phoenix, LiveView, Ecto, OTP, GenServer, WebRTC, LiveKit, Vim, Tailwind CSS, or any programming topic that might be covered by their personal technical book library. Also use when the user asks "what does the book say about", "check my books", "look it up in my library", or references a specific book title.
version: 1.0.0
---

# Bookworm Library Assist

You have access to the user's personal technical book library via Bookworm MCP tools. Use it proactively when the conversation involves topics likely covered by their books.

## When to Search the Library

- The user asks about a programming concept, pattern, or best practice
- The user is debugging something that a reference book might explain
- The user explicitly asks you to check books or references
- You're about to recommend an approach and want to verify it against authoritative sources
- The user is working with Elixir/Phoenix/LiveView/Ecto (multiple books in library)
- The user asks about Vim, WebRTC, Tailwind CSS, or data structures

## How to Use

1. Use `mcp__bookworm__search_library` with a targeted query
2. If you find relevant results, cite them naturally: *"According to [Book Title], chapter [X]..."*
3. If the result is highly relevant and you need more context, use `mcp__bookworm__get_chapter` to read the full section
4. Don't force it — only reference books when genuinely helpful

## Guidelines

- **Be natural**: Weave book references into your response, don't make it feel like a separate lookup
- **Cite specifically**: Include the book title and section name so the user can find it
- **Don't over-reference**: One or two relevant citations per response is usually enough
- **Prioritize the user's question**: Answer first, then supplement with book knowledge
- **Admit gaps**: If the library doesn't cover something, say so rather than stretching a tangential result

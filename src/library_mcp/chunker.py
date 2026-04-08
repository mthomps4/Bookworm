"""Text chunking with overlap, respecting paragraph and section boundaries."""

from __future__ import annotations

import logging

import tiktoken

from .models import Chunk, ChunkingConfig, ExtractedBook, Section

logger = logging.getLogger(__name__)

# Use cl100k_base (GPT-4 tokenizer) — good general-purpose token counter
_encoding = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_encoding.encode(text))


def chunk_book(book: ExtractedBook, config: ChunkingConfig | None = None) -> list[Chunk]:
    """Chunk an entire extracted book into embedding-ready pieces."""
    if config is None:
        config = ChunkingConfig()

    chunks: list[Chunk] = []
    chunk_index = 0

    for section in book.sections:
        section_chunks = _chunk_section(
            section=section,
            book_title=book.title,
            author=book.author,
            config=config,
            start_index=chunk_index,
        )
        chunks.extend(section_chunks)
        chunk_index += len(section_chunks)

    return chunks


def _chunk_section(
    section: Section,
    book_title: str,
    author: str,
    config: ChunkingConfig,
    start_index: int,
) -> list[Chunk]:
    """Chunk a single section, respecting paragraph boundaries."""
    text = section.text.strip()
    if not text:
        return []

    token_count = count_tokens(text)

    # If the section fits in one chunk, keep it whole
    if token_count <= config.max_tokens:
        return [
            Chunk(
                text=text,
                book_title=book_title,
                author=author,
                section_title=section.title,
                chunk_index=start_index,
                page_number=section.page_start,
                token_count=token_count,
            )
        ]

    # Split into paragraphs
    paragraphs = _split_paragraphs(text)

    # Build chunks from paragraphs with overlap
    chunks: list[Chunk] = []
    current_parts: list[str] = []
    current_tokens = 0
    overlap_buffer: list[str] = []

    for para in paragraphs:
        para_tokens = count_tokens(para)

        # If a single paragraph exceeds max_tokens, split it by sentences
        if para_tokens > config.max_tokens:
            # Flush current buffer first
            if current_parts:
                chunk_text = "\n\n".join(current_parts)
                chunks.append(Chunk(
                    text=chunk_text,
                    book_title=book_title,
                    author=author,
                    section_title=section.title,
                    chunk_index=start_index + len(chunks),
                    page_number=section.page_start,
                    token_count=count_tokens(chunk_text),
                ))
                overlap_buffer = _get_overlap_parts(current_parts, config.overlap_tokens)
                current_parts = []
                current_tokens = 0

            # Split large paragraph by sentences
            sentence_chunks = _chunk_large_paragraph(para, config)
            for sc_text in sentence_chunks:
                chunks.append(Chunk(
                    text=sc_text,
                    book_title=book_title,
                    author=author,
                    section_title=section.title,
                    chunk_index=start_index + len(chunks),
                    page_number=section.page_start,
                    token_count=count_tokens(sc_text),
                ))
            # Reset overlap from last sentence chunk
            overlap_buffer = []
            continue

        # Would adding this paragraph exceed the target?
        if current_tokens + para_tokens > config.target_tokens and current_parts:
            chunk_text = "\n\n".join(current_parts)
            chunks.append(Chunk(
                text=chunk_text,
                book_title=book_title,
                author=author,
                section_title=section.title,
                chunk_index=start_index + len(chunks),
                page_number=section.page_start,
                token_count=count_tokens(chunk_text),
            ))

            # Build overlap from tail of current chunk
            overlap_buffer = _get_overlap_parts(current_parts, config.overlap_tokens)
            current_parts = list(overlap_buffer)
            current_tokens = sum(count_tokens(p) for p in current_parts)

        current_parts.append(para)
        current_tokens += para_tokens

    # Flush remaining
    if current_parts:
        chunk_text = "\n\n".join(current_parts)
        chunks.append(Chunk(
            text=chunk_text,
            book_title=book_title,
            author=author,
            section_title=section.title,
            chunk_index=start_index + len(chunks),
            page_number=section.page_start,
            token_count=count_tokens(chunk_text),
        ))

    return chunks


def _split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs, preserving non-empty blocks."""
    parts = text.split("\n\n")
    paragraphs = []
    for p in parts:
        stripped = p.strip()
        if stripped:
            paragraphs.append(stripped)
    # If no double-newline splits worked, try single newline with blank-line detection
    if len(paragraphs) <= 1 and "\n" in text:
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    return paragraphs


def _get_overlap_parts(parts: list[str], overlap_tokens: int) -> list[str]:
    """Get trailing paragraphs that fit within the overlap token budget."""
    overlap: list[str] = []
    tokens = 0
    for part in reversed(parts):
        part_tokens = count_tokens(part)
        if tokens + part_tokens > overlap_tokens:
            break
        overlap.insert(0, part)
        tokens += part_tokens
    return overlap


def _chunk_large_paragraph(text: str, config: ChunkingConfig) -> list[str]:
    """Split an oversized paragraph into chunks by sentence boundaries."""
    sentences = _split_sentences(text)
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for sentence in sentences:
        s_tokens = count_tokens(sentence)
        if current_tokens + s_tokens > config.target_tokens and current:
            chunks.append(" ".join(current))
            # Keep last sentence(s) as overlap
            overlap_tokens = 0
            overlap: list[str] = []
            for s in reversed(current):
                st = count_tokens(s)
                if overlap_tokens + st > config.overlap_tokens:
                    break
                overlap.insert(0, s)
                overlap_tokens += st
            current = list(overlap)
            current_tokens = overlap_tokens

        current.append(sentence)
        current_tokens += s_tokens

    if current:
        chunks.append(" ".join(current))

    return chunks


def _split_sentences(text: str) -> list[str]:
    """Simple sentence splitter — split on sentence-ending punctuation."""
    import re

    # Split on . ! ? followed by whitespace or end of string
    # Avoid splitting on common abbreviations
    parts = re.split(r'(?<=[.!?])\s+', text)
    return [p.strip() for p in parts if p.strip()]

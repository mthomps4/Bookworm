"""Tests for the text chunking module."""

from library_mcp.chunker import chunk_book, count_tokens, _split_paragraphs, _split_sentences
from library_mcp.models import ChunkingConfig, ExtractedBook, BookFormat, Section


def test_count_tokens():
    assert count_tokens("hello world") > 0
    assert count_tokens("") == 0
    assert count_tokens("a " * 100) > 50


def test_split_paragraphs():
    text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    paras = _split_paragraphs(text)
    assert len(paras) == 3
    assert paras[0] == "First paragraph."
    assert paras[2] == "Third paragraph."


def test_split_paragraphs_single_newlines():
    text = "Line one.\nLine two.\nLine three."
    paras = _split_paragraphs(text)
    assert len(paras) == 3


def test_split_paragraphs_empty():
    assert _split_paragraphs("") == []
    assert _split_paragraphs("   ") == []


def test_split_sentences():
    text = "First sentence. Second sentence! Third sentence?"
    sentences = _split_sentences(text)
    assert len(sentences) == 3


def test_chunk_book_basic(sample_book):
    config = ChunkingConfig(target_tokens=600, max_tokens=800, overlap_tokens=75)
    chunks = chunk_book(sample_book, config)

    assert len(chunks) > 0
    for chunk in chunks:
        assert chunk.book_title == "Clean Design"
        assert chunk.author == "Test Author"
        assert chunk.text.strip() != ""
        assert chunk.token_count > 0


def test_chunk_book_preserves_section_info(sample_book):
    chunks = chunk_book(sample_book)
    section_titles = {c.section_title for c in chunks}
    assert "Chapter 1: Introduction" in section_titles
    assert "Chapter 2: Naming" in section_titles


def test_chunk_book_sequential_indices(sample_book):
    chunks = chunk_book(sample_book)
    indices = [c.chunk_index for c in chunks]
    assert indices == list(range(len(chunks)))


def test_chunk_small_section_stays_whole():
    """A section smaller than target_tokens should be one chunk."""
    book = ExtractedBook(
        title="Tiny",
        author="Author",
        format=BookFormat.PDF,
        sections=[Section(title="Short", text="This is a very short section.", page_start=1, page_end=1)],
    )
    config = ChunkingConfig(target_tokens=600, max_tokens=800, overlap_tokens=75)
    chunks = chunk_book(book, config)
    assert len(chunks) == 1
    assert chunks[0].text == "This is a very short section."


def test_chunk_empty_book():
    book = ExtractedBook(
        title="Empty",
        author="Author",
        format=BookFormat.PDF,
        sections=[],
    )
    chunks = chunk_book(book)
    assert chunks == []


def test_chunk_empty_section():
    book = ExtractedBook(
        title="Blank",
        author="Author",
        format=BookFormat.PDF,
        sections=[Section(title="Empty", text="", page_start=1, page_end=1)],
    )
    chunks = chunk_book(book)
    assert chunks == []


def test_chunk_whitespace_only_section():
    book = ExtractedBook(
        title="Whitespace",
        author="Author",
        format=BookFormat.PDF,
        sections=[Section(title="Spaces", text="   \n\n   \n  ", page_start=1, page_end=1)],
    )
    chunks = chunk_book(book)
    assert chunks == []


def test_chunk_respects_target_size():
    """Generate a large section and verify chunks stay near the target size."""
    # Build a long text (~5000 tokens)
    long_text = "\n\n".join(
        f"Paragraph {i}. " + "This is filler text for testing purposes. " * 10
        for i in range(50)
    )
    book = ExtractedBook(
        title="Long Book",
        author="Author",
        format=BookFormat.PDF,
        sections=[Section(title="Big Chapter", text=long_text)],
    )
    config = ChunkingConfig(target_tokens=200, max_tokens=400, overlap_tokens=30)
    chunks = chunk_book(book, config)

    assert len(chunks) > 5  # Should produce many chunks
    for chunk in chunks:
        # Allow some tolerance — overlap and paragraph boundaries can exceed target
        assert chunk.token_count <= config.max_tokens + 50  # generous margin


def test_chunk_page_number_carried_through():
    book = ExtractedBook(
        title="Paged",
        author="Author",
        format=BookFormat.PDF,
        sections=[
            Section(title="Ch1", text="Some text here.", page_start=42, page_end=50),
        ],
    )
    chunks = chunk_book(book)
    assert chunks[0].page_number == 42

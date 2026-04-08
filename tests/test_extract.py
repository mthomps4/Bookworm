"""Tests for the text extraction module."""

from pathlib import Path

import pytest

from library_mcp.extract import detect_format, extract_book, ExtractionError
from library_mcp.models import BookFormat


def test_detect_format_pdf():
    assert detect_format(Path("book.pdf")) == BookFormat.PDF
    assert detect_format(Path("book.PDF")) == BookFormat.PDF


def test_detect_format_epub():
    assert detect_format(Path("book.epub")) == BookFormat.EPUB


def test_detect_format_mobi():
    assert detect_format(Path("book.mobi")) == BookFormat.MOBI


def test_detect_format_unsupported():
    with pytest.raises(ValueError, match="Unsupported"):
        detect_format(Path("book.txt"))


def test_detect_format_no_extension():
    with pytest.raises(ValueError, match="Unsupported"):
        detect_format(Path("book"))


def test_extract_nonexistent_file():
    with pytest.raises(ExtractionError, match="File not found"):
        extract_book(Path("/nonexistent/book.pdf"))


def test_extract_empty_file(tmp_path):
    empty = tmp_path / "empty.pdf"
    empty.write_bytes(b"")
    with pytest.raises(ExtractionError, match="File is empty"):
        extract_book(empty)


def test_extract_corrupt_pdf(tmp_path):
    corrupt = tmp_path / "corrupt.pdf"
    corrupt.write_bytes(b"this is not a pdf")
    with pytest.raises(ExtractionError):
        extract_book(corrupt)


def test_extract_corrupt_epub(tmp_path):
    corrupt = tmp_path / "corrupt.epub"
    corrupt.write_bytes(b"this is not an epub")
    with pytest.raises(ExtractionError):
        extract_book(corrupt)


def test_extract_real_pdf(tmp_path):
    """Create a minimal valid PDF and extract text from it."""
    try:
        import fitz
    except ImportError:
        pytest.skip("pymupdf not available")

    # Create a simple PDF with pymupdf
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello, this is a test PDF document.")
    page.insert_text((72, 100), "It has two lines of text.")

    pdf_path = tmp_path / "test.pdf"
    doc.save(str(pdf_path))
    doc.close()

    book = extract_book(pdf_path)
    assert book.format == BookFormat.PDF
    assert len(book.sections) > 0

    # Check text was actually extracted
    all_text = " ".join(s.text for s in book.sections)
    assert "test PDF document" in all_text


def test_extract_real_epub(tmp_path):
    """Create a minimal valid EPUB and extract text from it."""
    try:
        from ebooklib import epub
    except ImportError:
        pytest.skip("ebooklib not available")

    book = epub.EpubBook()
    book.set_identifier("test-id-123")
    book.set_title("Test EPUB Book")
    book.set_language("en")
    book.add_author("Test Author")

    # Create a chapter
    chapter = epub.EpubHtml(title="Chapter 1", file_name="chap_01.xhtml", lang="en")
    chapter.content = (
        "<html><body>"
        "<h1>Chapter 1: Getting Started</h1>"
        "<p>This is the first chapter of our test book. It contains enough text "
        "to pass the minimum length threshold for extraction.</p>"
        "<p>Here is another paragraph with more content to make this realistic.</p>"
        "</body></html>"
    )
    book.add_item(chapter)

    # Add navigation
    book.toc = [epub.Link("chap_01.xhtml", "Chapter 1", "chapter1")]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", chapter]

    epub_path = tmp_path / "test.epub"
    epub.write_epub(str(epub_path), book, {})

    result = extract_book(epub_path)
    assert result.title == "Test EPUB Book"
    assert result.author == "Test Author"
    assert result.format == BookFormat.EPUB
    assert len(result.sections) > 0

    all_text = " ".join(s.text for s in result.sections)
    assert "first chapter" in all_text


def test_detect_format_markdown():
    assert detect_format(Path("notes.md")) == BookFormat.MARKDOWN


def test_extract_markdown_with_headings(tmp_path):
    md = tmp_path / "guide.md"
    md.write_text(
        "# My Guide\n\n"
        "Some preamble text here.\n\n"
        "## Chapter 1: Basics\n\n"
        "This chapter covers the basics of the topic.\n\n"
        "## Chapter 2: Advanced\n\n"
        "This chapter goes deeper into advanced concepts.\n"
    )
    result = extract_book(md)
    assert result.title == "My Guide"
    assert result.format == BookFormat.MARKDOWN
    assert len(result.sections) == 3  # preamble + 2 chapters
    assert result.sections[1].title == "Chapter 1: Basics"
    assert "basics" in result.sections[1].text.lower()


def test_extract_markdown_no_headings(tmp_path):
    md = tmp_path / "plain.md"
    md.write_text("Just some plain text without any headings.\n\nAnother paragraph.")
    result = extract_book(md)
    assert result.format == BookFormat.MARKDOWN
    assert len(result.sections) == 1
    assert "plain text" in result.sections[0].text


def test_extract_markdown_empty(tmp_path):
    md = tmp_path / "empty.md"
    md.write_text("   \n\n  ")
    with pytest.raises(ExtractionError, match="empty"):
        extract_book(md)

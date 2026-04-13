"""Text extraction from PDF, EPUB, and MOBI files."""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

from .models import BookFormat, ExtractedBook, Section

logger = logging.getLogger(__name__)


def detect_format(path: Path) -> BookFormat:
    suffix = path.suffix.lower()
    formats = {
        ".pdf": BookFormat.PDF,
        ".epub": BookFormat.EPUB,
        ".mobi": BookFormat.MOBI,
        ".md": BookFormat.MARKDOWN,
        ".txt": BookFormat.TXT,
        ".html": BookFormat.HTML,
        ".htm": BookFormat.HTML,
    }
    if suffix not in formats:
        raise ValueError(f"Unsupported file format: {suffix}")
    return formats[suffix]


class ExtractionError(Exception):
    """Raised when text extraction fails for a book."""


def extract_book(path: Path) -> ExtractedBook:
    """Extract text from a book file, dispatching by format.

    Raises ExtractionError with a descriptive message on failure.
    """
    if not path.exists():
        raise ExtractionError(f"File not found: {path}")
    if path.stat().st_size == 0:
        raise ExtractionError(f"File is empty: {path}")

    fmt = detect_format(path)
    extractors = {
        BookFormat.PDF: _extract_pdf,
        BookFormat.EPUB: _extract_epub,
        BookFormat.MOBI: _extract_mobi,
        BookFormat.MARKDOWN: _extract_markdown,
        BookFormat.TXT: _extract_txt,
        BookFormat.HTML: _extract_html,
    }
    try:
        return extractors[fmt](path)
    except ExtractionError:
        raise
    except Exception as e:
        raise ExtractionError(f"Failed to extract {path.name}: {e}") from e


# --- PDF Extraction ---


def _extract_pdf(path: Path) -> ExtractedBook:
    import fitz  # pymupdf

    try:
        doc = fitz.open(str(path))
    except Exception as e:
        raise ExtractionError(f"Cannot open PDF {path.name}: {e}") from e

    try:
        metadata = doc.metadata or {}
        title = metadata.get("title", "") or path.stem
        author = metadata.get("author", "") or "Unknown"

        if doc.page_count == 0:
            raise ExtractionError(f"PDF has no pages: {path.name}")

        # Try to extract TOC for chapter boundaries
        toc = doc.get_toc()  # list of [level, title, page_number]

        if toc:
            sections = _extract_pdf_with_toc(doc, toc)
        else:
            sections = _extract_pdf_no_toc(doc)
    finally:
        doc.close()

    return ExtractedBook(title=title, author=author, format=BookFormat.PDF, sections=sections)


def _extract_pdf_with_toc(doc, toc: list) -> list[Section]:
    """Extract sections using table of contents boundaries."""
    sections = []
    for i, (level, title, start_page) in enumerate(toc):
        if level > 2:
            continue  # Only use top 2 TOC levels

        # Determine end page: next TOC entry's page or end of document
        end_page = doc.page_count
        for j in range(i + 1, len(toc)):
            if toc[j][0] <= level:
                end_page = toc[j][2]
                break

        # Pages are 1-indexed in TOC, 0-indexed in pymupdf
        start_idx = max(0, start_page - 1)
        end_idx = min(doc.page_count, end_page - 1) if end_page != doc.page_count else doc.page_count

        text_parts = []
        for page_num in range(start_idx, end_idx):
            page_text = doc[page_num].get_text()
            if page_text.strip():
                text_parts.append(page_text)

        text = "\n".join(text_parts).strip()
        if text:
            sections.append(Section(
                title=title,
                text=text,
                page_start=start_page,
                page_end=end_page if end_page != doc.page_count else doc.page_count,
            ))

    # If TOC parsing produced nothing useful, fall back
    if not sections:
        return _extract_pdf_no_toc(doc)

    return sections


def _extract_pdf_no_toc(doc) -> list[Section]:
    """Extract PDF without TOC — group into page-range sections."""
    pages_per_section = 20
    sections = []
    total = doc.page_count

    for start in range(0, total, pages_per_section):
        end = min(start + pages_per_section, total)
        text_parts = []
        for page_num in range(start, end):
            page_text = doc[page_num].get_text()
            if page_text.strip():
                text_parts.append(page_text)

        text = "\n".join(text_parts).strip()
        if not text:
            # Try OCR fallback for pages with no extractable text
            text = _ocr_pages(doc, start, end)

        if text:
            sections.append(Section(
                title=f"Pages {start + 1}–{end}",
                text=text,
                page_start=start + 1,
                page_end=end,
            ))

    return sections


def _ocr_pages(doc, start: int, end: int) -> str:
    """OCR fallback for scanned pages using pytesseract."""
    try:
        import pytesseract
        from PIL import Image
        import io
    except ImportError:
        logger.warning("pytesseract/Pillow not available for OCR fallback")
        return ""

    texts = []
    for page_num in range(start, end):
        try:
            page = doc[page_num]
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            text = pytesseract.image_to_string(img)
            if text.strip():
                texts.append(text)
        except Exception as e:
            logger.warning(f"OCR failed for page {page_num + 1}: {e}")
            continue

    return "\n".join(texts).strip()


# --- EPUB Extraction ---


def _extract_epub(path: Path) -> ExtractedBook:
    import ebooklib
    from ebooklib import epub
    from bs4 import BeautifulSoup

    try:
        book = epub.read_epub(str(path), options={"ignore_ncx": True})
    except Exception as e:
        raise ExtractionError(f"Cannot open EPUB {path.name}: {e}") from e

    # Metadata
    title_meta = book.get_metadata("DC", "title")
    title = title_meta[0][0] if title_meta else path.stem
    author_meta = book.get_metadata("DC", "creator")
    author = author_meta[0][0] if author_meta else "Unknown"

    # Build a map of item href -> TOC title from the table of contents
    toc_map = _build_epub_toc_map(book)

    sections = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        html = item.get_content().decode("utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator="\n", strip=True)

        if not text or len(text) < 50:
            continue

        # Use TOC title if available, otherwise derive from filename
        section_title = toc_map.get(item.get_name(), item.get_name().rsplit("/", 1)[-1].rsplit(".", 1)[0])

        sections.append(Section(title=section_title, text=text))

    return ExtractedBook(title=title, author=author, format=BookFormat.EPUB, sections=sections)


def _build_epub_toc_map(book) -> dict[str, str]:
    """Build a mapping from item href to TOC section title."""
    from ebooklib import epub

    toc_map = {}

    def _walk_toc(entries):
        for entry in entries:
            if isinstance(entry, epub.Link):
                # Strip fragment identifier
                href = entry.href.split("#")[0]
                toc_map[href] = entry.title
            elif isinstance(entry, tuple) and len(entry) == 2:
                # Nested TOC: (Section, [children])
                section, children = entry
                if isinstance(section, epub.Section):
                    pass  # Section groups don't map to a single href
                if isinstance(children, list):
                    _walk_toc(children)

    _walk_toc(book.toc)
    return toc_map


# --- MOBI Extraction ---


def _extract_mobi(path: Path) -> ExtractedBook:
    """Convert MOBI to EPUB, then extract as EPUB."""
    # Try mobi library first
    try:
        return _mobi_via_library(path)
    except Exception as e:
        logger.info(f"mobi library failed ({e}), trying ebook-convert CLI")

    # Fallback: Calibre's ebook-convert
    return _mobi_via_calibre(path)


def _mobi_via_library(path: Path) -> ExtractedBook:
    import mobi

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        # mobi.extract returns (tempdir, filepath) of extracted content
        _, extracted_path = mobi.extract(str(path))
        extracted = Path(extracted_path)

        # The mobi library extracts to an epub or html file
        if extracted.suffix.lower() == ".epub":
            return _extract_epub(extracted)

        # If it's HTML, parse directly
        from bs4 import BeautifulSoup

        html = extracted.read_text(errors="replace")
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator="\n", strip=True)

        return ExtractedBook(
            title=path.stem,
            author="Unknown",
            format=BookFormat.MOBI,
            sections=[Section(title="Full Text", text=text)] if text else [],
        )


def _mobi_via_calibre(path: Path) -> ExtractedBook:
    with tempfile.TemporaryDirectory() as tmpdir:
        epub_path = Path(tmpdir) / f"{path.stem}.epub"
        result = subprocess.run(
            ["ebook-convert", str(path), str(epub_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"ebook-convert failed: {result.stderr}")

        book = _extract_epub(epub_path)
        # Override format to MOBI since that's the source
        return book.model_copy(update={"format": BookFormat.MOBI})


# --- Markdown Extraction ---


def _extract_markdown(path: Path) -> ExtractedBook:
    """Extract sections from a Markdown file by splitting on headings."""
    import re

    text = path.read_text(errors="replace")
    if not text.strip():
        raise ExtractionError(f"Markdown file is empty: {path.name}")

    # Try to pull a title from the first H1, fall back to filename
    title = path.stem
    author = "Unknown"
    first_h1 = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if first_h1:
        title = first_h1.group(1).strip()

    # Split on heading lines (## and above)
    heading_pattern = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
    matches = list(heading_pattern.finditer(text))

    if not matches:
        # No headings — treat whole file as one section
        return ExtractedBook(
            title=title,
            author=author,
            format=BookFormat.MARKDOWN,
            sections=[Section(title=title, text=text.strip())],
        )

    sections = []

    # Content before the first heading (if any)
    preamble = text[: matches[0].start()].strip()
    if preamble:
        sections.append(Section(title="Preamble", text=preamble))

    # Each heading starts a section that runs until the next heading
    for i, match in enumerate(matches):
        heading_title = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()

        if body:
            sections.append(Section(title=heading_title, text=body))

    return ExtractedBook(
        title=title,
        author=author,
        format=BookFormat.MARKDOWN,
        sections=sections,
    )


# --- Plain Text Extraction ---


def _extract_txt(path: Path) -> ExtractedBook:
    """Extract sections from a plain text file.

    Splits on blank-line-separated blocks of uppercase or title-case lines
    (common chapter headings), or falls back to fixed-size sections.
    """
    import re

    text = path.read_text(errors="replace")
    if not text.strip():
        raise ExtractionError(f"Text file is empty: {path.name}")

    title = path.stem.replace("-", " ").replace("_", " ")
    author = "Unknown"

    # Try to detect chapter-like headings: lines that are ALL CAPS, or
    # "Chapter N" / "PART N" patterns preceded by a blank line
    heading_pattern = re.compile(
        r"(?:^|\n\n+)"                        # preceded by blank lines or start
        r"((?:chapter|part|section)\s+\S+.*"   # "Chapter 1: ..." etc
        r"|[A-Z][A-Z\s:—\-]{5,})"             # or ALL CAPS line (min 6 chars)
        r"\s*\n",
        re.IGNORECASE | re.MULTILINE,
    )
    matches = list(heading_pattern.finditer(text))

    if len(matches) >= 2:
        sections = []
        # Content before first heading
        preamble = text[: matches[0].start()].strip()
        if preamble and len(preamble) > 50:
            sections.append(Section(title="Preamble", text=preamble))

        for i, match in enumerate(matches):
            heading = match.group(1).strip()
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[start:end].strip()
            if body:
                sections.append(Section(title=heading, text=body))

        if sections:
            return ExtractedBook(title=title, author=author, format=BookFormat.TXT, sections=sections)

    # Fallback: split into ~2000-character sections by paragraph boundaries
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    sections = []
    current_parts: list[str] = []
    current_len = 0
    section_num = 1

    for para in paragraphs:
        current_parts.append(para)
        current_len += len(para)
        if current_len >= 2000:
            sections.append(Section(
                title=f"Section {section_num}",
                text="\n\n".join(current_parts),
            ))
            section_num += 1
            current_parts = []
            current_len = 0

    if current_parts:
        sections.append(Section(
            title=f"Section {section_num}",
            text="\n\n".join(current_parts),
        ))

    return ExtractedBook(title=title, author=author, format=BookFormat.TXT, sections=sections)


# --- HTML Extraction ---


def _extract_html(path: Path) -> ExtractedBook:
    """Extract sections from an HTML file by splitting on heading elements."""
    from bs4 import BeautifulSoup

    html = path.read_text(errors="replace")
    if not html.strip():
        raise ExtractionError(f"HTML file is empty: {path.name}")

    soup = BeautifulSoup(html, "html.parser")

    # Try to get title from <title> tag or <h1>
    title_tag = soup.find("title")
    h1_tag = soup.find("h1")
    title = (title_tag.get_text(strip=True) if title_tag else None) or \
            (h1_tag.get_text(strip=True) if h1_tag else None) or \
            path.stem.replace("-", " ").replace("_", " ")

    # Try to get author from meta tag
    author_meta = soup.find("meta", attrs={"name": "author"})
    author = author_meta["content"] if author_meta and author_meta.get("content") else "Unknown"

    # Find all heading elements to use as section boundaries
    headings = soup.find_all(["h1", "h2", "h3"])

    if len(headings) >= 2:
        sections = []

        # Content before first heading
        first_heading = headings[0]
        pre_content = []
        for sibling in first_heading.previous_siblings:
            if hasattr(sibling, "get_text"):
                text = sibling.get_text(separator="\n", strip=True)
                if text:
                    pre_content.insert(0, text)
        preamble = "\n\n".join(pre_content).strip()
        if preamble and len(preamble) > 50:
            sections.append(Section(title="Preamble", text=preamble))

        # Each heading starts a section
        for i, heading in enumerate(headings):
            heading_text = heading.get_text(strip=True)

            # Collect all content between this heading and the next
            content_parts = []
            for sibling in heading.next_siblings:
                # Stop at the next heading
                if sibling in headings:
                    break
                if hasattr(sibling, "get_text"):
                    text = sibling.get_text(separator="\n", strip=True)
                    if text:
                        content_parts.append(text)
                elif isinstance(sibling, str) and sibling.strip():
                    content_parts.append(sibling.strip())

            body = "\n\n".join(content_parts).strip()
            if body:
                sections.append(Section(title=heading_text, text=body))

        if sections:
            return ExtractedBook(title=title, author=author, format=BookFormat.HTML, sections=sections)

    # Fallback: treat entire document as one section
    text = soup.get_text(separator="\n", strip=True)
    if not text:
        raise ExtractionError(f"No text content in HTML file: {path.name}")

    return ExtractedBook(
        title=title,
        author=author,
        format=BookFormat.HTML,
        sections=[Section(title=title, text=text)],
    )

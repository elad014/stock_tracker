import re
from dataclasses import dataclass
from typing import Literal

import pymupdf
import pymupdf4llm

from constant import DOC_DEFAULT_SECTION

_PDF_MAGIC = b"%PDF-"
_MD_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
_ITEM_HEADING = re.compile(
    r"^(?:#{1,6}\s*)?ITEM\s+\d+[A-Z]?\.?\s+\S.*$",
    re.IGNORECASE,
)
_ITEM_ONLY = re.compile(
    r"^(?:#{1,6}\s*)?ITEM\s+(\d+[A-Z]?)\.?\s*$",
    re.IGNORECASE,
)
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{3,}")

BlockKind = Literal["prose", "table"]


class PdfExtractError(ValueError):
    """Raised when PDF bytes cannot be turned into usable text."""


@dataclass(frozen=True)
class ExtractedBlock:
    kind: BlockKind
    section: str
    text: str


def _clean_meta(value: str) -> str:
    return " ".join(value.replace("|", "/").split())


def _is_table_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if _TABLE_ROW.match(stripped):
        return True
    return bool(_TABLE_SEPARATOR.match(stripped))


def _heading_from_line(line: str) -> str | None:
    stripped = line.strip()
    if not stripped:
        return None
    matched = _MD_HEADING.match(stripped)
    if matched:
        return _clean_meta(matched.group(2))
    if _ITEM_HEADING.match(stripped):
        return _clean_meta(re.sub(r"^#+\s*", "", stripped))
    return None


def parse_markdown_blocks(markdown: str) -> list[ExtractedBlock]:
    """Split LLM markdown into prose and table blocks, tracking section headers."""
    lines = markdown.replace("\r\n", "\n").split("\n")
    blocks: list[ExtractedBlock] = []
    current_section = DOC_DEFAULT_SECTION
    prose_buf: list[str] = []
    table_buf: list[str] = []

    def flush_prose() -> None:
        text = "\n".join(prose_buf).strip()
        prose_buf.clear()
        if text:
            blocks.append(
                ExtractedBlock(kind="prose", section=current_section, text=text)
            )

    def flush_table() -> None:
        text = "\n".join(table_buf).strip()
        table_buf.clear()
        if text:
            blocks.append(
                ExtractedBlock(kind="table", section=current_section, text=text)
            )

    index = 0
    while index < len(lines):
        line = lines[index]
        item_only = _ITEM_ONLY.match(line.strip())
        if item_only:
            title = item_only.group(1)
            lookahead = index + 1
            while lookahead < len(lines) and not lines[lookahead].strip():
                lookahead += 1
            suffix = ""
            if lookahead < len(lines):
                next_heading = _heading_from_line(lines[lookahead])
                next_table = _is_table_line(lines[lookahead])
                if not next_heading and not next_table:
                    suffix = f" {lines[lookahead].strip()}"
                    index = lookahead
            flush_table()
            flush_prose()
            current_section = _clean_meta(f"Item {title}.{suffix}")
            index += 1
            continue

        heading = _heading_from_line(line)
        if heading:
            flush_table()
            flush_prose()
            current_section = heading
            index += 1
            continue

        if _is_table_line(line):
            flush_prose()
            table_buf.append(line.rstrip())
            index += 1
            continue

        flush_table()
        prose_buf.append(line)
        index += 1

    flush_table()
    flush_prose()
    return blocks


def extract_pdf_markdown(data: bytes) -> str:
    """Convert a PDF payload to markdown, including tables and headings."""
    if not data.startswith(_PDF_MAGIC):
        raise PdfExtractError("File is not a valid PDF")

    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise PdfExtractError("File is not a valid PDF") from exc

    try:
        if document.is_encrypted:
            if not document.authenticate(""):
                raise PdfExtractError("PDF is encrypted")
        markdown = pymupdf4llm.to_markdown(
            document,
            write_images=False,
            ignore_images=True,
            table_strategy="lines_strict",
            table_output="markdown",
            show_progress=False,
        )
    except PdfExtractError:
        raise
    except Exception as exc:
        raise PdfExtractError("Failed to read PDF") from exc
    finally:
        document.close()

    cleaned = (markdown or "").strip()
    if not cleaned:
        raise PdfExtractError("PDF contains no extractable text")
    return cleaned


def extract_pdf_blocks(data: bytes) -> list[ExtractedBlock]:
    """Extract structured prose and table blocks from a PDF payload."""
    markdown = extract_pdf_markdown(data)
    blocks = parse_markdown_blocks(markdown)
    if not blocks:
        raise PdfExtractError("PDF contains no extractable text")
    return blocks

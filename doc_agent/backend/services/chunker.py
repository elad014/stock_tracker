from constant import DOC_DEFAULT_SECTION, DOC_TABLE_MAX_CHARS
from services.pdf_extractor import ExtractedBlock

_PROSE_BREAKS: tuple[str, ...] = (
    "\n\n",
    ". ",
    ".\n",
    "? ",
    "! ",
    "\n",
    " ",
)


def _clean_meta(value: str) -> str:
    return " ".join(value.replace("|", "/").split()) or DOC_DEFAULT_SECTION


def format_chunk(document_name: str, section: str, content: str) -> str:
    """Prepend document/section metadata used for embedding and retrieval."""
    header = (
        f"Document: {_clean_meta(document_name)} | "
        f"Section: {_clean_meta(section)}"
    )
    body = content.strip()
    if not body:
        return header
    return f"{header}\n\n{body}"


def _snap_end(text: str, start: int, hard_end: int) -> int:
    """Move hard_end back to a paragraph, then a sentence boundary."""
    if hard_end >= len(text):
        return len(text)

    window = text[start:hard_end]
    min_keep = max(1, len(window) // 4)
    region = window[min_keep:]
    for separator in _PROSE_BREAKS:
        idx = region.rfind(separator)
        if idx != -1:
            snapped = start + min_keep + idx + len(separator)
            if snapped > start:
                return snapped
    return hard_end


def chunk_text(text: str, chunk_chars: int, overlap: int) -> list[str]:
    """Split prose into overlapping character windows, snapped to boundaries."""
    cleaned = text.strip()
    if not cleaned:
        return []
    if chunk_chars <= 0:
        raise ValueError("chunk_chars must be a positive integer")
    safe_overlap = max(0, min(overlap, chunk_chars - 1))

    chunks: list[str] = []
    start = 0
    length = len(cleaned)
    while start < length:
        hard_end = min(start + chunk_chars, length)
        end = _snap_end(cleaned, start, hard_end)
        piece = cleaned[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= length:
            break
        next_start = end - safe_overlap
        if next_start <= start:
            next_start = end
        if next_start <= start:
            break
        start = next_start
    return chunks


def _is_separator_row(line: str) -> bool:
    stripped = line.strip().replace(":", "").replace("|", "").replace(" ", "")
    return bool(stripped) and set(stripped) <= {"-"}


def chunk_table(table: str, max_chars: int) -> list[str]:
    """Keep a markdown table intact, splitting only between complete rows."""
    cleaned = table.strip()
    if not cleaned:
        return []
    if max_chars <= 0 or len(cleaned) <= max_chars:
        return [cleaned]

    lines = [line for line in cleaned.splitlines() if line.strip()]
    header_lines: list[str]
    body: list[str]
    if len(lines) >= 2 and _is_separator_row(lines[1]):
        header_lines = lines[:2]
        body = lines[2:]
    else:
        header_lines = lines[:1]
        body = lines[1:]

    if not body:
        return [cleaned]

    def packed(rows: list[str]) -> str:
        return "\n".join(header_lines + rows)

    chunks: list[str] = []
    current: list[str] = []
    for row in body:
        candidate = packed(current + [row])
        if current and len(candidate) > max_chars:
            chunks.append(packed(current))
            current = [row]
            if len(packed(current)) > max_chars:
                chunks.append(packed(current))
                current = []
        else:
            current.append(row)
    if current:
        chunks.append(packed(current))
    return chunks


def chunk_extracted_document(
    blocks: list[ExtractedBlock],
    document_name: str,
    chunk_chars: int,
    overlap: int,
) -> list[str]:
    """Turn extracted blocks into embedding-ready chunks with metadata."""
    chunks: list[str] = []
    for block in blocks:
        if block.kind == "table":
            pieces = chunk_table(block.text, DOC_TABLE_MAX_CHARS)
        else:
            pieces = chunk_text(block.text, chunk_chars, overlap)
        for piece in pieces:
            formatted = format_chunk(document_name, block.section, piece)
            if formatted.strip():
                chunks.append(formatted)
    return chunks

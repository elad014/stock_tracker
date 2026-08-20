from constant import DOC_MAX_CHUNKS

_BREAK_SEPARATORS: tuple[str, ...] = (
    "\n\n",
    "\n",
    ". ",
    "? ",
    "! ",
    "; ",
    ", ",
    " ",
)


def _snap_end(text: str, start: int, hard_end: int) -> int:
    """Move hard_end back to the nearest paragraph/sentence boundary."""
    if hard_end >= len(text):
        return len(text)

    window = text[start:hard_end]
    min_keep = max(1, len(window) // 4)
    region_start = min_keep
    region = window[region_start:]
    for separator in _BREAK_SEPARATORS:
        idx = region.rfind(separator)
        if idx != -1:
            snapped = start + region_start + idx + len(separator)
            if snapped > start:
                return snapped
    return hard_end


def chunk_text(text: str, chunk_chars: int, overlap: int) -> list[str]:
    """Split text into overlapping character windows, snapped to boundaries."""
    cleaned = text.strip()
    if not cleaned:
        return []
    if chunk_chars <= 0:
        raise ValueError("chunk_chars must be a positive integer")
    safe_overlap = max(0, min(overlap, chunk_chars - 1))

    chunks: list[str] = []
    start = 0
    length = len(cleaned)
    while start < length and len(chunks) < DOC_MAX_CHUNKS:
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

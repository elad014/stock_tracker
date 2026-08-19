import re

_WHITESPACE_RE = re.compile(r"[ \t]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")


def clean_text(value: str) -> str:
    text = _WHITESPACE_RE.sub(" ", value)
    text = _BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()


def truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[:max_chars].rstrip() + "..."

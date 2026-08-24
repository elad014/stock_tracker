"""Best-effort readable-text extraction from a public article URL.

Extraction is never guaranteed: sites block bots, paywall content, or render
only via JavaScript. Every failure path returns ``None`` so callers can fall
back to the summary supplied by the news provider.
"""

import logging
from typing import Optional
from urllib.parse import urljoin

import requests
import trafilatura

from article_extractor.util import clean_text, is_safe_article_url, truncate
from constant import (
    ARTICLE_EXTRACT_MAX_BYTES,
    ARTICLE_EXTRACT_MAX_CHARS,
    ARTICLE_EXTRACT_MAX_REDIRECTS,
    ARTICLE_EXTRACT_TIMEOUT_SECONDS,
    ARTICLE_EXTRACT_USER_AGENT,
)

logger = logging.getLogger(__name__)


class ArticleExtractor:
    """Downloads an article page and extracts its main text."""

    def __init__(
        self,
        user_agent: Optional[str] = None,
        timeout: Optional[float] = None,
        max_bytes: Optional[int] = None,
        max_chars: Optional[int] = None,
    ) -> None:
        self._user_agent = user_agent or ARTICLE_EXTRACT_USER_AGENT
        self._timeout = timeout if timeout is not None else ARTICLE_EXTRACT_TIMEOUT_SECONDS
        self._max_bytes = max_bytes if max_bytes is not None else ARTICLE_EXTRACT_MAX_BYTES
        self._max_chars = max_chars if max_chars is not None else ARTICLE_EXTRACT_MAX_CHARS

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": self._user_agent,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _download(self, url: str) -> Optional[str]:
        current: str = url
        for _ in range(ARTICLE_EXTRACT_MAX_REDIRECTS + 1):
            if not is_safe_article_url(current):
                logger.info("Blocked unsafe article URL %s", current)
                return None
            try:
                with requests.get(
                    current,
                    headers=self._headers(),
                    timeout=self._timeout,
                    stream=True,
                    allow_redirects=False,
                ) as response:
                    if 300 <= response.status_code < 400:
                        location = str(response.headers.get("Location") or "").strip()
                        if not location:
                            return None
                        current = urljoin(current, location)
                        continue
                    response.raise_for_status()
                    content_type = str(response.headers.get("Content-Type", "")).lower()
                    if content_type and "html" not in content_type:
                        logger.info(
                            "Skipping non-HTML article %s (%s)",
                            current,
                            content_type,
                        )
                        return None

                    chunks: list[bytes] = []
                    total = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        if not chunk:
                            continue
                        chunks.append(chunk)
                        total += len(chunk)
                        if total >= self._max_bytes:
                            break
                    encoding = response.encoding or "utf-8"
                    return b"".join(chunks).decode(encoding, errors="replace")
            except requests.RequestException as exc:
                logger.info("Article download failed for %s: %s", current, exc)
                return None
        logger.info("Too many redirects for article URL %s", url)
        return None

    def extract(self, url: str) -> Optional[str]:
        """Return readable article text, or None when it cannot be extracted."""
        normalized = url.strip()
        if not normalized:
            return None

        html = self._download(normalized)
        if not html:
            return None

        extracted: Optional[str] = None
        try:
            extracted = trafilatura.extract(
                html,
                url=normalized,
                include_comments=False,
                include_tables=False,
                favor_precision=True,
            )
            if not extracted:
                extracted = trafilatura.extract(
                    html,
                    url=normalized,
                    include_comments=False,
                    include_tables=False,
                    favor_recall=True,
                )
        except Exception:
            logger.exception("Article extraction failed for %s", normalized)
            return None

        if not extracted:
            return None

        text = clean_text(extracted)
        if not text:
            return None
        return truncate(text, self._max_chars)

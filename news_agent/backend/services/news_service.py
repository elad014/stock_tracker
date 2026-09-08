import asyncio
import logging
import re
from datetime import date
from typing import Any, Optional

from fastapi import HTTPException, status

from constant import (
    ARTICLE_RETENTION_DAYS,
    NEWS_SEARCH_MAX_CHARS,
    NEWS_SEARCH_MAX_QUERY_CHARS,
    NEWS_SEARCH_SYSTEM_PROMPT,
)
from db_logics import articles_db_logic as articles_db
from llm_guard import guarded_user_message
from clients.llm_provider_client import LLMProviderClient
from models.news import (
    NewsArticle,
    SearchAndSummarizeResponse,
    SearchEvidenceArticle,
    StockNewsResponse,
    StoredNewsArticle,
    StoredStockNewsResponse,
)
from clients.news_provider_client import NewsProviderClient

logger = logging.getLogger(__name__)

_STOP_WORDS: frozenset[str] = frozenset(
    {
        "the",
        "and",
        "for",
        "did",
        "not",
        "who",
        "what",
        "when",
        "where",
        "why",
        "how",
        "read",
        "article",
        "news",
        "about",
        "from",
        "this",
        "that",
        "with",
        "have",
        "been",
        "does",
        "there",
        "here",
        "into",
        "than",
        "then",
        "also",
        "just",
        "some",
        "only",
        "such",
        "very",
    }
)
_QUERY_FIXES: dict[str, str] = {
    "invidia": "nvidia",
    "nvdia": "nvidia",
    "respons": "respond",
    "respon": "respond",
}
_FOLLOW_SENTENCE_MAX_CHARS: int = 400
_MATCHING_SENTENCE_LIMIT: int = 8
_NEWS_EXCERPT_LIMIT: int = 12


def _news_provider() -> NewsProviderClient:
    return NewsProviderClient()


def _llm_client() -> LLMProviderClient:
    return LLMProviderClient()


async def _run_provider(func: Any, *args: Any, **kwargs: Any) -> Any:
    return await asyncio.to_thread(func, *args, **kwargs)


async def get_stock_news(
    symbol: str,
    outputsize: int = 50,
    *,
    day: Optional[date] = None,
) -> StockNewsResponse:
    """Return Finnhub articles for one calendar day (default: today)."""
    normalized = symbol.strip().upper()
    if not normalized:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "symbol must not be empty")

    provider = _news_provider()
    target = day or date.today()
    # outputsize is kept as an optional cap for Swagger inspection; None path unused here.
    limit = max(1, min(int(outputsize), 200))

    try:
        items = await _run_provider(provider.get_news_for_day, normalized, target)
        items = items[:limit]
    except ValueError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc
    except RuntimeError as exc:
        message = str(exc)
        logger.warning("News fetch failed for %s: %s", normalized, message)
        if "not found" in message.lower():
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"Symbol not found: {normalized}",
            ) from exc
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"Failed to fetch news for {normalized}",
        ) from exc

    articles = [
        NewsArticle(
            title=item.title,
            url=item.url,
            published_at=item.published_at,
            source=item.source,
            summary=item.summary,
        )
        for item in items
    ]
    return StockNewsResponse(
        symbol=normalized,
        count=len(articles),
        articles=articles,
    )


async def get_stored_stock_news(
    symbol: str,
    *,
    days: int = ARTICLE_RETENTION_DAYS,
    limit: int = 8,
) -> StoredStockNewsResponse:
    """Return stored news_articles rows (including text) for one ticker."""
    normalized: str = symbol.strip().upper()
    if not normalized:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "symbol must not be empty")
    cap: int = max(1, min(int(limit), 50))
    rows: list[dict[str, Any]] = await articles_db.list_recent_articles_by_symbol(
        normalized,
        days=days,
        limit=cap,
    )
    articles: list[StoredNewsArticle] = [
        StoredNewsArticle(
            title=str(row.get("title") or "Untitled"),
            url=row.get("url"),
            published_at=row.get("published_at"),
            source=row.get("source"),
            text=row.get("text"),
            ai_summary=row.get("ai_summary"),
            provider_summary=row.get("provider_summary"),
        )
        for row in rows
    ]
    return StoredStockNewsResponse(
        symbol=normalized,
        count=len(articles),
        articles=articles,
    )


def _join_articles(bodies: list[str]) -> str:
    joined = "\n\n---\n\n".join(item.strip() for item in bodies if item.strip())
    if len(joined) <= NEWS_SEARCH_MAX_CHARS:
        return joined
    return joined[:NEWS_SEARCH_MAX_CHARS]


def _term_variants(word: str) -> list[str]:
    variants: list[str] = [word]
    if len(word) >= 5 and word.endswith("ies"):
        variants.append(word[:-3] + "y")
    elif len(word) >= 4 and word.endswith("s") and not word.endswith("ss"):
        variants.append(word[:-1])
    unique: list[str] = []
    for item in variants:
        if item not in unique:
            unique.append(item)
    return unique


def _query_terms(query: str, symbol: str = "") -> list[str]:
    words: list[str] = re.findall(r"[a-z0-9]+", query.lower())
    terms: list[str] = []

    def add_term(word: str) -> None:
        if len(word) < 4:
            return
        if word in _STOP_WORDS:
            return
        for variant in _term_variants(word):
            if variant in _STOP_WORDS or len(variant) < 3:
                continue
            if variant not in terms:
                terms.append(variant)

    for word in words:
        add_term(word)
        fixed: str = _QUERY_FIXES.get(word, "")
        if fixed:
            add_term(fixed)
    ticker: str = symbol.strip().lower()
    if ticker and ticker not in terms:
        terms.append(ticker)
    return terms


def _term_in_text(text: str, term: str) -> bool:
    if not term:
        return False
    return re.search(rf"\b{re.escape(term)}\b", text.lower()) is not None


def _article_score(body: str, terms: list[str]) -> int:
    if not terms:
        return 0
    return sum(1 for term in terms if _term_in_text(body, term))


def _sentence_overlap(sentence: str, terms: list[str]) -> int:
    return sum(1 for term in terms if _term_in_text(sentence, term))


def _sentence_rank(sentence: str, terms: list[str], ticker: str) -> int:
    score: int = _sentence_overlap(sentence, terms)
    ticker_l: str = ticker.strip().lower()
    if ticker_l and _term_in_text(sentence, ticker_l):
        score += 2
    return score


def _split_sentences(text: str) -> list[str]:
    normalized: str = re.sub(r"[\r\n]+(?=[•\-\*])", ". ", text)
    parts: list[str] = re.split(r"(?<=[.!?])(?!\d)\s+", normalized)
    sentences: list[str] = []
    for part in parts:
        stripped: str = part.strip()
        if stripped:
            sentences.append(stripped)
    return sentences


def _should_attach_following(current: str, following: str, ticker: str) -> bool:
    if not following or len(following) > _FOLLOW_SENTENCE_MAX_CHARS:
        return False
    stripped: str = following.lstrip("•-* ").strip()
    ticker_l: str = ticker.strip().lower()
    looks_like_new_item: bool = stripped.lower().startswith("for ")
    if looks_like_new_item and ticker_l and not _term_in_text(following, ticker_l):
        return False
    if looks_like_new_item and ticker_l and not _term_in_text(current, ticker_l):
        return False
    return True


def _matching_sentences(
    text: str,
    terms: list[str],
    limit: int = _MATCHING_SENTENCE_LIMIT,
    ticker: str = "",
) -> list[str]:
    if not terms:
        return []
    parts: list[str] = _split_sentences(text)
    scored: list[tuple[int, int, str]] = []
    for index, part in enumerate(parts):
        rank: int = _sentence_rank(part, terms, ticker)
        if rank <= 0:
            continue
        chunk: str = part
        if index + 1 < len(parts):
            following: str = parts[index + 1]
            if _should_attach_following(part, following, ticker):
                chunk = f"{part} {following}"
        scored.append((rank, -index, chunk))
    scored.sort(reverse=True)
    hits: list[str] = []
    for _rank, _order, sentence in scored:
        if sentence not in hits:
            hits.append(sentence)
        if len(hits) >= limit:
            break
    return hits


def _excerpt_rank_key(item: tuple[int, str]) -> int:
    return item[0]


def _rank_key(item: tuple[int, int, SearchEvidenceArticle]) -> tuple[int, int]:
    return (item[0], item[1])


async def search_and_summarize(symbol: str, query: str) -> SearchAndSummarizeResponse:
    """Search stored article text, return evidence plus optional news-LLM analysis."""
    ticker: str = symbol.strip().upper()
    question: str = query.strip()[:NEWS_SEARCH_MAX_QUERY_CHARS]
    if not ticker:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "symbol must not be empty")
    if not question:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "query must not be empty")

    empty = SearchAndSummarizeResponse(
        summary="No recent news found for this symbol.",
        articles=[],
    )
    try:
        rows: list[dict[str, Any]] = await articles_db.list_recent_articles_by_symbol(
            ticker,
            days=ARTICLE_RETENTION_DAYS,
            limit=50,
        )
    except Exception as exc:
        logger.exception("Failed to load article texts for %s", ticker)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Failed to load recent articles",
        ) from exc

    terms: list[str] = _query_terms(question, ticker)
    ranked: list[tuple[int, int, SearchEvidenceArticle]] = []
    for row in rows:
        body: str = str(row.get("text") or "").strip()
        if not body:
            continue
        title: str = str(row.get("title") or "Untitled").strip()
        sentences: list[str] = _matching_sentences(
            body,
            terms,
            ticker=ticker,
        )
        evidence = SearchEvidenceArticle(
            article_id=str(row.get("article_id") or ""),
            symbol=str(row.get("symbol") or ticker),
            title=title,
            published_at=row.get("published_at"),
            url=row.get("url"),
            matching_sentences=sentences,
            text=body,
        )
        score: int = _article_score(body, terms)
        best_overlap: int = 0
        for sentence in sentences:
            overlap: int = _sentence_rank(sentence, terms, ticker)
            if overlap > best_overlap:
                best_overlap = overlap
        ranked.append((score, best_overlap, evidence))
    ranked.sort(key=_rank_key, reverse=True)
    articles: list[SearchEvidenceArticle] = [item[2] for item in ranked]
    if not articles:
        return empty

    bodies: list[str] = [
        f"{item.title}\n\n{item.text}" for item in articles if item.text
    ]
    scored_excerpts: list[tuple[int, str]] = []
    for item in articles:
        for sentence in item.matching_sentences:
            scored_excerpts.append(
                (
                    _sentence_rank(sentence, terms, ticker),
                    f"{item.title}: {sentence}",
                )
            )
    scored_excerpts.sort(key=_excerpt_rank_key, reverse=True)
    excerpt_lines: list[str] = [
        line for _score, line in scored_excerpts[:_NEWS_EXCERPT_LIMIT]
    ]

    corpus: str = _join_articles(bodies)
    excerpt_block: str = (
        "\n".join(excerpt_lines) if excerpt_lines else "No keyword-matching sentences."
    )
    user_message = guarded_user_message(
        (
            f"Ticker: {ticker}\n"
            "Write an analysis of the question using only the news articles. "
            "Matching sentences are ground truth, including the sentence that "
            "follows a match. Ticker-specific bullets about options, sweeps, "
            "calls, or puts are answers to options-activity questions. If they "
            "answer the question, quote them. Do not say the articles lack the "
            "answer when those sentences contain it. Your analysis does not "
            "replace the article text."
        ),
        ("USER_QUESTION", question),
        ("MATCHING_SENTENCES", excerpt_block),
        ("NEWS_ARTICLES", corpus),
    )
    summary: str = ""
    try:
        llm = _llm_client()
        result = await llm.chat_completion(
            [
                {"role": "system", "content": NEWS_SEARCH_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=llm._default_max_tokens(),
        )
        summary = result.content.strip()
    except (ValueError, RuntimeError):
        logger.exception("News search LLM failed for %s", ticker)
        summary = (
            "News-agent LLM analysis is unavailable. Use SOURCE EVIDENCE only."
        )

    if not summary:
        summary = "News-agent LLM returned no analysis. Use SOURCE EVIDENCE only."
    return SearchAndSummarizeResponse(summary=summary, articles=articles)

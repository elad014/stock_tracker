import json
import logging
from typing import Any

from fastapi import HTTPException

from constant import CHAT_NEWS_ARTICLE_CHARS, CHAT_NEWS_MAX_ARTICLES
from doc_agent_client import doc_agent_client as doc_agent
from news_agent_client import news_agent_client as news_agent
from stock_manager_client import stock_manager_client as stock_manager

logger = logging.getLogger(__name__)

CHAT_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "ask_user_document",
            "description": (
                "Search the user's uploaded PDF documents only. Use this when "
                "they ask about a document, file, PDF, filing, or uploaded "
                "report. Do not use this for news or article questions. "
                "Pass document_id only if they named a specific file. "
                "Omit document_id to search all of their documents."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "string",
                        "description": (
                            "Path of the PDF relative to the user's folder. "
                            "Omit this field to search every uploaded document."
                        ),
                    },
                    "query": {
                        "type": "string",
                        "description": "The user's question about the document",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_news_summary",
            "description": (
                "Ask news-agent about stored news_articles.text for a ticker. "
                "News-agent searches and ranks article bodies, returns matching "
                "sentences plus article text, and may add an LLM analysis. "
                "Use this for news or article questions. Pass query as the "
                "user's question. Convert company names to tickers "
                "(Alibaba is BABA, Nvidia is NVDA)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock ticker symbol, for example BABA or AAPL",
                    },
                    "query": {
                        "type": "string",
                        "description": (
                            "The user's question about the news articles. "
                            "Pass the question so the stored article text is searched."
                        ),
                    },
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_price",
            "description": (
                "Get the current quote and stored stock summary. Use this when "
                "the user asks about the stock itself (price, change, how it "
                "is doing), including together with news and documents."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock ticker symbol, for example AAPL",
                    },
                },
                "required": ["symbol"],
            },
        },
    },
]


def _tool_error(exc: BaseException) -> str:
    if isinstance(exc, HTTPException):
        return f"Tool error ({exc.status_code}): {exc.detail}"
    return f"Tool error: {exc}"


def _clip_text(text: str, limit: int) -> str:
    stripped: str = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[:limit] + "\n[truncated]"


def _clip_text_preserving_matches(
    text: str,
    matches: list[str],
    limit: int,
) -> str:
    stripped: str = text.strip()
    if len(stripped) <= limit:
        return stripped
    for match in matches:
        needle: str = match.strip()
        if not needle:
            continue
        probe: str = needle[:96]
        pos: int = stripped.find(probe)
        if pos < 0:
            pos = stripped.lower().find(probe.lower())
        if pos < 0:
            continue
        start: int = max(0, pos - min(200, limit // 5))
        end: int = min(len(stripped), start + limit)
        if end - start < limit:
            start = max(0, end - limit)
        chunk: str = stripped[start:end]
        prefix: str = "...\n" if start > 0 else ""
        suffix: str = "\n[truncated]" if end < len(stripped) else ""
        return f"{prefix}{chunk}{suffix}"
    return stripped[:limit] + "\n[truncated]"


def _format_news_evidence(payload: dict[str, Any], ticker: str) -> str:
    summary: str = str(payload.get("summary") or "").strip()
    raw_articles: Any = payload.get("articles")
    articles: list[dict[str, Any]] = [
        item for item in raw_articles if isinstance(item, dict)
    ] if isinstance(raw_articles, list) else []

    lines: list[str] = []
    if summary:
        lines.append("NEWS AGENT ANSWER:")
        lines.append(summary)
        lines.append("")
    lines.append("SOURCE EVIDENCE:")
    if not articles:
        lines.append("No stored article bodies were returned.")
        return "\n".join(lines)

    for index, item in enumerate(articles[:CHAT_NEWS_MAX_ARTICLES], start=1):
        title: str = str(item.get("title") or "Untitled").strip()
        published: str = str(item.get("published_at") or "").strip()
        url: str = str(item.get("url") or "").strip()
        article_id: str = str(item.get("article_id") or "").strip()
        symbol: str = str(item.get("symbol") or ticker).strip()
        lines.append(f"Article {index}:")
        lines.append(f"Title: {title}")
        if published:
            lines.append(f"Published: {published}")
        if url:
            lines.append(f"URL: {url}")
        if article_id:
            lines.append(f"Article id: {article_id}")
        if symbol:
            lines.append(f"Symbol: {symbol}")
        sentences: Any = item.get("matching_sentences")
        quoted: list[str] = []
        if isinstance(sentences, list):
            quoted = [str(s).strip() for s in sentences if str(s).strip()]
            if quoted:
                lines.append("Matching sentences:")
                for sentence in quoted:
                    lines.append(f'"{sentence}"')
        body: str = str(item.get("text") or "").strip()
        if body:
            lines.append("Text:")
            lines.append(
                _clip_text_preserving_matches(
                    body,
                    quoted,
                    CHAT_NEWS_ARTICLE_CHARS,
                )
            )
        lines.append("")
    return "\n".join(lines).strip()


def _format_document_evidence(payload: dict[str, Any]) -> str:
    answer: str = str(payload.get("answer") or "").strip()
    raw_excerpts: Any = payload.get("excerpts")
    excerpts: list[str] = [
        str(item).strip() for item in raw_excerpts if str(item).strip()
    ] if isinstance(raw_excerpts, list) else []
    lines: list[str] = []
    if answer:
        lines.append("DOC AGENT ANSWER:")
        lines.append(answer)
        lines.append("")
    if excerpts:
        lines.append("SOURCE EXCERPTS:")
        for index, excerpt in enumerate(excerpts, start=1):
            lines.append(f"Excerpt {index}:")
            lines.append(_clip_text(excerpt, CHAT_NEWS_ARTICLE_CHARS))
            lines.append("")
    if not lines:
        return "No answer was returned for that document."
    return "\n".join(lines).strip()


def _format_quote(payload: dict[str, Any]) -> str:
    symbol = str(payload.get("symbol") or "").strip().upper() or "UNKNOWN"
    name = str(payload.get("name") or symbol).strip()
    parts: list[str] = [f"{name} ({symbol})"]
    labels: list[tuple[str, str]] = [
        ("close", "Price"),
        ("change", "Change"),
        ("percent_change", "Percent change"),
        ("open", "Open"),
        ("high", "High"),
        ("low", "Low"),
        ("volume", "Volume"),
        ("previous_close", "Previous close"),
        ("fifty_two_week_high", "52-week high"),
        ("fifty_two_week_low", "52-week low"),
    ]
    for key, label in labels:
        value = payload.get(key)
        if value is None or value == "":
            continue
        parts.append(f"{label}: {value}")
    summary = payload.get("stock_summery")
    if isinstance(summary, str) and summary.strip():
        parts.append(f"Summary: {summary.strip()}")
    return ". ".join(parts)


class ChatTools:
    """Execute orchestrator tools with the requesting user's identity bound."""

    def __init__(self, user_id: str) -> None:
        self._user_id = user_id

    async def ask_user_document(self, document_id: str, query: str) -> str:
        relative = document_id.strip()
        question = query.strip()
        if not question:
            return "query is required."
        try:
            payload = await doc_agent.ask_document(
                self._user_id,
                relative or None,
                question,
            )
        except Exception as exc:
            logger.exception("ask_user_document failed for %s", self._user_id)
            return _tool_error(exc)
        return _format_document_evidence(payload)

    async def get_stock_news_summary(self, symbol: str, query: str) -> str:
        ticker: str = symbol.strip().upper()
        if not ticker:
            return "symbol is required."
        question: str = query.strip() or (
            "Summarize the stored news articles for this ticker."
        )
        try:
            payload: dict[str, Any] = await news_agent.search_and_summarize(
                ticker,
                question,
            )
        except Exception as exc:
            logger.exception("get_stock_news_summary failed for %s", ticker)
            return _tool_error(exc)
        return _format_news_evidence(payload, ticker)

    async def get_stock_price(self, symbol: str) -> str:
        ticker = symbol.strip().upper()
        if not ticker:
            return "symbol is required."
        try:
            payload = await stock_manager.get_stock_by_symbol(ticker)
        except Exception as exc:
            logger.exception("get_stock_price failed for %s", ticker)
            return _tool_error(exc)
        if payload is None:
            return f"Symbol not found: {ticker}."
        if not isinstance(payload, dict):
            return f"No quote payload returned for {ticker}."
        return _format_quote(payload)

    async def execute(self, name: str, arguments_json: str) -> str:
        try:
            args: Any = json.loads(arguments_json or "{}")
        except json.JSONDecodeError:
            return "Invalid tool arguments."
        if not isinstance(args, dict):
            return "Invalid tool arguments."

        if name == "ask_user_document":
            return await self.ask_user_document(
                str(args.get("document_id") or ""),
                str(args.get("query") or ""),
            )
        if name == "get_stock_news_summary":
            return await self.get_stock_news_summary(
                str(args.get("symbol") or ""),
                str(args.get("query") or ""),
            )
        if name == "get_stock_price":
            return await self.get_stock_price(str(args.get("symbol") or ""))
        return f"Unknown tool: {name}"

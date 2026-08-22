import json
import logging
from typing import Any

from fastapi import HTTPException

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
                "Search the user's uploaded PDF documents. Call this even when "
                "the user does not name a file, including questions about fiscal "
                "years, filings, guidance, or dates that look like the future. "
                "Pass document_id only if the user named a specific file. "
                "Omit document_id to search all of their documents. Do not guess "
                "filenames. If nothing relevant is found, the tool says so."
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
                "Use this tool to get the latest news and AI-generated "
                "sentiment/summaries for a specific stock ticker."
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
    {
        "type": "function",
        "function": {
            "name": "get_stock_price",
            "description": (
                "Use this tool to get the current real-time price and basic "
                "financial metrics for a specific stock ticker."
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


def _format_news(payload: dict[str, Any]) -> str:
    symbol = str(payload.get("symbol") or "").strip().upper() or "UNKNOWN"
    articles = payload.get("articles")
    if not isinstance(articles, list) or not articles:
        return f"No recent news found for {symbol}."
    lines: list[str] = [f"Latest news for {symbol}:"]
    for article in articles:
        if not isinstance(article, dict):
            continue
        title = str(article.get("title") or "Untitled").strip()
        source = str(article.get("source") or "unknown").strip()
        summary = str(article.get("summary") or "").strip()
        published = str(article.get("published_at") or "").strip()
        headline = f"- {title} ({source})"
        if published:
            headline = f"{headline} [{published}]"
        if summary:
            headline = f"{headline}: {summary}"
        lines.append(headline)
    if len(lines) == 1:
        return f"No recent news found for {symbol}."
    return "\n".join(lines)


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
        answer = str(payload.get("answer") or "").strip()
        return answer or "No answer was returned for that document."

    async def get_stock_news_summary(self, symbol: str) -> str:
        ticker = symbol.strip().upper()
        if not ticker:
            return "symbol is required."
        try:
            payload = await news_agent.get_news(ticker)
        except Exception as exc:
            logger.exception("get_stock_news_summary failed for %s", ticker)
            return _tool_error(exc)
        if not isinstance(payload, dict):
            return f"No news payload returned for {ticker}."
        return _format_news(payload)

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
            return await self.get_stock_news_summary(str(args.get("symbol") or ""))
        if name == "get_stock_price":
            return await self.get_stock_price(str(args.get("symbol") or ""))
        return f"Unknown tool: {name}"

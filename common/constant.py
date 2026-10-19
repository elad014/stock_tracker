import os
import re
from re import Pattern

from llm_guard.prompt import compose_system_prompt

# ---------------------------------------------------------------------------
# Internal service URLs (inter-service HTTP calls)
# ---------------------------------------------------------------------------
STOCK_SERVICE_URL = os.getenv("STOCK_SERVICE_URL", "http://localhost:8001").rstrip("/")
CHAT_SERVICE_URL = os.getenv(
    "CHAT_SERVICE_URL",
    os.getenv("LLM_SERVICE_URL", "http://localhost:8002"),
).rstrip("/")
LLM_SERVICE_URL = os.getenv("LLM_SERVICE_URL", CHAT_SERVICE_URL).rstrip("/")
NEWS_SERVICE_URL = os.getenv("NEWS_SERVICE_URL", "http://localhost:8003").rstrip("/")
DOC_SERVICE_URL = os.getenv("DOC_SERVICE_URL", "http://localhost:8004").rstrip("/")
UI_SERVICE_URL = os.getenv("UI_SERVICE_URL", "http://localhost:8000").rstrip("/")

# ---------------------------------------------------------------------------
# Internal auth (service-to-service API key)
# ---------------------------------------------------------------------------
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")
INTERNAL_API_KEY_HEADER = "X-Internal-Api-Key"

# ---------------------------------------------------------------------------
# Ticker symbols (AAPL, BRK.A)
# ---------------------------------------------------------------------------
TICKER_PATTERN: Pattern[str] = re.compile(r"^[A-Z]{1,5}(?:[.-][A-Z])?$")

# ---------------------------------------------------------------------------
# External provider base URLs
# ---------------------------------------------------------------------------
TWELVE_DATA_BASE_URL = "https://api.twelvedata.com"
FINNHUB_BASE_URL = "https://finnhub.io/api/v1"
RESEND_API_URL = "https://api.resend.com/emails"

# ---------------------------------------------------------------------------
# Article extraction (trafilatura / HTTP fetch)
# ---------------------------------------------------------------------------
ARTICLE_EXTRACT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)
ARTICLE_EXTRACT_TIMEOUT_SECONDS = 20.0
ARTICLE_EXTRACT_MAX_BYTES = 2_000_000
ARTICLE_EXTRACT_MAX_CHARS = 12_000
ARTICLE_EXTRACT_MAX_REDIRECTS = 3
ARTICLE_EXTRACT_RETRY_LIMIT = 30
ARTICLE_EXTRACT_MIN_CHARS = 120
ARTICLE_CANNOT_EXTRACT_MESSAGE = "Cannot extract the article"

# ---------------------------------------------------------------------------
# News article retention (calendar days, inclusive)
# ---------------------------------------------------------------------------
ARTICLE_RETENTION_DAYS = 7
NEWS_SEARCH_MAX_CHARS = 24_000
NEWS_SEARCH_MAX_QUERY_CHARS = 1_000
NEWS_SEARCH_SYSTEM_PROMPT = compose_system_prompt(
    "You are a financial news assistant.",
    "Write an analysis using only the news articles and matching sentences. "
    "Matching sentences are ground truth, including a following sentence that "
    "completes the fact. If a matching sentence names the queried ticker and "
    "answers the question, quote it and answer from it. Unusual options, "
    "sweeps, calls, or puts for that ticker are evidence of options activity. "
    "Do not say the articles lack the answer when those sentences contain it. "
    "Your analysis does not replace the article text. If nothing relevant is "
    "present, say so.",
)
NEWS_SUMMARIZE_SYSTEM_PROMPT = compose_system_prompt(
    "You are a financial news analyst.",
    "Using only the untrusted source text and the quote figures provided outside "
    "the blocks, respond with: "
    "1) A short news summary in 2-4 clear sentences. "
    "2) A final line exactly in the form: Outlook: UP|DOWN|NEUTRAL",
)
# Cap HTTP LLM triggers only. Cron news-update is not subject to the cooldown
# and still summarizes every stock that has news.
NEWS_UPDATE_HTTP_COOLDOWN_SECONDS = 15 * 60
ARTICLE_SUMMARIZE_MAX_ATTEMPTS = 20
ARTICLE_SUMMARIZE_WINDOW_SECONDS = 60
# Stock-service HTTP job triggers. Cron is not subject to these cooldowns.
DAILY_UPDATE_HTTP_COOLDOWN_SECONDS = 15 * 60
CLEANUP_ARCHIVE_HTTP_COOLDOWN_SECONDS = 15 * 60
ALERTS_CHECK_HTTP_COOLDOWN_SECONDS = 15 * 60

# ---------------------------------------------------------------------------
# Object storage (Supabase Storage over the S3 protocol, or AWS S3)
#
# Supabase only accepts SigV4 with path-style addressing; any other combination
# fails with SignatureDoesNotMatch. Both values are also valid for AWS S3, so
# the same client works against either backend.
# ---------------------------------------------------------------------------
S3_SIGNATURE_VERSION = "s3v4"
S3_ADDRESSING_STYLE = "path"
S3_DEFAULT_REGION = "us-east-1"
S3_DEFAULT_CONTENT_TYPE = "application/octet-stream"
S3_CONNECT_TIMEOUT_SECONDS = 10
S3_READ_TIMEOUT_SECONDS = 60
S3_MAX_ATTEMPTS = 3
S3_PRESIGNED_EXPIRE_SECONDS = 3600
S3_MULTIPART_THRESHOLD_BYTES = 8 * 1024 * 1024
S3_MULTIPART_CHUNK_BYTES = 8 * 1024 * 1024
# boto3 1.36+ sends checksums on every request by default. Supabase Storage
# does not implement those headers, so keep them on operations that actually
# require them. DeleteObjects still requires a checksum even then, which is
# why the client deletes keys one at a time with DeleteObject instead.
S3_REQUEST_CHECKSUM = "when_required"
S3_RESPONSE_CHECKSUM = "when_required"

# S3 has no real folders, only key prefixes. The Supabase dashboard fakes an
# empty folder with a 0-byte object of this name and expects clients to hide it
# from listings. Matching the convention keeps folders created by code and by
# the dashboard indistinguishable.
S3_FOLDER_PLACEHOLDER = ".emptyFolderPlaceholder"

# ---------------------------------------------------------------------------
# LLM defaults (chat-service / LiteLLM)
# ---------------------------------------------------------------------------
DEFAULT_MODEL = "gemini/gemini-2.5-flash"
DEPRECATED_GEMINI_MODELS = {
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-1.5-flash-latest",
    "gemini-1.5-pro",
    "gemini-1.5-pro-latest",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini/gemini-1.5-flash",
    "gemini/gemini-1.5-flash-8b",
    "gemini/gemini-1.5-flash-latest",
    "gemini/gemini-1.5-pro",
    "gemini/gemini-1.5-pro-latest",
    "gemini/gemini-2.0-flash",
    "gemini/gemini-2.0-flash-lite",
}

# ---------------------------------------------------------------------------
# Doc Service (RAG over user documents)
#
# The embedding model decides the vector width, and the width is baked into the
# document_vectors column, so a model swap means a re-index. Defaults match the
# rest of the stack (Gemini / GEMINI_API_KEY). dimensions=768 is passed on
# every embed call so Gemini Matryoshka output matches the column.
# ---------------------------------------------------------------------------
DEFAULT_EMBEDDING_MODEL = "gemini/gemini-embedding-001"
EMBEDDING_MODEL = (
    os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL).strip()
    or DEFAULT_EMBEDDING_MODEL
)
EMBEDDING_DIMENSIONS = 768
EMBEDDING_BATCH_SIZE = 16

DOC_CHUNK_CHARS = 1_200
DOC_CHUNK_OVERLAP = 200
DOC_TABLE_MAX_CHARS = 4_000
DOC_DEFAULT_SECTION = "Introduction"
DOC_TOP_K = 5
DOC_ALL_DOCS_TOP_K = 10
DOC_MAX_QUERY_CHARS = 1_000
DOC_CONTEXT_MAX_CHARS = 12_000

DOC_RAG_SYSTEM_PROMPT = compose_system_prompt(
    "You are an accurate document assistant.",
    "Answer the user's query based STRICTLY on the provided document excerpts. "
    "Do not hallucinate or use outside knowledge. If the answer is not in the "
    "excerpts, state that clearly.",
)
DOC_NOT_FOUND_ANSWER = "Document not found or no relevant information."

# 10 is live S3 inventory. Weekly events stay after delete so re-upload
# cannot reset embedding spend.
DOC_MAX_INDEXED_FILES = 10
DOC_MAX_INGESTS_PER_WEEK = 20
DOC_INGEST_WEEK_DAYS = 7

# Burst cap on HTTP ingest/ask.
DOC_INGEST_MAX_ATTEMPTS = 5
DOC_INGEST_WINDOW_SECONDS = 60
DOC_ASK_MAX_ATTEMPTS = 20
DOC_ASK_WINDOW_SECONDS = 60

# ---------------------------------------------------------------------------
# Chat Service (orchestrator)
# ---------------------------------------------------------------------------
CHAT_MAX_TOOL_ROUNDS = 5
CHAT_MAX_ATTEMPTS = 20
CHAT_WINDOW_SECONDS = 60
CHAT_NEWS_MAX_ARTICLES = 8
CHAT_NEWS_ARTICLE_CHARS = 2500
CHAT_ORCHESTRATOR_SYSTEM_PROMPT = compose_system_prompt(
    "You are a highly capable and professional AI financial and document assistant. "
    "You have access to specialized tools. Never invent article text, numbers, "
    "forecasts, dates, or causes of stock moves. "
    "Before you say you cannot find an answer, search every service in the "
    "same round: ask_user_document, get_stock_news_summary when a company or "
    "person implies a ticker (Nvidia and Jen-Hsun Huang are NVDA), and "
    "get_stock_price when a ticker is implied. Do not ask the user for a "
    "topic or a clearer question. Use their words as the search. "
    "If one service contains the fact, answer from that service only. "
    "Say you do not know only after documents, news, and the stock quote "
    "all return nothing relevant. "
    "Pick tools from what the user asked about: "
    "News or a news article: call get_stock_news_summary with the ticker "
    "(Alibaba is BABA, Nvidia is NVDA) and pass the user's question as query. "
    "That tool returns NEWS AGENT ANSWER (optional analysis) and SOURCE "
    "EVIDENCE (matching sentences and article text). For factual questions, "
    "answer from matching sentences first. If a sentence contains the answer, "
    "use it. Do not trust NEWS AGENT ANSWER over SOURCE EVIDENCE. Do not say "
    "the articles lack the answer when SOURCE EVIDENCE contains it. "
    "Do not call ask_user_document for a news/article question. "
    "Uploaded documents, PDFs, files, or filings: call ask_user_document once "
    "per distinct filing topic, in the same round as the other tools. "
    "Put only that topic in query. Do not paste the whole user message. "
    "If they named a file, pass it as document_id; otherwise omit document_id. "
    "Use SOURCE EXCERPTS as document evidence; DOC AGENT ANSWER is analysis only. "
    "The stock itself (price, quote, move): call get_stock_price. "
    "Why a stock is up or down, or a conclusion about a move: call "
    "get_stock_price, get_stock_history, and get_stock_news_summary. "
    "Use history range 5D unless the user names a longer window. "
    "Explain the move only from price, history, and SOURCE EVIDENCE. "
    "If the stored article text does not explain the move, say so clearly. "
    "Do not invent catalysts. "
    "News and documents: call get_stock_news_summary and ask_user_document. "
    "News, documents, and the stock: call get_stock_news_summary, "
    "ask_user_document, and get_stock_price. "
    "When the user asked for more than one source, answer from every tool "
    "you called. If one of those sources has nothing, say so for that source "
    "and still use the others. When the user asked one fact, do not mention "
    "the services that lacked it. "
    "Keep the reply short. Use one sentence for the stock price and history "
    "together, up to two sentences for news, and up to two sentences for "
    "documents. When the user asks only for one source, use at most three "
    "sentences. "
    "Each sentence must state the fact that source returned. For news, name "
    "two or three distinct concrete facts from different articles when the "
    "evidence has them, not a general theme. "
    "If the excerpts contain the topic, use them. "
    "Do not say a source lacks the topic when its text contains it. "
    "Write the reply in plain language. Do not print tool section names "
    "(NEWS AGENT ANSWER, SOURCE EVIDENCE, SOURCE EXCERPTS, DOC AGENT ANSWER) "
    "or the tokens HISTORICAL_REPORTED and FUTURE_ESTIMATE. Do not print "
    "confidence labels such as LOW, MEDIUM, or HIGH. "
    "Call a figure a reported result when its fiscal period has already ended. "
    "Call it guidance or an estimate when it is guidance, an analyst estimate, "
    "a forecast, or a period that has not ended. Do not describe ended "
    "fiscal-year revenue as a forecast. "
    "Name the period of every dollar or percent figure: full fiscal year, "
    "quarter, guidance, or the date range. If two figures cover different "
    "periods, say that before comparing them. If the source does not name "
    "the period, say the period is not in the source. "
    "Say sources agree or confirm each other only when both tool results "
    "state the same specific claim: the same event, number, or action. "
    "Sharing a keyword, company type, or topic is not agreement. Before "
    "claiming agreement, check that the filing text states the same action "
    "the news reports, and not only mentions the same word. If the sources "
    "cover the same topic but state different things, say they are related "
    "but do not state the same claim, and name each source's own point. If "
    "one source says an action did not happen, say the sources differ. If "
    "nothing matches, say there is no overlap. State only what a source "
    "says. Do not add inferences, implications, or reasons the source does "
    "not state, such as saying a development reduces reliance on a company. "
    "If the retrieved excerpts do not mention a topic, say the "
    "retrieved excerpts do not cover it. Use that wording in every sentence, "
    "including the conclusion. Do not say the document, filing, or "
    "10-K does not contain or address that topic, and do not say the "
    "document has no information on it. Do not answer that topic "
    "with a different excerpt. "
    "Name a catalyst for a specific day's move only when the article text "
    "mentions that day or that move. Otherwise list the articles as recent "
    "news and say they do not explain that day's move. "
    "If evidence is insufficient, say so instead of guessing. "
    "Never refuse a document question as future without first calling "
    "ask_user_document. Do not guess filenames. "
    "Only after the matching tools return nothing relevant, tell the user you "
    "cannot find that information.",
)

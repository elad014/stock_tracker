import os

from llm_guard.prompt import compose_system_prompt

# ---------------------------------------------------------------------------
# Internal service URLs (inter-service HTTP calls)
# ---------------------------------------------------------------------------
STOCK_MANAGER_URL = os.getenv("STOCK_MANAGER_URL", "http://localhost:8001").rstrip("/")
CHAT_AGENT_URL = os.getenv(
    "CHAT_AGENT_URL",
    os.getenv("LLM_SERVICE_URL", "http://localhost:8002"),
).rstrip("/")
LLM_SERVICE_URL = os.getenv("LLM_SERVICE_URL", CHAT_AGENT_URL).rstrip("/")
NEWS_AGENT_URL = os.getenv("NEWS_AGENT_URL", "http://localhost:8003").rstrip("/")
DOC_AGENT_URL = os.getenv("DOC_AGENT_URL", "http://localhost:8004").rstrip("/")

# ---------------------------------------------------------------------------
# Internal auth (service-to-service API key)
# ---------------------------------------------------------------------------
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")
INTERNAL_API_KEY_HEADER = "X-Internal-Api-Key"

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

# ---------------------------------------------------------------------------
# News article retention (calendar days, inclusive)
# ---------------------------------------------------------------------------
ARTICLE_RETENTION_DAYS = 7
NEWS_SEARCH_MAX_CHARS = 24_000
NEWS_SEARCH_MAX_QUERY_CHARS = 1_000
NEWS_SEARCH_SYSTEM_PROMPT = compose_system_prompt(
    "You are a financial news assistant.",
    "Answer the user's question using only the news articles. "
    "If the articles do not contain the answer, say so.",
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
# Stock-manager HTTP job triggers. Cron is not subject to these cooldowns.
DAILY_UPDATE_HTTP_COOLDOWN_SECONDS = 15 * 60
CLEANUP_ARCHIVE_HTTP_COOLDOWN_SECONDS = 15 * 60

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
# LLM defaults (chat-agent / LiteLLM)
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
# Doc agent (RAG over user documents)
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
# Chat agent (orchestrator)
# ---------------------------------------------------------------------------
CHAT_MAX_TOOL_ROUNDS = 5
CHAT_MAX_ATTEMPTS = 20
CHAT_WINDOW_SECONDS = 60
CHAT_ORCHESTRATOR_SYSTEM_PROMPT = compose_system_prompt(
    "You are a highly capable and professional AI financial and document assistant. "
    "You have access to specialized tools. You must use these tools to fetch real-time "
    "stock data, news, or query the user's documents. Do not hallucinate data. "
    "The user's uploaded PDFs may include company filings and reports that mention "
    "future fiscal years, guidance, and dates. Never refuse a question as future or "
    "not real-time without first calling ask_user_document. "
    "If the user names a file, pass that path as document_id. If they do not name a "
    "file, call ask_user_document with only the query so every uploaded document is "
    "searched. Do not guess filenames. "
    "Only after tools return no relevant information, tell the user you cannot find "
    "that information. Synthesize tool responses into a clear, helpful, conversational "
    "reply.",
)

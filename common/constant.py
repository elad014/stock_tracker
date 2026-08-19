import os

# ---------------------------------------------------------------------------
# Internal service URLs (inter-service HTTP calls)
# ---------------------------------------------------------------------------
STOCK_MANAGER_URL = os.getenv("STOCK_MANAGER_URL", "http://localhost:8001").rstrip("/")
LLM_SERVICE_URL = os.getenv("LLM_SERVICE_URL", "http://localhost:8002").rstrip("/")
NEWS_AGENT_URL = os.getenv("NEWS_AGENT_URL", "http://localhost:8003").rstrip("/")

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

# ---------------------------------------------------------------------------
# News article retention (calendar days, inclusive)
# ---------------------------------------------------------------------------
ARTICLE_RETENTION_DAYS = 7
NEWS_SEARCH_MAX_CHARS = 24_000
NEWS_SEARCH_SYSTEM_PROMPT = (
    "You are a financial news assistant. Answer the user's query based strictly "
    "on the provided news articles. If the articles do not contain the answer, say so."
)

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
# LLM defaults (llm-service / LiteLLM)
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

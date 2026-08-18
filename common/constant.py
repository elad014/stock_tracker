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

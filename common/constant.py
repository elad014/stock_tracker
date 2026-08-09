import os

STOCK_MANAGER_URL = os.getenv("STOCK_MANAGER_URL", "http://localhost:8001").rstrip("/")
LLM_SERVICE_URL = os.getenv("LLM_SERVICE_URL", "http://localhost:8002").rstrip("/")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")
INTERNAL_API_KEY_HEADER = "X-Internal-Api-Key"

TWELVE_DATA_BASE_URL = "https://api.twelvedata.com"
RESEND_API_URL = "https://api.resend.com/emails"

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

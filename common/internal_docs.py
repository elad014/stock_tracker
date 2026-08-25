"""Protect FastAPI /docs, /redoc, and /openapi.json with the internal API key."""

import base64
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse

from constant import INTERNAL_API_KEY_HEADER
from internal_auth import expected_internal_api_key, internal_api_key_matches

DOCS_PATH = "/docs"
REDOC_PATH = "/redoc"
OPENAPI_PATH = "/openapi.json"
_WWW_AUTHENTICATE = {"WWW-Authenticate": 'Basic realm="internal-docs"'}


def disabled_docs_kwargs() -> dict[str, None]:
    """Pass to FastAPI() so the unauthenticated default docs routes are not mounted."""
    return {
        "docs_url": None,
        "redoc_url": None,
        "openapi_url": None,
    }


def _password_from_basic(authorization: str) -> str | None:
    scheme, _, credential = authorization.partition(" ")
    if scheme.lower() != "basic" or not credential:
        return None
    try:
        decoded = base64.b64decode(credential, validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    if ":" not in decoded:
        return None
    _username, password = decoded.split(":", 1)
    return password


def extract_docs_api_key(request: Request) -> str | None:
    header = request.headers.get(INTERNAL_API_KEY_HEADER)
    if header and header.strip():
        return header.strip()
    query_key = request.query_params.get("api_key")
    if query_key and query_key.strip():
        return query_key.strip()
    authorization = request.headers.get("Authorization")
    if authorization:
        return _password_from_basic(authorization)
    return None


def require_docs_key(request: Request) -> str:
    expected = expected_internal_api_key()
    provided = extract_docs_api_key(request)
    if not internal_api_key_matches(provided, expected):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid internal API key",
            headers=_WWW_AUTHENTICATE,
        )
    return provided or expected


def _openapi_url_for_ui(request: Request, key: str) -> str:
    if request.query_params.get("api_key"):
        return f"{OPENAPI_PATH}?api_key={quote(key, safe='')}"
    return OPENAPI_PATH


def mount_protected_docs(app: FastAPI) -> None:
    """Serve schema and UIs only when the caller presents INTERNAL_API_KEY."""

    @app.get(OPENAPI_PATH, include_in_schema=False)
    async def openapi_json(request: Request) -> JSONResponse:
        require_docs_key(request)
        return JSONResponse(app.openapi())

    @app.get(DOCS_PATH, include_in_schema=False)
    async def swagger_ui(request: Request) -> HTMLResponse:
        key = require_docs_key(request)
        return get_swagger_ui_html(
            openapi_url=_openapi_url_for_ui(request, key),
            title=f"{app.title} - Swagger UI",
            swagger_ui_parameters={"persistAuthorization": True},
        )

    @app.get(REDOC_PATH, include_in_schema=False)
    async def redoc_ui(request: Request) -> HTMLResponse:
        key = require_docs_key(request)
        return get_redoc_html(
            openapi_url=_openapi_url_for_ui(request, key),
            title=f"{app.title} - ReDoc",
        )

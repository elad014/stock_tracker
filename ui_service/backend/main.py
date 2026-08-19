import os
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from starlette.responses import Response

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "common"))

from database_client import db
from object_storage_client import ObjectStorageError
from routers.admin_routes import router as admin_router
from routers.auth_routes import router as auth_router
from routers.documents_routes import router as documents_router
from routers.stocks_routes import router as stocks_router
from routers.watchlist_routes import router as watchlist_router

app = FastAPI(title="Stock Tracker API")


@app.on_event("shutdown")
async def shutdown() -> None:
    await db.close()


@app.exception_handler(ObjectStorageError)
async def handle_object_storage_error(
    _request: Request,
    exc: ObjectStorageError,
) -> JSONResponse:
    """Storage outages are upstream failures, not client mistakes."""
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"detail": f"Document storage unavailable: {exc}"},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def redirect_legacy_stock_page(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Browser refresh of the old /stocks/{id} page hit the API and returned 401.

    Document navigations (Accept: text/html, no Authorization) are redirected to
    /stock/{id}. Axios API calls keep Authorization and still hit /stocks/{id}.
    """
    path: str = request.url.path
    parts: list[str] = [part for part in path.split("/") if part]
    if (
        request.method == "GET"
        and len(parts) == 2
        and parts[0] == "stocks"
        and "authorization" not in request.headers
        and "text/html" in request.headers.get("accept", "")
    ):
        return RedirectResponse(url=f"/stock/{parts[1]}", status_code=307)
    return await call_next(request)

app.include_router(auth_router)
app.include_router(watchlist_router)
app.include_router(stocks_router)
app.include_router(admin_router)
app.include_router(documents_router)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

    @app.get("/{path:path}")
    async def serve_frontend(path: str) -> FileResponse:
        file_path = FRONTEND_DIR / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIR / "index.html")

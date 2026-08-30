from __future__ import annotations

from contextlib import asynccontextmanager
from importlib import import_module
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import logging
import sys
import types
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
logging.disable(logging.CRITICAL)
_PROJECT_PREFIXES = (
    "article_extractor",
    "chat_agent_client",
    "constant",
    "database_client",
    "db_logics",
    "deps",
    "doc_agent_client",
    "email_client",
    "embedding_client",
    "llm_guard",
    "llm_limits",
    "llm_provider_client",
    "jobs",
    "models",
    "news_agent_client",
    "news_provider_client",
    "object_storage_client",
    "routers",
    "services",
    "stock_manager_client",
    "stock_provider_client",
)


class SimpleModel:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)
        self.model_fields_set = set(kwargs)

    def model_dump(self) -> dict[str, Any]:
        return dict(self.__dict__)

    def __repr__(self) -> str:
        fields = ", ".join(f"{key}={value!r}" for key, value in self.__dict__.items())
        return f"{self.__class__.__name__}({fields})"


class FakeHTTPException(Exception):
    def __init__(self, status_code: int, detail: Any = None, headers: dict[str, str] | None = None) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.headers = headers or None


class FakeResponse:
    def __init__(self, status_code: int = 200, payload: Any = None, text: str = "", headers: dict[str, str] | None = None) -> None:
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text
        self.headers = headers or {}

    def json(self) -> Any:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            exc = sys.modules["requests"].HTTPError(f"HTTP {self.status_code}")
            exc.response = self
            raise exc


class AsyncTransaction:
    def __init__(self, conn: Any = "conn") -> None:
        self.conn = conn

    async def __aenter__(self) -> Any:
        return self.conn

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False


class FakeDB:
    def __init__(self) -> None:
        self.fetch_one_results: list[Any] = []
        self.fetch_all_results: list[Any] = []
        self.execute_results: list[str] = []
        self.fetch_one_calls: list[tuple[str, tuple[Any, ...], Any]] = []
        self.fetch_all_calls: list[tuple[str, tuple[Any, ...], Any]] = []
        self.execute_calls: list[tuple[str, tuple[Any, ...], Any]] = []
        self.executemany_calls: list[tuple[str, list[tuple[Any, ...]], Any]] = []
        self.transactions: list[AsyncTransaction] = []

    async def fetch_one(self, sql: str, *params: Any, conn: Any = None) -> Any:
        self.fetch_one_calls.append((sql, params, conn))
        if self.fetch_one_results:
            return self.fetch_one_results.pop(0)
        return None

    async def fetch_all(self, sql: str, *params: Any, conn: Any = None) -> list[Any]:
        self.fetch_all_calls.append((sql, params, conn))
        if self.fetch_all_results:
            return self.fetch_all_results.pop(0)
        return []

    async def execute(self, sql: str, *params: Any, conn: Any = None) -> str:
        self.execute_calls.append((sql, params, conn))
        if self.execute_results:
            return self.execute_results.pop(0)
        return "DELETE 0"

    async def executemany(self, sql: str, args: list[tuple[Any, ...]], conn: Any = None) -> None:
        self.executemany_calls.append((sql, args, conn))

    @asynccontextmanager
    async def transaction(self):
        tx = AsyncTransaction(conn=f"conn-{len(self.transactions) + 1}")
        self.transactions.append(tx)
        yield tx.conn


def install_dependency_stubs() -> None:
    if "fastapi" not in sys.modules:
        fastapi = ModuleType("fastapi")
        fastapi.HTTPException = FakeHTTPException
        class APIRouter:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                self.args = args
                self.kwargs = kwargs
                self.routes: list[tuple[str, str, Any]] = []
            def _decorator(self, method: str, path: str, **_kwargs: Any):
                def register(func: Any) -> Any:
                    self.routes.append((method, path, func))
                    return func
                return register
            def get(self, path: str, **kwargs: Any):
                return self._decorator("GET", path, **kwargs)
            def post(self, path: str, **kwargs: Any):
                return self._decorator("POST", path, **kwargs)
            def put(self, path: str, **kwargs: Any):
                return self._decorator("PUT", path, **kwargs)
            def delete(self, path: str, **kwargs: Any):
                return self._decorator("DELETE", path, **kwargs)
        fastapi.APIRouter = APIRouter
        fastapi.Depends = lambda dependency=None, **_kwargs: dependency
        fastapi.Security = lambda dependency=None, **_kwargs: dependency
        fastapi.Path = lambda default=..., **_kwargs: default
        fastapi.Query = lambda default=..., **_kwargs: default
        fastapi.File = lambda default=..., **_kwargs: default
        fastapi.Form = lambda default=None, **_kwargs: default
        fastapi.UploadFile = type("UploadFile", (), {})
        fastapi.Request = type("Request", (), {})
        status = types.SimpleNamespace(
            HTTP_200_OK=200,
            HTTP_201_CREATED=201,
            HTTP_400_BAD_REQUEST=400,
            HTTP_401_UNAUTHORIZED=401,
            HTTP_403_FORBIDDEN=403,
            HTTP_404_NOT_FOUND=404,
            HTTP_409_CONFLICT=409,
            HTTP_413_REQUEST_ENTITY_TOO_LARGE=413,
            HTTP_429_TOO_MANY_REQUESTS=429,
            HTTP_500_INTERNAL_SERVER_ERROR=500,
            HTTP_502_BAD_GATEWAY=502,
        )
        fastapi.status = status
        security = ModuleType("fastapi.security")
        security.HTTPAuthorizationCredentials = type(
            "HTTPAuthorizationCredentials",
            (),
            {"__init__": lambda self, scheme="Bearer", credentials="": (setattr(self, "scheme", scheme), setattr(self, "credentials", credentials), None)[-1]},
        )
        security.HTTPBearer = type("HTTPBearer", (), {"__init__": lambda self, auto_error=True: setattr(self, "auto_error", auto_error)})
        security.APIKeyHeader = type("APIKeyHeader", (), {"__init__": lambda self, **kwargs: self.__dict__.update(kwargs)})
        sys.modules["fastapi"] = fastapi
        sys.modules["fastapi.security"] = security

    if "dotenv" not in sys.modules:
        dotenv = ModuleType("dotenv")
        dotenv.load_dotenv = lambda *args, **kwargs: False
        sys.modules["dotenv"] = dotenv

    if "asyncpg" not in sys.modules:
        asyncpg = ModuleType("asyncpg")
        asyncpg.Connection = type("Connection", (), {})
        asyncpg.Pool = type("Pool", (), {})
        async def create_pool(*_args: Any, **_kwargs: Any) -> Any:
            raise AssertionError("Tests must not create a real database pool")
        asyncpg.create_pool = create_pool
        sys.modules["asyncpg"] = asyncpg

    if "bcrypt" not in sys.modules:
        bcrypt = ModuleType("bcrypt")
        bcrypt.gensalt = lambda: b"salt"
        bcrypt.hashpw = lambda password, _salt: b"hashed:" + password
        bcrypt.checkpw = lambda plain, hashed: hashed == b"hashed:" + plain
        sys.modules["bcrypt"] = bcrypt

    if "jose" not in sys.modules:
        jose = ModuleType("jose")
        class JWTError(Exception):
            pass
        jwt = types.SimpleNamespace(
            encode=lambda payload, *_args, **_kwargs: "encoded:" + repr(payload),
            decode=lambda token, *_args, **_kwargs: token if isinstance(token, dict) else {},
        )
        jose.JWTError = JWTError
        jose.jwt = jwt
        sys.modules["jose"] = jose

    if "httpx" not in sys.modules:
        httpx = ModuleType("httpx")
        httpx.HTTPStatusError = type("HTTPStatusError", (Exception,), {})
        httpx.RequestError = type("RequestError", (Exception,), {})
        httpx.Response = FakeResponse
        class AsyncClient:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                self.args = args
                self.kwargs = kwargs
            async def __aenter__(self) -> "AsyncClient":
                return self
            async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
                return False
            async def get(self, *_args: Any, **_kwargs: Any) -> FakeResponse:
                raise AssertionError("Tests must mock httpx.AsyncClient.get")
            async def post(self, *_args: Any, **_kwargs: Any) -> FakeResponse:
                raise AssertionError("Tests must mock httpx.AsyncClient.post")
            async def put(self, *_args: Any, **_kwargs: Any) -> FakeResponse:
                raise AssertionError("Tests must mock httpx.AsyncClient.put")
            async def delete(self, *_args: Any, **_kwargs: Any) -> FakeResponse:
                raise AssertionError("Tests must mock httpx.AsyncClient.delete")
            async def request(self, *_args: Any, **_kwargs: Any) -> FakeResponse:
                raise AssertionError("Tests must mock httpx.AsyncClient.request")
        httpx.AsyncClient = AsyncClient
        sys.modules["httpx"] = httpx

    if "requests" not in sys.modules:
        requests = ModuleType("requests")
        requests.HTTPError = type("HTTPError", (Exception,), {})
        requests.RequestException = type("RequestException", (Exception,), {})
        requests.get = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Tests must mock requests.get"))
        requests.post = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Tests must mock requests.post"))
        sys.modules["requests"] = requests

    if "litellm" not in sys.modules:
        litellm = ModuleType("litellm")
        async def acompletion(**_kwargs: Any) -> Any:
            raise AssertionError("Tests must mock litellm.acompletion")
        async def aembedding(**_kwargs: Any) -> Any:
            raise AssertionError("Tests must mock litellm.aembedding")
        litellm.acompletion = acompletion
        litellm.aembedding = aembedding
        sys.modules["litellm"] = litellm

    if "boto3" not in sys.modules:
        boto3 = ModuleType("boto3")
        boto3.client = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Tests must mock boto3.client"))
        sys.modules["boto3"] = boto3
    if "botocore.config" not in sys.modules:
        botocore = ModuleType("botocore")
        config = ModuleType("botocore.config")
        config.Config = type("Config", (), {"__init__": lambda self, **kwargs: self.__dict__.update(kwargs)})
        exceptions = ModuleType("botocore.exceptions")
        exceptions.BotoCoreError = type("BotoCoreError", (Exception,), {})
        class ClientError(Exception):
            def __init__(self, response: dict[str, Any] | None = None, operation_name: str = "") -> None:
                super().__init__(operation_name)
                self.response = response or {"Error": {"Code": "Error"}}
        exceptions.ClientError = ClientError
        sys.modules["botocore"] = botocore
        sys.modules["botocore.config"] = config
        sys.modules["botocore.exceptions"] = exceptions

    if "boto3.s3.transfer" not in sys.modules:
        boto3_s3 = ModuleType("boto3.s3")
        transfer = ModuleType("boto3.s3.transfer")
        transfer.TransferConfig = type("TransferConfig", (), {"__init__": lambda self, **kwargs: self.__dict__.update(kwargs)})
        sys.modules["boto3.s3"] = boto3_s3
        sys.modules["boto3.s3.transfer"] = transfer

    if "trafilatura" not in sys.modules:
        trafilatura = ModuleType("trafilatura")
        trafilatura.extract = lambda *_args, **_kwargs: None
        sys.modules["trafilatura"] = trafilatura

    if "pymupdf" not in sys.modules:
        pymupdf = ModuleType("pymupdf")
        pymupdf.open = lambda *_args, **_kwargs: (_ for _ in ()).throw(Exception("mock pymupdf.open"))
        sys.modules["pymupdf"] = pymupdf
    if "pymupdf4llm" not in sys.modules:
        pymupdf4llm = ModuleType("pymupdf4llm")
        pymupdf4llm.to_markdown = lambda *_args, **_kwargs: ""
        sys.modules["pymupdf4llm"] = pymupdf4llm


def install_model_stubs() -> None:
    models = ModuleType("models")
    sys.modules["models"] = models
    submodules = {
        "auth": ["LoginRequest", "MessageResponse", "PasswordResetConfirm", "PasswordResetRequest", "RegisterRequest", "RegisterResponse", "Token", "UpdateSettingsRequest", "UpdateSettingsResponse"],
        "watchlist": ["AddWatchlistRequest", "WatchlistStock"],
        "stocks": ["StockArticle", "StockDetails", "StockHistoryBar", "StockQuoteResponse", "StockSummeryResponse", "MessageResponse", "AddWatchlistRequest", "RemoveWatchlistRequest", "JobTriggerResponse", "UpdateStockSummeryRequest"],
        "documents": ["CreateFolderRequest", "DocumentTree", "DownloadUrlResponse", "MoveFileRequest", "TreeNode"],
        "chat": ["ChatRequest", "ChatResponse", "ChatUsage", "SessionClearResponse"],
        "admin": ["AdminCreateUserRequest", "AdminSetPasswordRequest", "AdminUpdateUserRequest", "AdminUser", "AssignStockRequest", "CreateAdminStockRequest"],
        "news": ["NewsArticle", "SearchAndSummarizeRequest", "SearchAndSummarizeResponse", "SearchEvidenceArticle", "StockNewsResponse", "StoredNewsArticle", "StoredStockNewsResponse"],
        "articles": ["ArticleRecord", "ArticleSummaryResponse", "ArticleSyncResponse", "MessageResponse"],
        "docs": ["AskRequest", "AskResponse", "DeleteVectorsResponse", "IngestRequest", "IngestResponse", "PurgeUserResponse"],
    }
    for submodule, class_names in submodules.items():
        module = ModuleType(f"models.{submodule}")
        for class_name in class_names:
            setattr(module, class_name, type(class_name, (SimpleModel,), {}))
        setattr(models, submodule, module)
        sys.modules[f"models.{submodule}"] = module


def reset_project_modules() -> None:
    for name in list(sys.modules):
        if name in _PROJECT_PREFIXES or name.startswith(tuple(prefix + "." for prefix in _PROJECT_PREFIXES)):
            sys.modules.pop(name, None)


def add_project_paths(*relative_paths: str) -> None:
    paths = [ROOT / path for path in relative_paths]
    if not relative_paths:
        paths = [ROOT / "ui_service" / "backend", ROOT / "doc_agent" / "backend", ROOT / "common"]
    service_paths = [path for path in paths if path.name != "common"]
    common_paths = [path for path in paths if path.name == "common"]
    ordered = service_paths + common_paths
    known_roots = {
        str(ROOT / "common"),
        str(ROOT / "ui_service" / "backend"),
        str(ROOT / "stock_manager" / "backend"),
        str(ROOT / "news_agent" / "backend"),
        str(ROOT / "chat_agent" / "backend"),
        str(ROOT / "doc_agent" / "backend"),
    }
    sys.path[:] = [item for item in sys.path if item not in known_roots]
    for path in reversed(ordered):
        sys.path.insert(0, str(path))


def import_project_module(module_name: str, *relative_paths: str, model_stubs: bool = False) -> ModuleType:
    install_dependency_stubs()
    reset_project_modules()
    if model_stubs:
        install_model_stubs()
    add_project_paths(*relative_paths)
    return import_module(module_name)


def load_module(module_name: str, relative_path: str) -> ModuleType:
    install_dependency_stubs()
    module_path = ROOT / relative_path
    spec = spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {module_name} from {module_path}")
    module = module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module










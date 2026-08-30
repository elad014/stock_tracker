# Stock Tracker

A web app for following stocks, reading related news, uploading PDFs, and asking an AI assistant about your watchlist and documents.

The app is **not** an investment advisory tool. Market data, news summaries, and chat replies are for research only.

## What it does

- Create an account, sign in, reset a forgotten password, and update profile settings.
- Build a watchlist of Twelve Data tickers and view price, change, history charts, and market stats.
- Read Finnhub news per stock, with optional AI article summaries and a stock-level news rollup.
- Upload PDFs, organize them in folders, and ask questions over those files (RAG).
- Chat from the dashboard; the assistant can use stock quotes, news, and your documents.
- Admin users can manage accounts, locks, and watchlist assignments.

Home-page quotes are an illustrative snapshot, not live brokerage data. Signed-in quotes come from stock-manager.

## Architecture

Five Docker services share one Neon PostgreSQL database (plus pgvector for documents). The UI service is the only public API. Internal agents talk over HTTP with `X-Internal-Api-Key`.

```
Browser
  -> ui-service :8000   React SPA + FastAPI (JWT)
       -> stock-manager :8001   quotes, history, watchlist
       -> news-agent    :8003   Finnhub articles + LLM summaries
       -> doc-agent     :8004   PDF ingest, embeddings, RAG
       -> chat-agent    :8002   LiteLLM orchestrator (no database)
```

Chat-agent calls the other three internal services. News-agent writes stock rollup summaries through stock-manager. Doc-agent reads PDFs from the same object-storage bucket that ui-service writes to.

## Tech stack

| Layer | Technology |
| --- | --- |
| Frontend | React 18, TypeScript, Vite 5, React Router 6, Axios |
| Backend | Python 3.12, FastAPI, Uvicorn, Pydantic v2 |
| Database | PostgreSQL (Neon), pgvector |
| Auth | bcrypt, JWT (`python-jose`) |
| Email | Resend |
| Object storage | Supabase Storage over the S3 protocol (`boto3`) |
| Market data | Twelve Data |
| News | Finnhub, trafilatura for article text |
| LLM | LiteLLM (Gemini by default; OpenAI and Anthropic supported) |
| Scheduling | APScheduler in stock-manager and news-agent |
| Containers | Docker, Docker Compose |

## Project structure

```
stock_tracker/
├── docker-compose.yml
├── requirements.txt
├── ui_service/          # Public SPA + BFF (port 8000)
├── stock_manager/       # Quotes, history, watchlist (port 8001)
├── chat_agent/          # Chat orchestrator (port 8002)
├── news_agent/          # News fetch and summaries (port 8003)
├── doc_agent/           # PDF embeddings and RAG (port 8004)
└── common/              # Shared clients, constants, and guards
```

`common/` includes clients for the database, email, object storage, Twelve Data, Finnhub, LiteLLM, embeddings, article extraction, and HTTP clients for each internal service.

## Pages

| Path | Who | Purpose |
| --- | --- | --- |
| `/` | Public | Marketing home |
| `/help` | Public | Product help |
| `/login`, `/register`, `/forgot-password` | Public | Auth |
| `/dashboard` | Signed in | Watchlist, documents, news, chat |
| `/stock/:stockId` | Signed in | Charts, market data, articles |
| `/settings` | Signed in | Profile and password |
| `/admin` | Admin | Users and stocks |

## Public API (ui-service)

JWT is required except for register, login, and password reset.

| Method | Path | Description |
| --- | --- | --- |
| POST | `/auth/register` | Create an account |
| POST | `/auth/login` | Sign in and receive a JWT |
| GET | `/auth/me` | Current user |
| PUT | `/auth/me` | Update profile or password |
| POST | `/auth/password-reset-request` | Request a reset email |
| POST | `/auth/password-reset-confirm` | Set a new password with the token |
| GET/POST | `/watchlist` | List or add followed stocks |
| DELETE | `/watchlist/{stock_id}` | Remove a followed stock |
| GET | `/stocks/{stock_id}` | Quote and summary |
| GET | `/stocks/{stock_id}/history` | History (`range=1D` … `5Y`) |
| GET | `/stocks/{stock_id}/articles` | Stored news articles |
| POST | `/stocks/{stock_id}/articles/{article_id}/summarize` | Summarize one article |
| GET | `/documents/tree` | Folder and file tree |
| POST | `/documents/files` | Upload a PDF |
| POST | `/documents/files/move` | Move a file |
| GET | `/documents/files/download` | Presigned download URL |
| DELETE | `/documents/files` | Delete a file |
| POST/DELETE | `/documents/folders` | Create or delete a folder |
| POST | `/chat` | Ask the assistant |
| GET/POST/PUT/DELETE | `/admin/*` | Admin user and stock tools |

Internal services expose their own `/health` plus API-key-protected `/docs`.

## Limits

| Limit | Default |
| --- | --- |
| PDF files per user | 10 |
| Upload size | 20 MB |
| Document indexes per rolling 7 days | 20 |
| Chat session history | 20 messages |
| JWT lifetime | 30 minutes |
| Password-reset token | 15 minutes |

## Database tables

`user_auth_data`, `stock_quotes`, `stock_history`, `stock_history_archive`, `watchlist`, `news_articles`, `stock_articles`, `document_vectors`, `document_ingest_quota`.

## Getting started

### Prerequisites

- Docker and Docker Compose
- Node.js 20+ and Python 3.12+ for local development
- A Neon database, Resend account, Twelve Data key, Finnhub key, Gemini (or other LiteLLM) key, and Supabase Storage S3 credentials

### Environment files

Copy each example file to `.env` in the same folder and fill in real values:

- `ui_service/backend/.env.example`
- `stock_manager/backend/.env.example`
- `chat_agent/backend/.env.example`
- `news_agent/backend/.env.example`
- `doc_agent/backend/.env.example`

`INTERNAL_API_KEY` must match across services. `DATABASE_URL` is used by ui-service, stock-manager, news-agent, and doc-agent. Chat-agent has no database. Ui-service and doc-agent must use the same S3 bucket for user PDFs.

### Run with Docker

```bash
docker-compose up --build
```

The app is at `http://localhost:8000`.

| Service | Port |
| --- | --- |
| ui-service | 8000 |
| stock-manager | 8001 |
| chat-agent | 8002 |
| news-agent | 8003 |
| doc-agent | 8004 |

### Local development

Install Python dependencies once from the repo root:

```bash
pip install -r requirements.txt
```

Run each backend from its `backend` folder (`PYTHONPATH` must include `common` and that backend). Default ports match the table above.

```bash
uvicorn main:app --reload --port 8000
```

Frontend (proxies API routes to port 8000):

```bash
cd ui_service/frontend
npm install
npm run dev
```

Vite starts at `http://localhost:5173`.

## Automated tests

The repository keeps isolated unit tests and integration/service tests in separate folders:

- `tests/unit` covers backend business logic, validators, mapping/parsing helpers, cache/rate-limit guards, API-client response parsing, LLM/embedding wrappers, document chunking, and database logic with mocks/fakes.
- `tests/integration` covers main application flows through FastAPI route handlers and service layers, including auth/admin flows, watchlist flows, stock quote/history persistence, ui-service communication with stock-manager/news-agent/doc-agent/chat-agent, internal API-key auth, news/article processing, document upload/ingest/ask flows, and chat orchestration.

The tests are deterministic and do not use production data. They do not require Docker, Neon/PostgreSQL, S3/Supabase, Twelve Data, Finnhub, Gemini, or any other live external service. Paid and external integrations are mocked or faked.

Run commands from the repository root after installing the Python dependencies.

Run unit tests:

```bash
python -m unittest discover -s tests/unit -v
```

Run integration/service tests:

```bash
python -m unittest discover -s tests/integration -v
```

Run all tests with detailed per-test output and grouped summaries:

```bash
python run_tests.py
```

`run_tests.py` exits with a non-zero status code if any test fails or errors, so it can be used later in CI/GitHub Actions.
## User types

| Role | Capabilities |
| --- | --- |
| User | Account, watchlist, stock details, documents, news, chat, settings |
| Admin | Everything a user can do, plus manage users, locks, stocks, and watchlist assignments |

Deleting a user from admin removes that account’s S3 files, vectors, ingest quota, and watchlist rows.




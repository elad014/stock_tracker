# Stock Tracker

A web application for tracking investment portfolios, monitoring real-time stock data, and receiving AI-powered financial insights and notifications.

## Overview

Stock Tracker is designed to help users:

- Create a personal account and manage their profile.
- Build and manage a personalized investment portfolio of stocks, indices, and cryptocurrencies.
- Track real-time financial data including prices, daily changes, and historical charts.
- Stay updated with relevant financial news per asset.
- Receive AI-based analysis, summaries, and recommendations powered by artificial intelligence.
- Get alerts and notifications on significant events for tracked assets.

The system aggregates data from multiple sources (stocks, market indices like S&P 500, Nasdaq-100, TA-35, TA-125, and cryptocurrencies) into a single unified platform with a clean dashboard experience.

> **Note:** The application is **not** an investment advisory tool. It helps users better understand real-time data through automated notifications and AI-based analysis.

## Tech Stack

| Layer              | Technology                                    |
| ------------------ | --------------------------------------------- |
| **Frontend**       | React 18, TypeScript, Vite 5, React Router 6  |
| **Backend**        | Python 3.12, FastAPI, Uvicorn                 |
| **Database**       | PostgreSQL (Neon)                              |
| **Authentication** | bcrypt (password hashing), JWT (python-jose)   |
| **Email**          | Resend API via httpx                           |
| **Validation**     | Pydantic v2                                    |
| **Containerization** | Docker, Docker Compose                       |

## Project Structure

```
stock_tracker/
├── docker-compose.yml          # Service orchestration
├── requirements.txt            # Python dependencies
├── ui_service/
│   ├── Dockerfile              # Multi-stage build (frontend + backend)
│   ├── backend/
│   │   ├── main.py             # FastAPI app entry point
│   │   ├── auth.py             # Authentication endpoints
│   │   ├── models.py           # Pydantic request/response schemas
│   │   └── db_logics/
│   │       └── user_db_logic.py  # User data access layer
│   └── frontend/
│       ├── src/
│       │   ├── App.tsx
│       │   ├── api/auth.ts     # API client
│       │   └── pages/          # Login, Register, Recovery pages
│       ├── package.json
│       └── vite.config.ts
└── common/                     # Shared utility clients
    ├── database_client/        # Async PostgreSQL client (Neon)
    └── email_client/           # Resend email client
```

## User Types

| Role      | Capabilities                                                              |
| --------- | ------------------------------------------------------------------------- |
| **User**  | Register, login, manage portfolio, track stocks, view news, receive alerts and AI insights |
| **Admin** | Manage users, manage asset lists, configure AI service quality, view system dashboards, send notifications |

## Supported Financial Assets

- **Stocks** - Individual company shares
- **Market Indices** - S&P 500, Nasdaq-100, TA-35, TA-125
- **Cryptocurrencies** - Digital assets

## Workflow

1. User registers and creates a personal account.
2. User logs in and accesses their personal dashboard.
3. User builds a portfolio by adding stocks, indices, and cryptocurrencies.
4. The system provides real-time data updates for each asset in the portfolio.
5. In parallel, the system fetches financial news and alerts relevant to the user's assets.
6. The AI engine analyzes events and produces actionable insights.
7. User receives summaries, recommendations based on AI analysis, and notifications on asset developments.

## API Endpoints

| Method | Path                          | Description                    |
| ------ | ----------------------------- | ------------------------------ |
| POST   | `/auth/register`              | Create a new user account      |
| POST   | `/auth/login`                 | Login and receive a JWT token  |
| POST   | `/auth/password-reset-request`| Request a password reset email |
| POST   | `/auth/password-reset-confirm`| Reset password with token      |
| GET    | `/*`                          | Serve frontend SPA             |

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Node.js 20+ (for local frontend development)
- Python 3.12+ (for local backend development)

### Environment Variables

Create a `.env` file at `ui_service/backend/.env` with the following:

```
DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require
JWT_SECRET_KEY=your-secret-key
RESEND_API_KEY=your-resend-api-key
EMAIL_FROM=noreply@yourdomain.com
```

### Run with Docker

```bash
docker-compose up --build
```

The application will be available at `http://localhost:8000`.

### Local Development

**Backend:**

```bash
pip install -r requirements.txt
cd ui_service/backend
uvicorn main:app --reload --port 8000
```

**Frontend:**

```bash
cd ui_service/frontend
npm install
npm run dev
```

The Vite dev server starts at `http://localhost:5173` and proxies API requests to the backend.

## Database Schema

The application expects a PostgreSQL table:

```sql
CREATE TABLE user_auth_data (
    id            TEXT PRIMARY KEY,
    user_name     TEXT UNIQUE NOT NULL,
    password      TEXT NOT NULL,
    email         TEXT UNIQUE NOT NULL,
    phone_number  TEXT
);
```

## Planned Features

- Real-time stock data tracking and historical charts
- Personal portfolio management with P&L tracking
- Financial news feed per asset
- AI-powered analysis module (alerts, summaries, sentiment analysis, recommendations)
- Custom notification system (real-time and scheduled)
- Interactive dashboards with customizable panels
- Admin panel for user and system management
- Support for cryptocurrency exchanges (e.g., Binance)
- Advanced AI models for financial question answering

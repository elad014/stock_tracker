# --- Stage 1: Build frontend ---
FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend
COPY ui_service/frontend/package.json ui_service/frontend/package-lock.json* ./
RUN npm install
COPY ui_service/frontend/ ./
RUN npm run build

# --- Stage 2: Backend + serve frontend ---
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONPATH=/app/utils:/app/backend

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY ui_service/backend/ ./backend/
COPY utils/ ./utils/

COPY --from=frontend-build /app/frontend/dist ./frontend/dist

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

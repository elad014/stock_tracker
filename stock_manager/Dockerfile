# --- Stock Manager service ---
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONPATH=/app/common:/app/backend

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY stock_manager/backend/ ./backend/
COPY common/ ./common/

EXPOSE 8001

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8001"]

# --- LLM Service ---
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONPATH=/app/common:/app/backend

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --upgrade litellm

COPY llm_service/backend/ ./backend/
COPY common/ ./common/

EXPOSE 8002

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8002"]

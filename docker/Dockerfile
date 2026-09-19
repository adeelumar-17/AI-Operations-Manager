FROM python:3.12-slim

WORKDIR /app

# ── AWS Lambda Web Adapter ─────────────────────────────────────────────────────
# Lets Lambda invoke the container exactly as-is (uvicorn keeps listening on
# PORT 8000); no handler rewrite needed. The layer is a no-op outside Lambda.
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.8.4 /lambda-adapter /opt/extensions/lambda-adapter
ENV PORT=8000

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY agents ./agents
COPY rag ./rag
COPY integrations ./integrations

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
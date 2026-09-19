# Deployment Guide — AWS Lambda + ECR + Neon

This guide deploys the AI Operations Manager backend as a **container-based AWS Lambda function** exposed via a **Lambda Function URL** (no API Gateway needed). The database runs on **Neon** (serverless PostgreSQL). The APScheduler is replaced by an **EventBridge Scheduler** rule that calls the app's `/internal/run-followups` endpoint.

> **Prerequisites**
> - AWS CLI configured (`aws configure`)
> - Docker Desktop running
> - Your Neon project created at [neon.tech](https://neon.tech) (free tier)
> - Alembic migrations run locally against Neon (see Step 0)

---

## Step 0 — Run Alembic Migrations Against Neon

Ensure required extensions are enabled in your Neon database SQL editor:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

Configure both Neon connection strings in your local `.env`:

```ini
# Pooled connection string (used by app runtime / Lambda)
DATABASE_URL=postgresql+psycopg://user:pass@ep-xxx.pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require

# Direct unpooled connection string (used by Alembic migrations)
DATABASE_URL_DIRECT=postgresql+psycopg://user:pass@ep-xxx.eu-central-1.aws.neon.tech/neondb?sslmode=require
```

Then run Alembic migrations locally (Alembic will automatically use `DATABASE_URL_DIRECT`):

```bash
alembic upgrade head
```

---

## Step 1 — Create ECR Repository

```bash
aws ecr create-repository --repository-name ai-ops-manager --region <region>
```

> The free tier includes 500 MB private storage for 12 months.  
> After year one, storage costs a few cents/month (typically < $0.50/month).

---

## Step 2 — Build & Push Docker Image

```bash
# Authenticate Docker with ECR
aws ecr get-login-password --region <region> | \
  docker login --username AWS --password-stdin <account-id>.dkr.ecr.<region>.amazonaws.com

# Build the image (run from repo root)
docker build -f docker/Dockerfile -t ai-ops-manager .

# Tag and push
docker tag ai-ops-manager:latest <account-id>.dkr.ecr.<region>.amazonaws.com/ai-ops-manager:latest
docker push <account-id>.dkr.ecr.<region>.amazonaws.com/ai-ops-manager:latest
```

---

## Step 3 — Create the Lambda Function

```bash
aws lambda create-function \
  --function-name ai-ops-manager \
  --package-type Image \
  --code ImageUri=<account-id>.dkr.ecr.<region>.amazonaws.com/ai-ops-manager:latest \
  --role arn:aws:iam::<account-id>:role/lambda-basic-execution \
  --memory-size 1024 \
  --timeout 60 \
  --region <region>
```

> **Memory**: 1024 MB — LangChain/LangGraph load ~400 MB on cold start.  
> Lambda scales CPU proportionally with memory, so 1024 MB also speeds cold starts.  
> At this scale you'll use a tiny fraction of the 400,000 free GB-seconds/month.

---

## Step 4 — Set Environment Variables on Lambda

```bash
aws lambda update-function-configuration \
  --function-name ai-ops-manager \
  --region <region> \
  --environment "Variables={
    DATABASE_URL=postgresql+psycopg://user:pass@ep-xxx.pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require,
    GROQ_API_KEY=gsk_your-actual-key,
    GROQ_MODEL=openai/gpt-oss-120b,
    GROQ_TEMPERATURE=1.0,
    GROQ_MAX_TOKENS=2048,
    GROQ_REASONING_EFFORT=medium,
    EMBEDDING_BACKEND=sentence-transformers,
    SENTENCE_TRANSFORMERS_MODEL=all-MiniLM-L6-v2,
    SCHEDULER_ENABLED=false,
    SCHEDULER_SECRET=your-random-secret-here
  }"
```

> **DATABASE_URL**: Use the **pooled** Neon connection string here. Lambda can spawn many concurrent execution environments; the pooler absorbs connection spikes so you don't hit Postgres's connection limit.

> **SCHEDULER_ENABLED=false**: Tells the app to skip starting APScheduler in-process. EventBridge calls `/api/v1/internal/run-followups` instead.

---

## Step 5 — Create Lambda Function URL

```bash
aws lambda create-function-url-config \
  --function-name ai-ops-manager \
  --region <region> \
  --auth-type NONE \
  --cors '{
    "AllowOrigins": ["https://your-frontend.vercel.app"],
    "AllowMethods": ["*"],
    "AllowHeaders": ["*"],
    "AllowCredentials": false
  }'
```

You'll get back a URL like:

```
https://xxxx.lambda-url.<region>.on.aws/
```

That's your API base URL. Set it as `VITE_API_URL` (or equivalent) in your frontend deployment.

> **No API Gateway needed** — Function URLs are a built-in HTTPS endpoint with no extra charge beyond Lambda invocations themselves.

---

## Step 6 — Set Up EventBridge Scheduler (Replaces APScheduler)

### Create the IAM role for EventBridge → Lambda

```bash
# Create the role
aws iam create-role \
  --role-name eventbridge-lambda-invoker \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": { "Service": "scheduler.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }]
  }'

# Attach Lambda invoke permission
aws iam attach-role-policy \
  --role-name eventbridge-lambda-invoker \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaRole
```

### Create the schedule (fires every hour)

```bash
aws scheduler create-schedule \
  --name ai-ops-followup-sweep \
  --region <region> \
  --schedule-expression "rate(1 hour)" \
  --flexible-time-window '{"Mode": "OFF"}' \
  --target '{
    "Arn": "arn:aws:lambda:<region>:<account-id>:function:ai-ops-manager",
    "RoleArn": "arn:aws:iam::<account-id>:role/eventbridge-lambda-invoker",
    "Input": "{\"httpMethod\":\"POST\",\"path\":\"/api/v1/internal/run-followups\",\"headers\":{\"X-Scheduler-Secret\":\"your-random-secret-here\"},\"body\":\"\",\"isBase64Encoded\":false}"
  }'
```

See `eventbridge-payload.json` for the full sample payload.

> Cost at this scale: effectively free (well under the Always-Free limit of 14 million scheduler invocations/month).

---

## Step 7 — Update Lambda on New Deploys

```bash
# Rebuild and push the image (Steps 2), then:
aws lambda update-function-code \
  --function-name ai-ops-manager \
  --region <region> \
  --image-uri <account-id>.dkr.ecr.<region>.amazonaws.com/ai-ops-manager:latest
```

---

## Architecture After Deployment

```
Frontend (Vercel / S3+CloudFront)
        │  HTTPS
        ▼
Lambda Function URL  ──────────────────────────────────────────────┐
        │                                                          │
        ▼                                                          │
FastAPI (uvicorn on :8000)                              EventBridge Scheduler
  ├── /api/v1/chat          → LangGraph Agent                (rate 1 hour)
  ├── /api/v1/approvals     → HITL approval flow                  │
  ├── /api/v1/products      → Inventory                           │
  ├── /api/v1/quotes        → Quotations                          ▼
  ├── /api/v1/...           → Other domains       POST /api/v1/internal/run-followups
  └── /api/v1/internal      → EventBridge trigger       (X-Scheduler-Secret header)
        │
        ▼
Neon PostgreSQL (serverless, pooled connection)
  + pgvector for RAG embeddings
```

---

## Local Dev — Unchanged

Local development workflow is **identical** to before:

```bash
# Start DB
docker compose up db -d

# Run the API (APScheduler starts automatically)
uvicorn backend.app.main:app --reload
```

`SCHEDULER_ENABLED` defaults to `true`, so APScheduler polls normally. The Lambda adapter layer in the Dockerfile is a no-op when running outside Lambda.

# AI Operations Manager

> **Production-Grade Autonomous B2B Operations Engine**  
> *Built with FastAPI, LangGraph, SQLAlchemy 2.0, PostgreSQL (pgvector), and APScheduler.*  
> *Deployable as a containerized AWS Lambda function via Lambda Web Adapter + Neon + EventBridge.*

---

An autonomous, production-grade AI operations agent built with **LangGraph**, **Groq** (`openai/gpt-oss-120b`), **FastAPI**, and **PostgreSQL + pgvector**.

The system automates six core enterprise operational workflows while enforcing business policies through **local RAG embeddings** and **Human-in-the-Loop (HITL) checkpoints** for high-risk actions.

---

## Architecture Overview

```
                          ┌──────────────────────────┐
                          │   Client / Frontend / UI │
                          └─────────────┬────────────┘
                                        │ HTTP / JSON
                                        ▼
    ┌────────────────────────────────────────────────────────────────────────┐
    │                       FastAPI REST API Layer (M8)                      │
    │  /api/v1/chat  /api/v1/approvals  /api/v1/customers  /api/v1/quotes...   │
    └──────────────────┬─────────────────────────────────────┬───────────────┘
                       │                                     │
                       ▼                                     ▼
        ┌─────────────────────────────┐       ┌──────────────────────────────┐
        │  LangGraph Operations Agent │       │  APScheduler Background (M7) │
        │     (StateGraph Routing)    │◄──────┤   (Polls due followup tasks) │
        └──────────────┬──────────────┘       └──────────────────────────────┘
                       │
         ┌─────────────┴─────────────┐
         ▼                           ▼
┌──────────────────┐       ┌──────────────────┐
│   Tool Layer     │       │   Memory / HITL  │
│    (18 Tools)    │       │  (Checkpointer)  │
└────────┬─────────┘       └────────┬─────────┘
         │                          │
         ▼                          ▼
┌──────────────────┐       ┌──────────────────┐
│ Business Domain  │       │  PostgreSQL DB   │
│ Services (M2)    │◄─────►│   + pgvector     │
└──────────────────┘       └──────────────────┘
```

### Architectural Principles
1. **Clean Separation of Concerns**: `agents/` is a top-level package completely decoupled from `backend/` and `rag/`. It can be run as a standalone CLI script, a background scheduled task, or behind FastAPI.
2. **Tools Have Zero Business Logic**: Tools in `agents/tools/` are strict 1-to-2 line wrappers around M2 service methods. All authorization, mathematical calculations, and state invariants are enforced by service classes.
3. **Local RAG Embeddings**: Policy retrieval runs locally via `sentence-transformers` (`all-MiniLM-L6-v2`, 384 dimensions) using cosine distance in `pgvector`. No external embedding API key is required.
4. **Persistent Human-in-the-Loop**: High-risk actions (discounts > 10%, refunds > $500) trigger LangGraph `interrupt()`, persisting execution state to disk so approval can happen hours later or survive process restarts.

---

## The Six Operational Workflows

| # | Workflow | Key Operations | Approval Gating |
|---|---|---|---|
| **1** | **Inventory & Fulfillment** | Check SKU stock, verify multi-item fulfillment feasibility, query low-stock alerts. | None (Read-only / Safe) |
| **2** | **Quotation** | Create quotes, apply discounts, look up discount policy, convert quotes to orders. | **Required** if discount > 10% (regular) or > 15% (preferred) |
| **3** | **Invoice & Overdue** | Query invoice status, list accounts receivable, calculate days overdue. | None |
| **4** | **Customer Management** | Search accounts, inspect customer purchase history, fetch communication logs. | None |
| **5** | **Issue Resolution** | Policy-driven return/refund evaluation, dispute handling, order status review. | **Required** if refund amount > $500 |
| **6** | **Follow-up & Reminders** | Schedule future follow-up reminders, query stale quotes, automated email/note logging. | None |

---

## Directory Layout

```text
AI-Operations-Manager/
├── backend/
│   ├── app/
│   │   ├── api/routes/         # FastAPI REST endpoints (/chat, /approvals, /quotes...)
│   │   ├── core/               # Configuration (Pydantic BaseSettings), audit logging
│   │   ├── db/                 # SQLAlchemy models, repositories, and DB session
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   ├── services/           # Domain business logic (QuoteService, InventoryService...)
│   │   ├── scheduler/          # APScheduler configuration and periodic jobs
│   │   └── main.py             # FastAPI entrypoint with lifespan manager
│   └── tests/                  # Integration tests (API, scheduler)
│
├── agents/
│   ├── graph/nodes/            # Routing nodes (classify, entities) & 6 workflow nodes
│   ├── tools/                  # 18 domain tools bound to LangGraph
│   ├── prompts/                # System, routing, extraction, and response prompts
│   ├── memory/                 # Checkpointer (PostgresSaver / MemorySaver)
│   ├── llm.py                  # Groq client & ChatGroq factory (openai/gpt-oss-120b)
│   ├── agent_service.py        # Single callable run_agent() & resume_agent() interface
│   └── tests/                  # Agent smoke tests & HITL verification
│
├── rag/
│   ├── ingestion/              # Document parser, chunker, and pgvector ingester
│   ├── embeddings.py           # Sentence-transformers embedding backend (384-dim)
│   ├── retriever.py            # Cosine similarity vector search
│   └── vector_store.py         # VectorStore facade
│
├── scripts/
│   └── setup_checkpointer.py   # One-time setup script for LangGraph PostgresSaver tables
│
├── data/policies/              # Markdown policy documents (discounts, refunds, etc.)
├── tests/eval/                 # Evaluation dataset (eval_cases.json) and benchmark runner
├── docker-compose.yml          # Postgres + pgvector and API container definition
├── requirements.txt            # Python dependencies
└── .env.example                # Environment template
```

---

## Getting Started

### 1. Prerequisites
- Python 3.11+
- Docker & Docker Compose
- Groq API Key (free from [console.groq.com](https://console.groq.com))

### 2. Configure Environment
Copy `.env.example` to `.env` and set your Groq API key:
```ini
POSTGRES_DB=ai_operations_manager
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/ai_operations_manager

# Embedding backend (runs locally, free, no key needed)
EMBEDDING_BACKEND=sentence-transformers
SENTENCE_TRANSFORMERS_MODEL=all-MiniLM-L6-v2

# Groq LLM (free tier available at console.groq.com)
GROQ_API_KEY=gsk_your_actual_groq_api_key
GROQ_MODEL=openai/gpt-oss-120b
GROQ_TEMPERATURE=1.0
GROQ_MAX_TOKENS=2048
GROQ_REASONING_EFFORT=medium
```

### 3. Database Setup: Neon (Production) & Local Docker

This project uses **Neon (serverless PostgreSQL)** as its database in production (and AWS Lambda deployments). It also supports local PostgreSQL via Docker Compose for offline development.

#### Enabling Required Neon Extensions
Before running migrations against your Neon database, run the following SQL statements in the **Neon Console SQL Editor** (or via `psql`) to enable the required extensions:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

#### Connection Strings: Pooled vs. Direct
Neon provides two distinct connection endpoints:
- **`DATABASE_URL` (Pooled)**: Neon's PgBouncer pooled connection (`<ep-name>-pooler...`). The FastAPI application and AWS Lambda runtime use this URL to safely handle concurrent requests without exhausting database connection limits.
- **`DATABASE_URL_DIRECT` (Direct)**: Neon's direct unpooled compute connection (`<ep-name>...`). **Alembic migrations must be run with `DATABASE_URL_DIRECT` rather than the pooled URL**, as connection poolers in transaction mode do not support the session-level locking and transactional DDL statements required by schema migrations.

The Alembic runner (`alembic/env.py`) automatically sources `DATABASE_URL_DIRECT` for migrations.

#### Running Migrations
For local Docker Compose:
```bash
docker compose up db -d
alembic upgrade head
```

For Neon:
Set `DATABASE_URL` and `DATABASE_URL_DIRECT` in your `.env` (copied from `.env.example`), then run:
```bash
alembic upgrade head
```

#### Initializing LangGraph Checkpoint Tables
LangGraph uses **PostgresSaver** to persist agent graph states and manage human-in-the-loop (HITL) checkpoints across process restarts and Lambda invocations. Its checkpoint tables (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations`) are managed separately from Alembic business tables.

Run the one-time checkpointer setup script (which connects using `DATABASE_URL_DIRECT`):
```bash
python scripts/setup_checkpointer.py
```
> **Important**: This script must be run once against Neon before the human-in-the-loop / approval flow will work, in the same way `alembic upgrade head` must be run once for the business schema.


### 4. Ingest Policy Documents
```bash
python -m rag.ingestion postgresql://postgres:postgres@localhost:5432/ai_operations_manager --force
```

### 5. Launch the FastAPI API Server
```bash
uvicorn backend.app.main:app --reload
```
- Interactive Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health Check: [http://localhost:8000/health](http://localhost:8000/health)

---

## API Endpoints Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/chat` | Submit a request to the operations agent. |
| `GET` | `/api/v1/approvals` | List all pending high-risk approval requests. |
| `POST` | `/api/v1/approvals/{id}/approve` | Approve a pending action and resume execution. |
| `POST` | `/api/v1/approvals/{id}/reject` | Reject a pending action and cancel execution. |
| `GET` | `/api/v1/customers` | Search or list customer accounts. |
| `GET` | `/api/v1/customers/{id}` | Get customer profile details. |
| `GET` | `/api/v1/products` | List product catalog with stock levels. |
| `GET` | `/api/v1/products/low-stock` | List items below reorder point. |
| `GET` | `/api/v1/quotes/{id}` | Retrieve quote line items and status. |
| `GET` | `/api/v1/orders/{id}` | Retrieve order details and fulfillment status. |
| `GET` | `/api/v1/invoices/overdue` | Retrieve overdue invoices. |
| `GET` | `/api/v1/invoices/{id}` | Retrieve invoice status. |
| `GET` | `/api/v1/tasks` | List pending scheduled tasks. |
| `POST` | `/api/v1/tasks` | Schedule a future follow-up task. |
| `POST` | `/api/v1/tasks/trigger` | Trigger immediate execution of due tasks. |

---

## Running Test & Benchmark Suites

### M6 — Human-in-the-Loop & Checkpointing
Verifies graph interruption when a 15% discount is requested, checks checkpoint persistence, and tests resumption upon managerial approval and rejection:
```bash
python -m agents.tests.test_m6_hitl
```

### M7 — Automated Scheduler
Verifies APScheduler background lifecycle and automated follow-up job processing:
```bash
python -m backend.tests.test_scheduler
```

### M8 — API Integration Tests
Validates all mounted endpoints, OpenAPI specifications, and chat routing:
```bash
python -m backend.tests.test_api
```

### M10 — Evaluation Benchmark
Runs 12 structured end-to-end operational scenarios across all 6 workflows:
```bash
python -m tests.eval.run_eval
```

---

## Direct CLI Streaming

You can test native token-by-token streaming from the Groq client at any time without running the server:
```bash
python -m agents.llm "Summarize our return policy for damaged items in two sentences."
```

---

## Deployment (AWS Lambda + Neon)

The AI Operations Manager backend is designed for serverless, cost-effective deployment on AWS Lambda and Neon PostgreSQL, allowing the platform to run within the AWS Always-Free tier with zero idle cost.

👉 **For the complete copy-paste CLI walkthrough, see [`deploy/README.md`](deploy/README.md).**

---

### Architecture Overview

```
Frontend (React/Vite on Vercel)
       │ HTTPS requests
       ▼
AWS Lambda Function URL (Built-in HTTPS endpoint + Single-Layer CORS)
       │
       ▼
AWS Lambda Container (AWS Lambda Web Adapter)
       │ HTTP forward to localhost:8000
       ▼
FastAPI App (uvicorn on port 8000 — unmodified codebase)
       ├── /api/v1/chat              ──► LangGraph Operations Agent (Groq LLM)
       ├── /api/v1/approvals         ──► Human-in-the-Loop Approval Checkpoints
       ├── /api/v1/products, quotes  ──► Domain Operations Services
       └── /api/v1/internal          ──► POST /internal/run-followups
             ▲                                │
             │ HTTP POST (Hourly)             ▼
  AWS EventBridge Scheduler           Neon Serverless PostgreSQL (TLS)
  (Function URL v2.0 payload)          ├── Pooled URL: App queries & checkpointer
                                       ├── Direct URL: Alembic migrations & setup
                                       └── pgvector + pgcrypto extensions
```

#### 1. Backend Container Runtime & Web Adapter
- **Containerized FastAPI**: The application is packaged into a Docker container image based on `python:3.12-slim` and deployed to AWS Lambda as an Image package type.
- **AWS Lambda Web Adapter**: Included as an extension layer via Dockerfile (`COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.8.4 /lambda-adapter /opt/extensions/lambda-adapter`). It intercepts incoming Lambda invocations and converts them into standard HTTP requests sent to the local `uvicorn` process listening on `PORT 8000`.
- **Zero Code Rewrites**: No ASGI adaptation layers (such as Mangum) or custom Lambda handler functions are needed. The exact same container runs locally and in the cloud.

#### 2. Ingress via Lambda Function URL (No API Gateway)
- Exposed directly through a **Lambda Function URL** with `AuthType=NONE`.
- Provides a dedicated, low-latency HTTPS endpoint (`https://<id>.lambda-url.<region>.on.aws/`) with no extra API Gateway management overhead or per-request API Gateway charges.

#### 3. Database: Serverless Neon PostgreSQL (Pooled vs. Direct)
- **Engine**: Neon serverless PostgreSQL with `pgvector` and `pgcrypto` extensions enabled for vector similarity search and secure ID generation.
- **Dual Connection Strings**:
  - `DATABASE_URL` (Pooled): Points to Neon's PgBouncer connection pooler (`ep-...-pooler...neondb?sslmode=require`). Used by the running FastAPI application and Lambda runtime to absorb concurrency spikes and prevent exhausting database connection limits across concurrent Lambda environments.
  - `DATABASE_URL_DIRECT` (Direct / Unpooled): Points directly to the Neon compute instance (`ep-...neondb?sslmode=require`). **Used exclusively for Alembic schema migrations (`alembic upgrade head`) and the LangGraph checkpointer initialization script (`python scripts/setup_checkpointer.py`)**, as DDL statements and migration locking mechanisms are incompatible with connection poolers.

#### 4. Durable LangGraph Checkpointing (`langgraph-checkpoint-postgres`)
- Human-in-the-Loop (HITL) checkpoints and agent thread persistence are handled using `PostgresSaver` from `langgraph-checkpoint-postgres`, connected to Neon via `DATABASE_URL`.
- **Why Not SQLite?**: SQLite was deliberately rejected for this deployment because Lambda's `/tmp` filesystem is ephemeral, limited, and not shared between concurrent execution environments or cold-start container lifecycles. Storing checkpoints in Neon guarantees that when a workflow pauses for managerial approval (e.g., quotes with discounts > 10% or refunds > $500), execution state survives indefinitely until reviewed.

#### 5. Container Registry (Amazon ECR)
- Docker images are tagged and pushed to a private **Amazon Elastic Container Registry (ECR)** repository (`ai-ops-manager`) in your target AWS region.

#### 6. IAM Execution Role & Networking (No VPC)
- **IAM Role**: Uses a dedicated Lambda execution role scoped strictly to CloudWatch Logs writing via the managed `AWSLambdaBasicExecutionRole` policy. Root or overprivileged IAM roles are avoided.
- **No VPC Attached (Deliberate Cost Optimization)**: Placing a Lambda function inside a custom VPC would require an AWS NAT Gateway to reach external endpoints (Neon database, Groq API). A NAT Gateway incurs a fixed minimum cost of ~$32+/month and is not part of any AWS free tier. Because the function connects to Neon and Groq over HTTPS/TLS (`sslmode=require`), running outside a VPC is fully encrypted and eliminates unwanted AWS infrastructure costs.

#### 7. Scheduled Tasks (EventBridge Scheduler replaces APScheduler)
- In a traditional server environment, APScheduler runs as a continuous in-process background thread polling for due tasks. On AWS Lambda, background worker threads are frozen when an invocation finishes, making in-process scheduling non-viable.
- **Solution**:
  - Setting `SCHEDULER_ENABLED=false` on Lambda skips starting the in-process APScheduler.
  - An authenticated HTTP endpoint, `POST /api/v1/internal/run-followups`, executes the due-followup sweep.
  - The endpoint is protected by a shared secret header (`X-Scheduler-Secret`), which is compared against the `SCHEDULER_SECRET` environment variable declared in the application's `Settings` class.
  - An **AWS EventBridge Scheduler** rule triggers hourly, sending a Function URL v2.0 event payload with the `X-Scheduler-Secret` header to the Lambda function. The Lambda Web Adapter transparently translates this payload into an HTTP POST request to `/api/v1/internal/run-followups`.

#### 8. Frontend Deployment (Vercel)
- The frontend is a separate React/Vite repository deployed independently on **Vercel**.
- Connects to the backend using the Lambda Function URL, configured via the frontend's environment variable (`VITE_API_BASE_URL` or `VITE_API_URL`) in Vercel project settings.

#### 9. Single-Layer CORS Strategy
- CORS is configured **exclusively at the Lambda Function URL layer** (allowing the Vercel production domain, HTTP methods, and headers).
- FastAPI's internal `CORSMiddleware` was **deliberately removed** in `backend/app/main.py` because having both Lambda Function URL CORS and FastAPI `CORSMiddleware` produces duplicate `Access-Control-Allow-Origin` response headers, which browsers reject outright.
- *Note*: If the backend is ever deployed to a hosting platform that lacks a built-in CORS proxy layer (such as Render, Railway, or Hugging Face Spaces), `CORSMiddleware` must be re-enabled at the FastAPI application level.

---

### Required Environment Variables (Lambda)

Configure the following variables in the Lambda function configuration (AWS Console &rarr; Configuration &rarr; Environment variables, or via `aws lambda update-function-configuration`):

| Variable | Required | Source in Code | Description |
|---|---|---|---|
| `DATABASE_URL` | **Yes** | `backend.app.core.config.Settings` | Pooled Neon PostgreSQL connection string (`postgresql+psycopg://...-pooler...neondb?sslmode=require`). |
| `GROQ_API_KEY` | **Yes** | `backend.app.core.config.Settings` | API key from [console.groq.com](https://console.groq.com) for agent LLM inference. |
| `SCHEDULER_SECRET` | **Yes** | `backend.app.core.config.Settings` | Random secret token securing `POST /api/v1/internal/run-followups` against unauthorized calls. |
| `SCHEDULER_ENABLED` | **Yes** | `backend.app.main` | Must be set to `false` on Lambda to disable in-process APScheduler background polling. |
| `GROQ_MODEL` | No | `backend.app.core.config.Settings` | Model identifier (defaults to `openai/gpt-oss-120b`). |
| `GROQ_TEMPERATURE` | No | `backend.app.core.config.Settings` | Sampling temperature (defaults to `1.0`). |
| `GROQ_MAX_TOKENS` | No | `backend.app.core.config.Settings` | Max completion tokens (defaults to `2048`). |
| `GROQ_REASONING_EFFORT` | No | `backend.app.core.config.Settings` | Reasoning effort for reasoning models (defaults to `medium`). |
| `EMBEDDING_BACKEND` | No | `backend.app.core.config.Settings` | Embedding engine (defaults to `sentence-transformers`). |
| `SENTENCE_TRANSFORMERS_MODEL` | No | `backend.app.core.config.Settings` | Model name (defaults to `all-MiniLM-L6-v2`, 384 dimensions). |

*(Note: `DATABASE_URL_DIRECT` is only required when running migrations and checkpointer setup scripts from your local workstation, and is not needed in the Lambda runtime environment.)*

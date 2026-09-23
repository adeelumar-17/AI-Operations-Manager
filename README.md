# AI Operations Manager

> **Production-Grade Autonomous B2B Operations Engine**  
> *Built with FastAPI, LangGraph, SQLAlchemy 2.0, PostgreSQL (pgvector), and APScheduler.*  
> *Dockerless architecture designed for native Python deployments (Render, Railway, Linux/macOS/Windows) with Neon Serverless PostgreSQL.*

---

An autonomous, production-grade AI operations agent built with **LangGraph**, **Groq** (`openai/gpt-oss-120b`), **FastAPI**, and **PostgreSQL + pgvector** (hosted on [Neon](https://neon.tech)).

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
    │                       FastAPI REST API Layer                           │
    │  /api/v1/chat  /api/v1/approvals  /api/v1/customers  /api/v1/quotes...   │
    └──────────────────┬─────────────────────────────────────┬───────────────┘
                       │                                     │
                       ▼                                     ▼
        ┌─────────────────────────────┐       ┌──────────────────────────────┐
        │  LangGraph Operations Agent │       │     APScheduler Background   │
        │     (StateGraph Routing)    │◄──────┤   (Polls due followup tasks) │
        └──────────────┬──────────────┘       └──────────────────────────────┘
                       │
         ┌─────────────┴─────────────┐
         ▼                           ▼
┌──────────────────┐       ┌──────────────────┐
│   Tool Layer     │       │   Memory / HITL  │
│    (18 Tools)    │       │  (PostgresSaver) │
└────────┬─────────┘       └────────┬─────────┘
         │                          │
         ▼                          ▼
┌──────────────────┐       ┌──────────────────┐
│ Business Domain  │       │  Neon PostgreSQL │
│ Services         │◄─────►│   + pgvector     │
└──────────────────┘       └──────────────────┘
```

### Architectural Principles
1. **Clean Separation of Concerns**: `agents/` is a top-level package completely decoupled from `backend/` and `rag/`. It can be run as a standalone CLI script, a background scheduled task, or behind FastAPI.
2. **Tools Have Zero Business Logic**: Tools in `agents/tools/` are strict wrappers around backend domain services. All authorization, mathematical calculations, and state invariants are enforced by service classes.
3. **Local RAG Embeddings**: Policy retrieval runs locally via `sentence-transformers` (`all-MiniLM-L6-v2`, 384 dimensions) using cosine distance in `pgvector`.
4. **Persistent Human-in-the-Loop**: High-risk actions (discounts > 10%, refunds > $500) trigger LangGraph `interrupt()`, persisting execution state in Neon via `PostgresSaver` so approval can happen asynchronously or survive process restarts.
5. **Dockerless Deployment**: Runs as a standard ASGI Python process (`uvicorn backend.app.main:app`), compatible out of the box with Render, Railway, or any modern PaaS.

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
│   │   ├── api/                # FastAPI routers and route handlers (/chat, /approvals, /quotes...)
│   │   ├── core/               # Configuration (Pydantic BaseSettings), audit logging
│   │   ├── db/                 # SQLAlchemy models, repositories, and DB session
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   ├── services/           # Domain business logic (QuoteService, InventoryService...)
│   │   ├── scheduler/          # APScheduler configuration and periodic jobs
│   │   └── main.py             # FastAPI entrypoint with CORS & lifespan manager
│   └── tests/                  # Backend unit & integration tests (API, scheduler)
│
├── agents/
│   ├── graph/nodes/            # Routing nodes (classify, entities) & 6 workflow nodes
│   ├── tools/                  # 18 domain tools bound to LangGraph
│   ├── prompts/                # System, routing, extraction, and response prompts
│   ├── memory/                 # Checkpointer (PostgresSaver with MemorySaver fallback)
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
├── integrations/               # External integration stubs (email, shipping, notifications)
├── data/
│   ├── policies/               # Markdown policy documents (discounts, refunds, etc.)
│   └── seed/                   # Database seed scripts for realistic enterprise demo data
│
├── scripts/
│   └── setup_checkpointer.py   # One-time setup script for LangGraph PostgresSaver tables
│
├── alembic/                    # Database migrations configured for Neon (pooled + direct)
├── tests/eval/                 # Evaluation dataset (eval_cases.json) and benchmark runner
├── requirements.txt            # Python dependencies (CPU torch + psycopg 3)
├── Procfile                    # ASGI process specification for Render / Railway
├── .python-version             # Python runtime specification (3.11.9)
└── .env.example                # Environment variables template
```

---

## Getting Started

### 1. Prerequisites
- Python 3.11+
- A [Neon](https://neon.tech) PostgreSQL account (free tier)
- A Groq API Key (free from [console.groq.com](https://console.groq.com))
- *(Optional)* A Hugging Face token ([huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)) for higher rate limits when downloading embeddings.

### 2. Local Environment Setup

Clone the repository and set up a Python virtual environment:

```bash
python -m venv .venv

# Windows PowerShell:
.venv\Scripts\Activate.ps1

# macOS / Linux:
source .venv/bin/activate

# Install dependencies:
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Configure your credentials in `.env`:
```ini
# ── Database Connection Strings ───────────────────────────────────────────────
# Pooled connection string (used by the running app & connection pooler)
DATABASE_URL=postgresql+psycopg://<username>:<password>@<ep-name>-pooler.<region>.aws.neon.tech/<dbname>?sslmode=require

# Direct unpooled connection string (used by Alembic migrations & checkpointer setup)
DATABASE_URL_DIRECT=postgresql+psycopg://<username>:<password>@<ep-name>.<region>.aws.neon.tech/<dbname>?sslmode=require

# ── Embeddings ────────────────────────────────────────────────────────────────
EMBEDDING_BACKEND=sentence-transformers
SENTENCE_TRANSFORMERS_MODEL=all-MiniLM-L6-v2
# HF_TOKEN=hf_...               # Optional: Hugging Face read token for higher download rate limits

# ── Groq LLM ──────────────────────────────────────────────────────────────────
GROQ_API_KEY=gsk_your_actual_groq_api_key
GROQ_MODEL=openai/gpt-oss-120b
GROQ_TEMPERATURE=1.0
GROQ_MAX_TOKENS=2048
GROQ_REASONING_EFFORT=medium

# ── Scheduler ─────────────────────────────────────────────────────────────────
SCHEDULER_ENABLED=true
SCHEDULER_SECRET=your-random-secret-key
```

---

### 4. Database Setup: Neon (Serverless PostgreSQL)

#### Step 4.1: Enable Required Neon Extensions
Run the following SQL in the **Neon Console SQL Editor** (or via `psql`):
```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

#### Step 4.2: Run Database Migrations
Run schema migrations against Neon:
```bash
alembic upgrade head
```
*(Alembic automatically uses `DATABASE_URL_DIRECT` to safely execute DDL migrations outside PgBouncer).*

#### Step 4.3: Initialize LangGraph Checkpointer Tables
Create the LangGraph `PostgresSaver` state tables (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations`):
```bash
python scripts/setup_checkpointer.py
```

#### Step 4.4: Seed Initial Demo Data
Populate the database with demo users, customers, catalog items, and invoices:
```bash
python -m data.seed.seed
```

#### Step 4.5: Ingest Business Policies into pgvector
Chunk and index the markdown policies in `data/policies/`:
```bash
python -m rag.ingestion --force
```

---

### 5. Launch the FastAPI Application

Start the local development server:
```bash
uvicorn backend.app.main:app --reload
```
or run via the module entrypoint:
```bash
python -m backend.app.main
```

- **Interactive API Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

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

### Unit & Integration Tests (Pytest)
Run all 69 backend integration and unit tests:
```bash
pytest backend/tests -v
```

### Human-in-the-Loop (HITL) Verification
Test graph interruption, checkpoint persistence, and resumption upon approval/rejection:
```bash
python -m agents.tests.test_m6_hitl
```

### Automated Scheduler Test
Verify APScheduler background lifecycle and automated follow-up task processing:
```bash
python -m backend.tests.test_scheduler
```

### Operational Evaluation Benchmark
Run 12 structured end-to-end operational scenarios across all 6 workflows:
```bash
python -m tests.eval.run_eval
```

### Direct CLI Streaming
Test native token-by-token streaming from Groq without starting the API server:
```bash
python -m agents.llm "Summarize our return policy for damaged items in two sentences."
```

---

## Deployment Guide (Render, Railway, or PaaS)

The application runs natively as a Python ASGI service without any Docker requirement.

### 1. Render Deployment

1. **Connect Repository**: Link your GitHub repository in the [Render Dashboard](https://dashboard.render.com).
2. **Create a Web Service**:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python -m alembic upgrade head && uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
   - Update an existing service's configured Start Command too; changing the repository's `Procfile` does not replace a command already configured in the dashboard.
3. **Set Environment Variables**:

| Variable | Required | Default / Format | Description |
|---|---|---|---|
| `DATABASE_URL` | **Yes** | `postgresql+psycopg://...-pooler...` | Neon pooled PostgreSQL connection string. |
| `DATABASE_URL_DIRECT` | **Yes** | `postgresql+psycopg://...` | Neon direct unpooled connection string. |
| `GROQ_API_KEY` | **Yes** | `gsk_...` | Groq API key for agent LLM inference. |
| `SCHEDULER_SECRET` | **Yes** | `string` | Secret key securing the scheduler endpoint. |
| `SCHEDULER_ENABLED` | No | `true` | Runs APScheduler in-process every 60s. |
| `HF_TOKEN` | No | `hf_...` | Hugging Face token for higher rate limits. |
| `EMBEDDING_BACKEND` | No | `sentence-transformers` | `sentence-transformers` (local) or `openai`. |
| `GROQ_MODEL` | No | `openai/gpt-oss-120b` | Groq LLM model name. |

Migrations must finish before the scheduler starts. Both database URLs must target the same database and schema; Alembic prefers `DATABASE_URL_DIRECT`. Migration `004` adds `followup_tasks.started_at`. If logs report that column is missing, run `python -m alembic upgrade head` in the service shell, then `python -m alembic current` to verify the migration revision, and restart the service. Do not use `alembic stamp` to repair a missing column: stamping records a revision without applying its schema changes.

> [!TIP]
> **Free Tier Memory Advisory**:
> Local `sentence-transformers` uses ~380–450 MB RAM. If deploying on a 512 MB free tier and encountering Out-of-Memory restarts, set `EMBEDDING_BACKEND=openai` and provide `OPENAI_API_KEY` to reduce memory consumption to ~80 MB.

### 2. Connecting the Frontend (e.g. Vercel)

The backend includes `CORSMiddleware` configured to accept cross-origin requests from any client origin. Set your frontend's environment variable (e.g. in Vercel):

```env
VITE_API_BASE_URL=https://your-service-name.onrender.com
```

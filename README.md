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
│   ├── memory/                 # Checkpointer (SqliteSaver / MemorySaver)
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

### 3. Start Database & Run Migrations
```bash
docker compose up db -d
alembic upgrade head
```

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

The backend ships as a **container image** deployable to AWS Lambda with zero code changes, using the [AWS Lambda Web Adapter](https://github.com/awslabs/aws-lambda-web-adapter). The existing uvicorn process keeps listening on port 8000 — the adapter layer proxies Lambda invocations to it transparently.

| Component | Technology |
|---|---|
| Container runtime | AWS Lambda (1024 MB, container image) |
| Image registry | Amazon ECR |
| HTTPS endpoint | Lambda Function URL (no API Gateway) |
| Database | Neon serverless PostgreSQL (pooled) |
| Scheduled jobs | EventBridge Scheduler → `POST /api/v1/internal/run-followups` |

**APScheduler in local dev** runs normally. On Lambda, set `SCHEDULER_ENABLED=false` — the in-process scheduler is skipped and EventBridge triggers the followup sweep endpoint instead.

👉 **See [`deploy/README.md`](deploy/README.md) for the complete step-by-step deploy guide.**

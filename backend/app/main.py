'''
What the file does?
Primary entry point for the FastAPI backend. Configures CORS, mounts the versioned
API router, manages the application lifespan (including optional APScheduler startup),
and exposes /health and /internal routes.

Classes:
    None (FastAPI application factory module).

Methods:
    lifespan: Async context manager that conditionally starts/stops APScheduler.
        Controlled by the SCHEDULER_ENABLED env var (default: true).
        Set to "false" on Lambda — EventBridge triggers /internal/run-followups instead.
    health_check: GET /health endpoint returning service liveness status.
'''

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.router import api_router
from backend.app.scheduler.scheduler import start_scheduler, stop_scheduler

# When SCHEDULER_ENABLED=false the in-process APScheduler is skipped.
# Use this on Lambda where a persistent background thread cannot survive
# between invocations — EventBridge hits /internal/run-followups instead.
_SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager — conditionally starts APScheduler.

    Local dev (SCHEDULER_ENABLED=true, the default): APScheduler polls for due
    follow-up tasks every 60 seconds in a background thread.

    Lambda (SCHEDULER_ENABLED=false): scheduler block is skipped entirely;
    EventBridge Scheduler calls POST /internal/run-followups on its own cadence.
    """
    if _SCHEDULER_ENABLED:
        try:
            start_scheduler(interval_seconds=60)
        except Exception as exc:
            print(f"[Warning] Could not start scheduler: {exc}")
    else:
        print("[Info] APScheduler disabled (SCHEDULER_ENABLED=false). Using EventBridge trigger.")
    yield
    if _SCHEDULER_ENABLED:
        try:
            stop_scheduler()
        except Exception:
            pass


app = FastAPI(
    title="AI Operations Manager",
    description="Agentic operations management platform powered by Groq and LangGraph.",
    version="0.1.0",
    lifespan=lifespan,
)



app.include_router(api_router)


@app.get("/health", tags=["Health"])
def health_check():
    """Service health check endpoint."""
    return {"status": "ok", "service": "AI Operations Manager"}
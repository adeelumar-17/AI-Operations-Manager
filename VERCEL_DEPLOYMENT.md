# Deploy the OfficeHub backend to Vercel

Use a separate Vercel project for this backend repository. The frontend remains its own project. The API paths, request/response contracts, demo database roles, graph routing and checkpoint schema are unchanged.

## Deployment settings

1. Import this repository from GitHub, with the repository root as Root Directory.
2. Select the **FastAPI** framework preset. Python **3.12** is specified in `pyproject.toml`.
3. Leave Install Command and Build Command at their detected defaults. The configured build is `python -m scripts.prepare_vercel_model`; if the dashboard overrides it, set that exact Build Command.
4. `vercel.json` explicitly enables **Fluid Compute** and sets the Hobby 300-second function duration; no dashboard toggle is needed. Do not copy Render's Uvicorn Start Command into Vercel.
5. Vercel resolves the lightweight `pyproject.toml`/`uv.lock` dependencies. Do not override installation with `pip install -r requirements.txt`: that older profile includes PyTorch for local/Render compatibility.

The build downloads a pinned, unquantized ONNX export of **the same all-MiniLM-L6-v2 model** and its tokenizer. It smoke-tests 384-dimensional vectors and bundles only inference assets, so chat does not download models during a cold start. Pooling, truncation and normalization match the original model. No database migrations or policy re-ingestion are performed in deployment builds, including previews.

## Environment variables

Configure these on the **backend** Vercel project:

| Variable | Value |
|---|---|
| `DATABASE_URL` | Your existing PostgreSQL connection string, with TLS |
| `DATABASE_URL_DIRECT` | Direct connection to the same database, for manual migrations/checkpointer setup |
| `GROQ_API_KEY` | Your existing Groq secret |
| `GROQ_MODEL` | Your existing model, e.g. `openai/gpt-oss-120b` |
| `EMBEDDING_BACKEND` | **`onnx`** |
| `SENTENCE_TRANSFORMERS_MODEL` | `all-MiniLM-L6-v2` |
| `SCHEDULER_ENABLED` | `false` (Vercel also disables the process scheduler automatically) |
| `SCHEDULER_SECRET` | A long random secret, used by the protected scheduler trigger |
| `HF_TOKEN` | Optional read token for build downloads |

`VERCEL=1` is supplied by Vercel. Do not set `ONNX_MODEL_DIR` unless you intentionally change the bundled location. No paid embedding API is required. Existing policy vectors are reused; the deployment does not change the model or vector dimension.

Keep production and preview database configuration explicit. To avoid previews changing production business records, either do not configure previews with production credentials, or use a separate preview database.

## Database preparation

Keep the existing PostgreSQL database. Before directing users to the new backend, verify it is at migration **004** and the LangGraph checkpoint tables exist. Run these from a trusted local environment with the intended deployed database URLs configured:

```powershell
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.setup_checkpointer
```

These commands target the configured database; they are not required on every request. Vercel uses PostgreSQL for durable interrupted approvals and fails rather than silently switching to process-local checkpoints if persistence cannot initialize. Smaller per-instance pools reduce idle connections as Vercel scales.

## Scheduled follow-ups

APScheduler cannot provide a persistent timer inside Vercel Functions. Configure an external HTTP scheduler (for example cron-job.org) to send:

```text
Method: POST
URL: https://YOUR-BACKEND.vercel.app/api/v1/internal/run-followups
Header: X-Scheduler-Secret: YOUR_SCHEDULER_SECRET
```

Use a cadence appropriate to your task volume, e.g. every minute. Each Vercel sweep handles at most **one** due task and leaves the rest pending, to reduce the risk of exceeding the request duration. The external service's HTTP timeout must accommodate the agent workflow. Overlapping calls retain the existing conditional database claim, so the same task is not executed by two workers. The frontend's existing manual task trigger is still available.

**No automatic schedule is configured by this repository.** Vercel Hobby's native cron is limited to daily runs, which does not preserve the old minute-by-minute timer. A terminated workflow may leave an in-progress task; existing stale-claim handling marks it failed for human review instead of replaying possible side effects.

## Frontend cutover and checks

1. Open `https://YOUR-BACKEND.vercel.app/health` and confirm `status: ok`.
2. Update the **frontend** project's `VITE_API_BASE_URL` to the backend's new HTTPS origin, without `/api/v1` or a trailing slash, and redeploy it. Keep its three demo user UUID variables pointing to active database users.
3. Check customer/product lists, policy retrieval in chat, approval pause/resume and rejection, and task creation/triggering. Test an approval across two separate requests so durable checkpoints are exercised.
4. Inspect Vercel's function logs and memory/duration metrics. Cold model loading and a real multi-step chat must fit comfortably under 2 GB and 300 seconds; local checks do not establish deployed peak memory or provider latency.
5. Keep the old Render deployment available until the checks pass. Avoid running both automatic schedulers during cutover.

## Local verification

```powershell
$env:UV_PROJECT_ENVIRONMENT = '.venv-vercel'
uv sync --python 3.12 --no-dev
uv pip install --python .venv-vercel/Scripts/python.exe pytest
.\.venv-vercel\Scripts\python.exe -m scripts.prepare_vercel_model
.\.venv-vercel\Scripts\python.exe -m scripts.verify_onnx_parity export
.\.venv\Scripts\python.exe -m scripts.verify_onnx_parity compare
.\.venv-vercel\Scripts\python.exe -m pytest backend/tests/unit backend/tests/audit agents/tests/test_inventory_tools.py -q -p no:cacheprovider
```

The comparison uses the original environment's SentenceTransformer and the slim environment's ONNX outputs. It verifies numerical agreement, long-text truncation, empty/Unicode text and policy ranking without contacting PostgreSQL or Groq.

## Verification performed in this workspace

- **95 offline tests passed** in the clean Python 3.12 Vercel dependency environment.
- The same **95 tests passed** in the existing local/Render environment.
- Ten reference texts matched the original SentenceTransformer numerically; minimum cosine agreement rounded to **1.00000000**, and policy ranking was unchanged.
- Bundled inference assets measured **86.7 MiB**.
- The clean Windows runtime dependencies, including test-only tools, occupied **189.8 MiB**. Deployment bundle size must still be checked in Vercel's Linux build.
- A Windows process loading the FastAPI application and embedding repeated maximum-length texts peaked at **277.5 MiB working set**. It used an explicit in-memory test checkpointer and made no real PostgreSQL or Groq requests. This is a smoke measurement, not a guarantee of deployed full-chat memory.
- PyTorch was neither installed nor imported in that environment.

The production deployment, real PostgreSQL pause/resume across instances, real Groq latency and the external schedule still need the cutover checks above. No remote database or deployment was changed during this work.

Official references: [FastAPI deployment](https://vercel.com/docs/frameworks/backend/fastapi), [Python dependencies and bundling](https://vercel.com/docs/functions/runtimes/python), [function limits](https://vercel.com/docs/functions/limitations), [Hobby cron limits](https://vercel.com/docs/cron-jobs/usage-and-pricing). Hobby is for personal, non-commercial use within its usage quotas.

# Local verification — PowerShell and curl.exe

Use a disposable **local PostgreSQL database with pgvector installed**, and the existing Python environment. These instructions are for local verification, not your deployed database. The fixture script refuses non-loopback database hosts and creates new records without deleting/updating existing data. Live chat checks require your existing Groq/embedding configuration; the offline tests do not.

## 1. Offline regression suite

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/unit backend/tests/audit agents/tests/test_inventory_tools.py -q -p no:cacheprovider
```

The `backend/tests/audit` configuration forces an in-memory database and MemorySaver. Do not run the old live scheduler/HITL scripts against your deployment as part of this check.

## 2. Local database, migration, fixtures, and server

Create a local database named `officehub_audit` first (for example with your PostgreSQL `createdb` utility). Substitute your local database password below if different. The environment override prevents `.env` from selecting your deployment database.

```powershell
$env:DATABASE_URL = 'postgresql+psycopg://postgres:postgres@127.0.0.1:5432/officehub_audit'
$env:DATABASE_URL_DIRECT = $env:DATABASE_URL
$env:SCHEDULER_ENABLED = 'false'
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.setup_checkpointer
.\.venv\Scripts\python.exe -m scripts.seed_audit_verification > audit-fixtures.json
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Keep that terminal running. In a second PowerShell terminal at the repository root:

```powershell
$base = 'http://127.0.0.1:8000/api/v1'
$f = Get-Content ./audit-fixtures.json -Raw | ConvertFrom-Json
$manager = "X-User-Id: $($f.manager_id)"
$staff = "X-User-Id: $($f.staff_id)"
curl.exe -sS http://127.0.0.1:8000/health
```

Use JSON request files to avoid Windows command-line quoting differences:

```powershell
function Write-AuditBody($value) {
    [IO.File]::WriteAllText((Join-Path (Get-Location) 'audit-request.json'), ($value | ConvertTo-Json -Depth 10), [Text.UTF8Encoding]::new($false))
}
function Invoke-AuditChat([string]$message, [string]$thread = '') {
    $body = @{ message = $message }
    if ($thread) { $body.thread_id = $thread }
    Write-AuditBody $body
    curl.exe -sS -X POST "$base/chat" -H $manager -H 'Content-Type: application/json' --data-binary '@audit-request.json' | ConvertFrom-Json
}
```

## 3. Identity, list endpoints, filters, and response compatibility

```powershell
curl.exe -i "$base/customers"
curl.exe -sS "$base/customers?query=Audit&limit=1" -H $manager
curl.exe -i "$base/customers?limit=-1" -H $manager
curl.exe -sS "$base/customers/$($f.preferred_id)" -H $manager
curl.exe -sS "$base/products" -H $manager
curl.exe -sS "$base/products/low-stock" -H $manager
curl.exe -sS "$base/orders?status=pending" -H $manager
curl.exe -sS "$base/quotes?status=approved" -H $manager
curl.exe -sS "$base/quotes/$($f.quote_id)" -H $manager
curl.exe -i "$base/invoices?status=not-a-status" -H $manager
```

Expected: missing identity 401; one search row; negative limit 422; preferred customer reports `tier=preferred`; existing resource lists work; quote detail includes customer_name/approval_id/created_at; invalid status 422. Existing response fields remain present.

## 4. Invoice balance, overdue status, and reminder truthfulness

```powershell
curl.exe -sS "$base/invoices/$($f.invoice_number)" -H $manager
curl.exe -sS "$base/invoices/overdue?customer_id=$($f.customer_id)" -H $manager
curl.exe -i -X POST "$base/invoices/$($f.paid_invoice_id)/remind" -H $manager
curl.exe -sS -X POST "$base/invoices/$($f.invoice_id)/remind" -H $manager
curl.exe -sS "$base/tasks" -H $manager
```

Expected: the $100 invoice with $40 paid reports `amount_due=60`, and appears overdue although its stored status is partially_paid. The paid invoice reminder returns 409. A successful unpaid-invoice reminder says a **draft was recorded**, and its task is completed only when that matching communication exists. If the agent/LLM fails, success is false and the task is failed; no response claims a sent email or a queued retry.

## 5. Discount persistence, limits, and genuine approval

```powershell
Invoke-AuditChat "Apply a 5 percent discount to quote $($f.quote_id). Do not convert it to an order."
curl.exe -sS "$base/quotes/$($f.quote_id)" -H $manager
Invoke-AuditChat "Apply a 15 percent discount to quote $($f.preferred_quote_id). Do not convert it."
curl.exe -sS "$base/quotes/$($f.preferred_quote_id)" -H $manager
Invoke-AuditChat "Apply a 26 percent discount to quote $($f.quote_id)."

$thread = 'audit-approval-' + [guid]::NewGuid().ToString()
$pending = Invoke-AuditChat "Apply a 20 percent discount to quote $($f.quote_id). Do not convert it to an order." $thread
$pending | ConvertTo-Json -Depth 10
$approval = $pending.approval_id
curl.exe -sS "$base/approvals/$approval" -H $manager
curl.exe -sS "$base/quotes/$($f.quote_id)" -H $manager
```

Expected: regular quote total persists as 95 after 5%; preferred quote persists as 85 with no approval at 15%; 26% is refused. The 20% request yields a real saved approval ID and pauses; the quote remains at its prior 95 total with pending_approval status.

```powershell
Write-AuditBody @{ approved_by = $f.manager_id; comment = 'Staff must not approve' }
curl.exe -i -X POST "$base/approvals/$approval/approve" -H $staff -H 'X-User-Role: admin' -H 'Content-Type: application/json' --data-binary '@audit-request.json'

Write-AuditBody @{ approved_by = $f.staff_id; comment = 'Manager approves the saved proposal' }
curl.exe -sS -X POST "$base/approvals/$approval/approve" -H $manager -H 'X-User-Role: staff' -H 'Content-Type: application/json' --data-binary '@audit-request.json'
curl.exe -sS "$base/quotes/$($f.quote_id)" -H $manager
curl.exe -sS "$base/approvals/$approval" -H $manager
curl.exe -sS -X POST "$base/approvals/$approval/approve" -H $manager -H 'Content-Type: application/json' --data-binary '@audit-request.json'
curl.exe -i -X POST "$base/approvals/$approval/reject" -H $manager
```

Expected: staff is denied with 403 even with an admin role header/body override; the database manager can approve despite a staff role header; recorded reviewer is manager, total becomes 80, and repeated approval does not repeat the mutation. Opposite decision is rejected. No order is automatically created during resume.

For durable-checkpoint verification, stop/restart the local server **after the pending response and before approval**, keeping the same local database and checkpoint setup; the same approval request must resume successfully.

```powershell
$rejected = Invoke-AuditChat "Apply a 20 percent discount to quote $($f.reject_quote_id)."
curl.exe -sS -X POST "$base/approvals/$($rejected.approval_id)/reject" -H $manager
curl.exe -sS "$base/quotes/$($f.reject_quote_id)" -H $manager
Invoke-AuditChat 'Review a refund of $600 for this customer. Do not issue a payment.'
```

Expected: rejected quote stays at 100 with its prior approved status; a $600 refund review requires approval independently of policy-search wording. Refund review never claims money was issued.

## 6. Product ambiguity, combined demand, and order fulfillment

```powershell
Invoke-AuditChat "Check fulfillment of two separate lines for SKU $($f.sku): 60 units on each line. Use the multi-item feasibility tool."
Invoke-AuditChat "Fulfill order $($f.order_number)."
curl.exe -sS "$base/orders/$($f.order_id)" -H $manager
curl.exe -sS "$base/products" -H $manager
Invoke-AuditChat "Fulfill order $($f.order_number) again."
Invoke-AuditChat "Move order $($f.order_number) to shipped."
curl.exe -sS "$base/orders/$($f.order_id)" -H $manager
```

Expected: combined demand of 120 exceeds initial stock of 100; fulfillment deducts exactly 2 and moves to processing; repeated fulfillment fails without another deduction; shipping changes status without deducting again. Ambiguous product writes and fractional quantities have deterministic offline regressions, independent of whether the live LLM chooses those invalid calls.

## 7. API scheduling validation and the new conversational tool

```powershell
$future = (Get-Date).AddDays(2).ToString('yyyy-MM-ddTHH:mm:sszzz')
Write-AuditBody @{ task_type = 'manual_reminder'; scheduled_at = $future; customer_id = 'not-a-uuid' }
curl.exe -i -X POST "$base/tasks" -H $manager -H 'Content-Type: application/json' --data-binary '@audit-request.json'
Write-AuditBody @{ task_type = 'quote_followup'; scheduled_at = $future; customer_id = $f.preferred_id; quote_id = $f.quote_id }
curl.exe -i -X POST "$base/tasks" -H $manager -H 'Content-Type: application/json' --data-binary '@audit-request.json'
Write-AuditBody @{ task_type = 'manual_reminder'; scheduled_at = $future; customer_id = $f.customer_id }
curl.exe -sS -X POST "$base/tasks" -H $manager -H 'Content-Type: application/json' --data-binary '@audit-request.json'
Invoke-AuditChat "Schedule one follow-up for customer $($f.customer_id) at $future. Do not contact them now."
curl.exe -sS "$base/tasks" -H $manager
```

Expected: malformed ID and wrong-customer quote return 422; valid API and conversational requests each create a task for the requested customer/time. A name-only request should use search_customer before the creation tool; missing time/timezone should prompt clarification, never immediate scheduling.

To exercise competing manual sweeps on a due task:

```powershell
$soon = (Get-Date).AddSeconds(10).ToString('yyyy-MM-ddTHH:mm:sszzz')
Write-AuditBody @{ task_type = 'manual_reminder'; scheduled_at = $soon; customer_id = $f.customer_id }
curl.exe -sS -X POST "$base/tasks" -H $manager -H 'Content-Type: application/json' --data-binary '@audit-request.json'
Start-Sleep -Seconds 11
$jobs = 1..2 | ForEach-Object {
    Start-Job -ArgumentList $base,$f.manager_id -ScriptBlock {
        param($url,$userId)
        curl.exe -sS -X POST "$url/tasks/trigger" -H "X-User-Id: $userId"
    }
}
$jobs | Wait-Job | Receive-Job
$jobs | Remove-Job
curl.exe -sS "$base/tasks" -H $manager
```

Expected: a due task has attempt_count 1; the loser does not execute it again. Completed means matching communication evidence exists; failed means it needs review. This local check complements the conditional-claim regression and is not a substitute for a PostgreSQL load test.

## 8. Conversation history and run/audit telemetry

```powershell
$conversation = 'audit-history-' + [guid]::NewGuid().ToString()
Invoke-AuditChat "Show customer $($f.customer_id)." $conversation
Invoke-AuditChat 'Show the same customer account history.' $conversation
$runs = curl.exe -sS "$base/runs" -H $manager | ConvertFrom-Json
$runs | Select-Object -First 5
curl.exe -sS "$base/runs/$($runs[0].id)/logs" -H $manager
```

Expected: later turns receive prior context; new executions appear in runs; logs contain node/tool results tied to the same run ID. Exact prose is model-dependent. Use the offline suite for deterministic verification of dispatch, tool registration, retries, validation, and accounting calculations.

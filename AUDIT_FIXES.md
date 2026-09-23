# Audit implementation and review guide

The audit fixes and the explicitly approved individual follow-up tool are implemented. API paths, HTTP methods, existing response field names, configuration variable names, the AgentState schema, routing topology, and checkpointer setup are preserved. No dependencies, Docker changes, or AWS/Lambda changes were introduced. The graph now invokes the existing audit wrapper; its edges are unchanged.

The original audit is a historical snapshot. Review the exact before/after changes in [AUDIT_CHANGES.diff](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/AUDIT_CHANGES.diff>). It includes every modified source/test file and every new Python file. The table below gives the one-sentence explanation for each finding; the patch contains its actual before/after diff.

| Finding | Before → after, and why the fix is correct |
|---|---|
| B01 | Approval interrupts were caught as ordinary exceptions → they propagate to LangGraph, producing a genuinely paused checkpoint. |
| B02 | Generated approval IDs and request/thread IDs diverged → a stable request/action approval ID identifies the saved record, and the actual RunnableConfig thread ID is saved with it. |
| B03 | Approval changed labels and claimed completion → the exact proposed discount is saved, linked to its quote, and applied once only after a persisted manager decision; rejection preserves the old price/status. |
| B04 | Headers/body could supply a privileged role or reviewer → X-User-Id must identify an active database user, database role controls approval, and approved_by in the body cannot override the acting user. |
| B05 | Routes resolved approvals twice and blocked safe retries → one serialized resume path resolves the decision, rejects contradictory decisions, resumes failed executions, and returns a saved result on repeated successful requests. |
| B06 | Discounts flushed then rolled back on close → permitted discounts commit before success is reported; above-threshold discounts remain unapplied proposals. |
| B07 | The model selected the threshold and could request up to 100% → Python derives 10%/15% from the stored legacy customer tier marker and enforces the 25% absolute cap. |
| B08 | Refund review relied on policy-result wording → Python checks the amount against $500 before issue tools run, and missing amounts require clarification; no refund execution or automatic return authorization is claimed. |
| B09 | Invoice amount_due/reminders used the gross invoice amount → both use Decimal payment aggregation and the same outstanding-balance helper, with zero due for paid/cancelled invoices. |
| B10 | Overdue lists depended on stale status → date/status/balance facts govern the overdue API, and paid/cancelled/draft invoices are not described as overdue by the days tool. |
| B11 | Successful prose marked reminders complete and claimed delivery → completion requires a matching persisted outbound communication; failures remain failures and logged email is explicitly a draft. |
| B12 | Invalid customer IDs selected the first customer and invalid quote IDs vanished → shared validation rejects malformed/missing IDs, customer/quote mismatches, missing targets, past times, and timestamps without offsets. |
| B13 | A private helper missed tool-resolved customers and converted invalid dates to now → a registered, bound create_followup_task tool uses verified UUIDs and explicit ISO time/offset validation. |
| B14 | Overlapping sweeps could claim the same task → a conditional UPDATE claims a pending task once, and stale/legacy in-progress tasks fail for human review instead of being automatically replayed. |
| B15 | Concurrent stock changes used unlocked stale reads → stock mutations acquire a row lock and refresh the product before changing its balance, while order/invoice mutation reads also lock their parent row. |
| B16 | Duplicate product lines independently passed stock checks → demand is aggregated by resolved product UUID and fractional/invalid quantities are rejected. |
| B17 | A fuzzy product match could silently choose the first row → ambiguous matches return SKU choices, exact SKU lookup uses equality, and case-colliding SKU records cannot silently pick one. |
| B18 | Pending→processing skipped stock deduction → this transition delegates to fulfillment, which checks stock and records deductions in the same transaction. |
| B19 | Order mutation tools were registered but unreachable → existing order status/fulfillment tools are now bound to the inventory and quote/order workflows. |
| B20 | Tools emitted business numbers that downstream UUID-only tools rejected → quote/order/invoice repositories resolve either form, and invoice/customer-history results also expose UUIDs. |
| B21 | Every customer appeared regular → the API and discount rules share a deterministic interpretation of the explicit existing preferred-tier notes marker. |
| B22 | Prior conversation messages were ignored → classification, entity extraction, and workflow calls receive bounded prior messages, and completed user/assistant turns are retained in the existing messages field. |
| B23 | Clarifications disappeared and inventory allowed only one tool round → direct responses are retained, inventory supports dependent rounds, and iteration exhaustion returns an explicit incomplete-operation error. |
| B24 | Dispatch looked up any global tool and continued after approval → each node dispatches only its bound tools, unavailable calls receive a tool result, and approval immediately exits the tool batch. |
| B25 | Run/audit utilities were disconnected → requests create/update AgentRun rows, node wrappers record execution, and tool results reference the actual deterministic AgentRun ID. |
| B26 | Errors became silent strings/pass → affected tools/nodes log tracebacks, scheduler failures are recorded, and response generation preserves failed/incomplete states. |
| B27 | LLM construction bypassed fallback and reminder keywords lost to invoice keywords → initialization is inside the fallback boundary and the confirmed refund/reminder/order fallback cases route correctly. |
| B28 | Customer search ignored limit → the limit is validated and applied to the search query as well as the normal listing. |
| B29 | Quote edits could change finalized/pending records without invalidating approval → immutable/expired states are rejected, item edits invalidate prior approval, permitted discounts receive a usable approved state, and empty/expired conversion is rejected. |
| B30 | Rounding, cancelled payments, and concurrent overpayment checks were incomplete → money uses an explicit cents rule, fractional-cent inputs are rejected, cancelled invoices reject payments, and payment validation runs under the invoice lock. |

Additional checks reject invalid order/quote/invoice status filters with 422 rather than allowing a database enum error. Quote detail adds the already-existing list metadata (`customer_name`, `approval_id`, `created_at`) without removing or renaming fields.

## Optimizations included

- Quote/task lists eagerly load customers; existing invoice/order eager loading stays intact.
- Invoice lists eagerly load payments needed for correct balances; days-overdue lookup no longer loads the same invoice twice.
- Policy tools use the shared database engine through the existing session-based retriever, instead of creating a new connection pool per query.
- Bounded communication history applies its limit in SQL.
- Scheduler transactions are short; identity/approval lookups release their read connections before LLM work.
- Per-thread PostgreSQL advisory locking uses a dedicated, immediately closed connection, so concurrent LLM requests cannot exhaust the normal tool-session pool by holding its connections.
- Migration 004 adds claim timestamps and seven indexes for due tasks, pending approvals, quote approval links, run logs, quote/order items, and invoice payments.
- Removed verified unused imports and silent catalog hasattr fallbacks. Optional pagination and wider speculative indexes were not added. Existing product response variants retain their field sets.

## Deliberate limits and operational details

- As requested, this remains a **demo identity system**: X-User-Id is not proof of identity. X-User-Role is ignored for authorization. Valid database IDs are required, including for read APIs; `/health` remains available without this header. No login/JWT implementation was added.
- Preferred tier currently comes from the anchored `Preferred customer tier` marker in existing notes. It is a compatibility rule for the existing data model, not LLM inference. A dedicated tier field would be separate schema/product work.
- Refund review records approval/rejection but does not move money. Return eligibility needs human review; refund/return execution, customer editing, quote creation, payment-recording tools, outbound delivery, and stale-quote discovery remain the separately scoped coverage gaps from the audit.
- Approval resumes execute the saved proposal and stop. They do not reinterpret the original request or silently perform an additional order conversion. A subsequent explicit conversion request uses the approved quote.
- Failed approvals may retry the same decision. A contradictory decision is rejected. Legacy approvals without the corrected saved proposal/thread information are not guessed or silently resumed; use a new request after reviewing the old record.
- Tasks held in progress for over 30 minutes (or legacy claims with no timestamp) become failed for review. They are never automatically retried because a communication may already have been recorded.
- A relative-date request with no time/timezone should produce a clarification. The creation tool requires a future timestamp with an offset and never substitutes the current time.
- Migration 004 must run before starting this version. Existing migrations and checkpointer setup were not rewritten. No migration was applied to your configured database during this task.

## Validation

Final offline result: **90 tests passed**. Git whitespace validation also passed.

The offline suite covers existing service behavior, real LangGraph pause/resume, correct approval IDs, no price mutation before approval, rejection, retry after execution failure, idempotent successful resume, customer/quote validation, task claiming/recovery, duplicate inventory demand, ambiguous writes, balances, tool bindings, demo role enforcement, response consistency, constructor fallback, complete-graph telemetry/history, and migration upgrade/downgrade.

See [AUDIT_VERIFICATION.md](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/AUDIT_VERIFICATION.md>) for the exact test command, local fixture setup, and curl.exe checks. Offline tests use SQLite/fake LLMs/MemorySaver; they do not establish live PostgreSQL concurrency behavior, Groq output quality, or durable PostgresSaver behavior across process restarts. Those require the local PostgreSQL/live-agent checks in that guide.

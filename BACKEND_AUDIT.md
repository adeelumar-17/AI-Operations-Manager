# OfficeHub backend audit — 23 September 2026

Audit only. No application code, routes, configuration, migrations, or deployment files were changed. This report is the review checkpoint requested in the pasted instructions.

## Scope and evidence

Reviewed all 51 Python files in the requested directories: 10 route modules, 11 repository files, 10 service files, 12 graph-node files, and 8 tool files (counts include package initializers). Traced their dependencies into ORM models, schemas, the agent facade, graph/state, prompts, scheduler, authentication dependencies, audit utilities, policy retrieval, policy documents, and all three Alembic revisions. Deployment changes are excluded.

Checks performed:

- Read source and cross-checked repository/service method calls against their actual definitions, including repositories injected into services. No remaining nonexistent repository/service method call was found in these paths. The previously corrected customer search and order-list problems are not reported as new bugs.
- Syntax-tree inspection found **20 defined tools, all 20 registered, and 2 registered tools bound to no workflow**: `update_order_status` and `fulfill_order`. Every tool name in the current workflow binding lists exists.
- Existing offline service tests: **67 passed** using `.venv\Scripts\python.exe -m pytest backend/tests/unit -q -p no:cacheprovider`.
- Isolated reproductions used the actual source function bodies with fake database/LLM objects. The interrupt reproduction used the installed LangGraph graph and MemorySaver. Results: approval flagged but no interrupt/checkpoint continuation; returned approval ID differed from saved ID; discount tool made zero commits; duplicate product demand of 12 against stock of 10 returned FEASIBLE; a $100 invoice with $40 paid returned `amount_due=100`.
- No production database queries, external messages, real agent actions, live LLM requests, or migrations were executed. Concurrency findings below follow from transaction code inspection, not a production load test. Index observations describe the checked-in schema/migrations; live database indexes were not inspected.

Severity: **P1** = approval, financial, data-integrity, or central workflow failure; **P2** = other correctness/coverage failure; **P3** = cleanup or optimization. Related symptoms are grouped to avoid counting one defect repeatedly.

## Confirmed bugs and correctness findings

### B01 — P1: Approval interrupts are swallowed

Evidence: [create_quote_node.py:138](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/graph/nodes/create_quote_node.py:138>) and [resolve_issue_node.py:119](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/graph/nodes/resolve_issue_node.py:119>).

Both nodes wrap `interrupt(...)` in `except Exception: pass`; their outer catch also catches ordinary exceptions. In the installed LangGraph, `GraphInterrupt` inherits from `Exception`. The control-flow exception never reaches the graph. The workflow can report that it awaits approval while actually reaching END.

**Reproduced:** `approval_required=True`, no `__interrupt__`, and checkpoint `next=()`. Merely removing the inner catch is insufficient because the outer catch must also let the interrupt propagate.

### B02 — P1: Approval records and checkpoint identities do not match

Evidence: [create_quote_node.py:118](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/graph/nodes/create_quote_node.py:118>), [resolve_issue_node.py:99](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/graph/nodes/resolve_issue_node.py:99>), [approval_repository.py:28](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/db/repositories/approval_repository.py:28>), [agent_service.py:47](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/agent_service.py:47>).

The nodes generate one random approval ID, while `request_approval()` creates another and its returned record is ignored. A client using the returned ID cannot retrieve/approve the saved record. The saved payload additionally calls `request_id` the `thread_id`, although the actual checkpoint key may be a caller-supplied thread/conversation ID. Even selecting the saved approval from the list can therefore resume the wrong checkpoint. Both are concrete identity mismatches, independent of B01.

### B03 — P1: Approval does not finalize the requested action

Evidence: [create_quote_node.py:125](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/graph/nodes/create_quote_node.py:125>), [approval_repository.py:110](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/db/repositories/approval_repository.py:110>), [formulate_response.py:60](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/graph/nodes/formulate_response.py:60>).

The quote is never linked to the new approval through `Quote.approval_id`, so repository resolution cannot synchronize that quote. After a decision, the node appends a “manager decision” string; it does not execute a validated pending action. The response nevertheless says the operation was “approved and completed.” There is no refund execution operation either.

Once B01 is corrected, replay must also be handled: work and approval creation occur before `interrupt`, so resuming the node can repeat tool side effects and create another approval. Fixing only the exception catch would expose this existing non-idempotent structure.

### B04 — P1: Manager approval endpoints do not enforce manager authorization

Evidence: [approvals.py:50](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/api/routes/approvals.py:50>), [dependencies.py:30](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/api/dependencies.py:30>), [approval_repository.py:90](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/db/repositories/approval_repository.py:90>).

Approve/reject depend only on `get_current_user`, which accepts caller-provided identity/role headers and defaults to an anonymous operator. Neither endpoint checks the role. The body can override the reviewer identity; invalid/nonexistent reviewers become NULL while the action is still approved. `require_role` is unused and itself declares `Header(None)` instead of `Depends(get_current_user)`.

Thus the backend has no effective manager-only gate. Whether a trusted upstream authenticates requests is not established by this repository; simply trusting an arbitrary `X-User-Role` header would not establish authentication either.

### B05 — P1: Approval resolution is duplicated, non-atomic, and cannot safely recover from resume failure

Evidence: [approvals.py:68](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/api/routes/approvals.py:68>), [agent_service.py:128](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/agent_service.py:128>), [approval_repository.py:79](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/db/repositories/approval_repository.py:79>).

The route commits a decision, then `resume_agent` opens another session and resolves it again. If resume fails, the approval remains resolved and the route rejects a retry as already resolved. The repository has no conditional pending-status update or lock, so concurrent approve/reject requests can both pass the route check and overwrite one another. Resume suppresses database-resolution failures and falls back to using the approval ID as a checkpoint key. These paths can separate the recorded decision from actual execution.

### B06 — P1: Applying a discount does not persist it

Evidence: [quote_tools.py:91](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/tools/quote_tools.py:91>) and [quote_repository.py:57](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/db/repositories/quote_repository.py:57>).

`apply_discount_to_quote` calls services/repositories that flush but never commit, then closes its own session. It returns changed totals and status even though the transaction is rolled back on close. A following conversion opens a new session and can see the old price/status. **Reproduced:** zero commit calls and one close call on the tool's success path.

### B07 — P1: Discount authorization is partly controlled by the LLM and disagrees with policy

Evidence: [quote_tools.py:73](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/tools/quote_tools.py:73>), [quote_service.py:198](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/services/quote_service.py:198>), [create_quote_node.py:103](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/graph/nodes/create_quote_node.py:103>), [discount_policy.md](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/data/policies/discount_policy.md>).

The tool exposes `approval_threshold` as an LLM-supplied argument rather than deriving it from trusted customer policy. The service only bounds the discount at 100%, while the checked-in business policy prohibits discounts above 25%. The node separately uses a hard-coded 10% check, incorrectly requiring approval for a preferred customer's 11–15% discount and potentially flagging hypothetical/failed requests. Approval detection also depends on a phrase in a tool's display string.

The Python comparison exists, but its policy input and the end-to-end decision are not reliably server-controlled. This fails the determinism requirement.

### B08 — P1: Refund approval depends on LLM behavior and wording

Evidence: [resolve_issue_node.py:57](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/graph/nodes/resolve_issue_node.py:57>) and [authorization_service.py:45](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/services/authorization_service.py:45>).

The prompt asks the LLM to decide whether a refund exceeds $500. The Python fallback only runs after a tool output contains both “approval” and “require,” and only if entity extraction supplied `amount`. A $600 refund need not be flagged if no qualifying tool text is returned. The existing deterministic `check_refund_authorization` helper is never called by production workflows. Amount strings containing commas can also fail the ad hoc float conversion. Return eligibility is likewise left to policy prose rather than a deterministic check of delivery/date/condition facts.

### B09 — P1: Invoice balances and reminder amounts ignore payments

Evidence: [invoices.py:28](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/api/routes/invoices.py:28>), [invoices.py:124](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/api/routes/invoices.py:124>), [invoice_tools.py:40](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/tools/invoice_tools.py:40>).

`amount_due` is the entire invoice amount unless status is exactly `paid`. A $100 invoice with $40 paid reports $100 due; reminders describe the same full amount as the outstanding balance. Cancelled invoices also receive a nonzero amount_due. Invoice tools expose gross amounts/payments but no computed outstanding balance, leaving an agent to calculate the remaining debt itself. **The partial-payment API defect was reproduced.**

### B10 — P2: Overdue results disagree between API and tools

Evidence: [invoices.py:60](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/api/routes/invoices.py:60>), [invoice_tools.py:74](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/tools/invoice_tools.py:74>), [invoice_tools.py:118](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/tools/invoice_tools.py:118>).

`GET /invoices/overdue` only checks the persisted `overdue` status. The tool correctly also checks due dates for `sent` and `partially_paid` invoices. No periodic status-refresh operation was found, so invoices that age overnight can be absent from the API result. Conversely, stale overdue status can include a future-due invoice. `get_days_overdue` reports a paid/cancelled invoice as overdue based solely on its due date, unlike the detailed invoice tool's status-aware wording.

### B11 — P1: Reminder and scheduler success can be reported without successful execution

Evidence: [invoices.py:100](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/api/routes/invoices.py:100>), [jobs.py:49](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/scheduler/jobs.py:49>), [communication_tools.py:35](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/tools/communication_tools.py:35>).

Both callers mark a task completed whenever `run_agent` returns, without checking returned errors, pending approval, failed tool results, or evidence of the requested action. Workflow failures normally return dictionaries rather than raising. The reminder route also always returns `success=True`; on an exception it marks the task `failed` but says it is queued. Failed tasks are excluded from the pending-only sweep, so that statement is false.

There is no email/SMS delivery tool: `log_communication` creates a pending database record, and the integration packages contain no delivery implementation. “Reminder sent” cannot be established from this path. The route also accepts paid, cancelled, draft, or not-yet-due invoices for an explicitly overdue reminder and does not preserve an invoice identifier on the queued task for later execution.

### B12 — P1: Task creation silently selects the wrong customer or drops the quote

Evidence: [tasks.py:59](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/api/routes/tasks.py:59>) and [task.py:9](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/schemas/task.py:9>).

The request schema accepts string IDs. An invalid customer UUID triggers `db.query(Customer).first()` and schedules against that unrelated customer; an invalid quote UUID is silently discarded. Valid-shaped but nonexistent IDs are not checked before the foreign-key insert and can surface as a server error. There is no check that a supplied quote belongs to the supplied customer. Scheduling against the wrong account is a data-integrity failure, not a helpful fallback.

### B13 — P1: Conversational follow-up creation is incomplete and can run at the wrong time

Evidence: [followup_node.py:93](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/graph/nodes/followup_node.py:93>) and [followup_node.py:120](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/graph/nodes/followup_node.py:120>).

There is **no registered individual-task creation tool**. A private helper runs only if the original extracted entities already contain both a customer UUID and a date. The UUID found later by `search_customer` stays in a string tool result and never updates those entities. “Remind me to follow up with Ahmed next Tuesday” therefore normally never reaches insertion.

If the helper is reached, non-ISO dates such as “next Tuesday” fall back to **now**, silently turning a future reminder into an immediate one. Naive timestamps have no explicit business timezone handling. The node does not pass an extracted quote ID into the helper. Database errors are swallowed as `None`, with no failure result explaining that scheduling failed. The loop can log a communication immediately even when the request was to schedule one for later.

The API/repository can create tasks, so the feature is not wholly absent from the backend; it is absent as a usable agent tool and unreliable conversationally. Adding that tool remains subject to the user's explicit confirmation.

### B14 — P1: Concurrent task sweeps can execute the same task twice

Evidence: [followup_repository.py:62](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/db/repositories/followup_repository.py:62>), [followup_repository.py:84](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/db/repositories/followup_repository.py:84>), [jobs.py:29](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/scheduler/jobs.py:29>).

Fetching pending tasks and marking them in progress are separate operations. Two overlapping invocations can both fetch the same task, then both mark and execute it because `mark_in_progress` does not conditionally claim a pending row. The manual trigger and periodic scheduler provide a concrete overlap path. A process failure after committing `in_progress` strands the task because only pending tasks are selected. Recovery and claiming need an explicit, bounded policy; this is not solved by adding another scheduler.

### B15 — P1: Inventory updates can lose concurrent changes

Evidence: [inventory_service.py:94](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/services/inventory_service.py:94>), [product_repository.py:25](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/db/repositories/product_repository.py:25>), [order_service.py:84](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/services/order_service.py:84>).

Stock updates use an unlocked read-modify-write. Two sessions can read 10, each deduct 6, and both save 4, even though the ledger records 12 units deducted. The nonnegative constraint cannot detect that lost update. Fulfillment also reads order state without locking, so concurrent attempts are not protected against duplicate processing. This is a code-confirmed race; it was not load-tested against the deployed database.

### B16 — P2: Fulfillment feasibility does not combine duplicate products

Evidence: [inventory_tools.py:155](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/tools/inventory_tools.py:155>).

Each input line is checked independently against the entire product stock. Two lines requesting 6 of the same product pass against stock 10. Aliases/SKUs resolving to the same product have the same problem. **Reproduced.** The tool also coerces JSON quantities with `int`, so a fractional quantity such as 1.9 becomes 1 rather than being rejected as invalid whole-unit demand.

### B17 — P1: Ambiguous product names can mutate an arbitrary product

Evidence: [inventory_tools.py:38](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/tools/inventory_tools.py:38>) and [product_repository.py:28](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/db/repositories/product_repository.py:28>).

`_find_product` returns the first fuzzy match and is used by the stock mutation tool. An ambiguous “chair” restock can affect whichever matching row is returned first, without disambiguation. Even the “exact SKU” query uses unescaped `ILIKE`, so `%` and `_` act as wildcard patterns. Name search is useful; using an ambiguous result for a write is the bug.

### B18 — P2: Order status transitions can bypass inventory deduction

Evidence: [order_service.py:56](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/services/order_service.py:56>) and [order_tools.py:76](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/tools/order_tools.py:76>).

`transition_status(pending, processing)` changes only the status. The order can then proceed through shipped/delivered without stock deduction. Calling `fulfill_order` afterward fails because it only accepts pending orders. This is a service/tool correctness hole currently made less reachable by B19; binding the existing tool without addressing it would expose the hole to normal conversations.

### B19 — P2: Existing order mutation tools are unreachable through normal workflow bindings

Evidence: [tools/__init__.py:44](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/tools/__init__.py:44>) and the workflow binding inventory below.

`update_order_status` and `fulfill_order` exist and are in `ALL_TOOLS`, but neither is bound anywhere. A normal request to fulfill or advance an existing order cannot be completed using the tools advertised to any workflow. No nonexistent names or other unregistered tools were found.

### B20 — P2: Business numbers are emitted where downstream tools require UUIDs

Evidence: [customer_tools.py:108](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/tools/customer_tools.py:108>), [invoice_tools.py:104](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/tools/invoice_tools.py:104>), [order_tools.py:53](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/tools/order_tools.py:53>), [quote_tools.py:49](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/tools/quote_tools.py:49>).

Order/quote/invoice tools parse identifiers with `UUID(...)`, although entity extraction explicitly accepts business numbers. History returns order/invoice numbers but omits their database UUIDs; the overdue tool says it returns invoice IDs but emits only invoice numbers. An agent finding `INV-1001` cannot then call `get_invoice` or `get_days_overdue` with that value. The reminder route itself supplies the number in its prompt. The HTTP invoice detail route supports numbers, but the agent tool does not.

### B21 — P2: The customer API reports every customer as regular

Evidence: [customers.py:37](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/api/routes/customers.py:37>), [customer.py:27](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/db/models/customer.py:27>), and [seed.py:68](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/data/seed/seed.py:68>).

The ORM has no `tier` attribute, so `getattr(..., "tier", "regular")` always returns regular for loaded customers. Seed data stores preferred status in notes. The API field consequently misrepresents preferred customers, and no trusted structured tier is available to the discount authorization path. A correction must retain the API field and settle a deterministic source for its value.

### B22 — P2: Conversation history is accepted and stored in state but never used

Evidence: [chat.py:23](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/api/routes/chat.py:23>), [agent_service.py:64](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/agent_service.py:64>), and every classification/entity/workflow prompt.

All LLM invocations build fresh messages from the current request. None consume `state['messages']`, and the final assistant response is not appended there. Requests such as “apply that discount to the same quote” cannot use supplied history even though the chat API accepts it. This can be corrected without changing the state schema.

### B23 — P2: Workflow loops discard clarification responses; inventory stops after one tool round

Evidence: [customer_mgmt_node.py:60](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/graph/nodes/customer_mgmt_node.py:60>), [create_quote_node.py:75](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/graph/nodes/create_quote_node.py:75>), [check_inventory_node.py:73](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/graph/nodes/check_inventory_node.py:73>), [formulate_response.py:80](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/graph/nodes/formulate_response.py:80>).

The customer, quote, invoice, issue, and follow-up loops break when the model answers without tools but discard that answer. A necessary clarification or explanation of missing capability is lost; the final response generator sees only tool results or “No actions were taken,” without the original request. Hitting an iteration limit also has no explicit incomplete-action result.

Inventory does preserve a direct answer, but executes only the first round of tool calls and never feeds their results back to its LLM. “Find low-stock products and add 10 to each” needs a result-dependent second round that this node cannot perform.

### B24 — P2: Tool execution does not enforce the node's advertised tool list

Evidence: [create_quote_node.py:84](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/graph/nodes/create_quote_node.py:84>) and the corresponding tool dispatch in all six workflow nodes.

Binding filters tools for the model, but dispatch searches global `ALL_TOOLS`. A returned call to a registered but unbound tool will execute anyway. Unknown names are silently skipped without a matching tool result. In the quote loop, detecting approval does not stop the remaining calls in the same batch; the break occurs afterward. Advertised tool coverage therefore is not an execution boundary, and an approval signal does not immediately gate subsequent actions.

### B25 — P2: Agent runs and operational audit logging are not connected

Evidence: [agent_service.py:19](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/agent_service.py:19>), [graph.py:43](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/graph/graph.py:43>), [audit.py:76](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/core/audit.py:76>), [runs.py:23](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/api/routes/runs.py:23>).

No production code creates `AgentRun` rows. The `audit_node` decorator is defined but never applied; `record_audit_log` has no active graph/tool caller. Thus the runs/logs endpoints cannot reflect new executions through this agent facade. If the decorator were simply switched on, it also uses `request_id` as the `run_id` foreign key, which references `AgentRun.id`, not its request_id string. This is an existing observability gap, not a proposal for new telemetry infrastructure.

### B26 — P2: Exceptions are routinely returned or suppressed without logging

Evidence: exception handlers in all seven [tool modules](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/tools>), all workflow nodes, [followup_node.py:160](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/graph/nodes/followup_node.py:160>), [agent_service.py:141](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/agent_service.py:141>), and [invoices.py:133](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/api/routes/invoices.py:133>).

Failures become strings, state errors, `None`, or bare `pass` without a server log/traceback. This includes failed approval persistence and scheduling. The scheduler does log error strings, but not exception tracebacks. Response formulation suppresses its own error and falls back to “Request completed.” Log exceptions at the boundary and preserve failure state; do not turn LangGraph control-flow interrupts into logged application failures.

### B27 — P2: LLM initialization failures bypass the advertised fallback

Evidence: [classify_intent.py:39](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/graph/nodes/classify_intent.py:39>) and [identify_entities.py:39](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/graph/nodes/identify_entities.py:39>).

Both initialize the LLM outside their `try` block. A constructor/configuration error bypasses keyword fallback or empty-entity recovery and can escape to the HTTP caller. The keyword fallback also tests invoice keywords before reminder keywords, so on a model failure “remind Ahmed about his overdue invoice” routes to the invoice-only workflow. That specific fallback cannot perform its requested communication action.

### B28 — P2: Customer search ignores its accepted limit

Evidence: [customers.py:21](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/api/routes/customers.py:21>) and [customer_repository.py:26](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/db/repositories/customer_repository.py:26>).

`limit` applies only to `list_all`; adding `query` switches to unbounded `search(query)`. Thus `?query=Ahmed&limit=1` can return many rows. The limit also has no nonnegative/upper-bound validation. Other declared route filters were traced: order/quote/invoice status and overdue customer_id are consumed. No other accepted-and-ignored route query parameter was found.

### B29 — P2: Quote lifecycle mutations do not preserve approval invariants

Evidence: [quote_service.py:93](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/services/quote_service.py:93>), [quote_service.py:198](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/services/quote_service.py:198>), [quote_service.py:228](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/services/quote_service.py:228>).

Line-item edits and discounts accept rejected, expired, converted, or already approved quotes without lifecycle validation or approval invalidation. A converted quote can be changed independently of its existing order. Applying a lower permitted discount to `pending_approval` leaves it pending; applying an ordinary discount to a draft leaves it draft, and there is no exposed standard quote-approval operation to make it convertible. Conversion checks only status, not `expires_at` or nonempty items. These are service-level invariant gaps; line-item edit methods currently have no agent tools, while discount and conversion do.

### B30 — P2: Financial precision and payment validation are incomplete

Evidence: [quote_service.py:57](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/services/quote_service.py:57>), [invoice_service.py:69](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/services/invoice_service.py:69>), [quote.py:87](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/db/models/quote.py:87>).

Quote arithmetic uses Decimal, but does not quantize monetary results or discount inputs to the persisted two-decimal precision. For example, 10% of $0.05 is computed as $0.005 and a total of $0.045, then both are independently stored in two-decimal columns. Application results and stored financial facts do not have a defined shared rounding rule. Fractional-cent payments are likewise validated before database rounding.

`record_payment` also allows a positive payment on a cancelled invoice and leaves its status cancelled. Its read/check/insert sequence is unlocked, allowing concurrent payments each to pass an outstanding-balance check and collectively overpay. These payment-service findings are latent in agent use because no payment tool currently exposes the service.

## Six-workflow coverage

These distinguish existing broken behavior from missing capabilities. Only the explicitly flagged follow-up creation tool is proposed for implementation after separate confirmation; other absent operations are suggestions, not authorized additions.

| Workflow | Tools bound today | Coverage and realistic gaps |
|---|---|---|
| Customer management | search_customer, get_customer_details, get_customer_history, get_communication_history, log_communication | Covers the README's read/history use cases. Cannot create/update a customer or update contact details, although the classification prompt advertises updates. Full communication bodies and record IDs are absent from history output, limiting detailed complaint context. |
| Inventory | check_stock, update_inventory, check_fulfillment_feasibility, get_low_stock_products, get_all_products, search_customer | Core catalog/stock capabilities exist. Duplicate demand, ambiguous writes, concurrency, and single-round execution are broken. Existing fulfill_order is unbound; this is a registration-to-workflow gap, not a missing implementation. |
| Quotations/orders | search_customer, get_customer_details, get_quote, apply_discount_to_quote, convert_quote_to_order, check_stock, check_fulfillment_feasibility, search_business_policy | Cannot create a new quote despite the workflow name, README, and classifier. Cannot add/edit/remove quote items through a tool despite service support. No quote search/list tool resolves a customer's quote without a UUID. Standard draft approval is absent. Existing order fulfillment/status mutations are unbound. Discount/HITL defects prevent reliable existing operations. |
| Invoice/payment follow-up | search_customer, get_invoice, find_overdue_invoices, get_days_overdue, get_customer_history | Can inspect a UUID-addressed invoice or list overdue entries. Cannot record a payment despite an existing service and the classifier's claim. No all-customer receivables/list-invoices tool for current non-overdue balances, no deterministic outstanding-total output, and no communication tool bound in this workflow. “Remind this overdue customer” can be classified here with no way to log the reminder. |
| Customer issue resolution | search_customer, get_customer_details, get_customer_history, get_order_status, get_invoice, log_communication, search_business_policy | Supports lookup, policy retrieval, and logging a proposed resolution. Refund/return eligibility and approval are not deterministic end to end. Cannot actually issue a refund, create a return, or ship a replacement. These execution additions are beyond the current refinement authorization; do not claim completion for them. |
| Scheduled follow-ups | search_customer, get_customer_details, get_customer_history, log_communication, get_communication_history, find_overdue_invoices | Can find overdue accounts and record communication drafts/notes. No individual create-task tool; private helper is unreliable. No stale-quote search/list or even get_quote bound, despite stale-quote follow-ups in the README. Cannot reschedule/cancel/list tasks conversationally. Actual email delivery is absent; the documented logging capability should be described accurately. |

All **20 tools** are accounted for by this table plus the two unbound order tools. `get_order_status` is bound only to issue resolution. No imported tool was found omitted from `ALL_TOOLS`.

## Determinism verdict

**Not compliant end to end.** Existing Python helpers correctly cover quote multiplication/subtotals/discount arithmetic, order subtotal, paid-total aggregation, invoice status, date subtraction, stock shortage, and raw discount/refund threshold comparisons. Those helpers are a good foundation and do not need a rewrite.

The gaps are B07–B10 and B30: model-selected discount limits; a missing hard 25% policy cap; preferred-tier ambiguity; refund approval dependent on prompts/tool wording; return eligibility delegated to policy prose; outstanding balances not supplied by deterministic tools; and unspecified currency rounding. `SYSTEM_PROMPT` saying “never calculate” does not fix missing computational tools. The separate response-formulation prompt does not include that rule either. No live LLM transcript was used to claim that a particular response hallucinated a number; the confirmed issue is that these paths leave decisions/calculations to the model or provide incorrect facts.

## API completeness and response consistency

- All expected existing resource collections have list endpoints: customers, products, quotes, orders, invoices, approvals (pending), tasks, and runs. The order list exists and applies status filtering. No missing-list-endpoint bug remains in these resources. Chat and action/internal routes do not need artificial list endpoints.
- Invoice and order list/detail responses already share formatters. Customer list/detail currently agree, apart from the false tier value.
- Quotes duplicate serialization. The list contains `customer_name`, `approval_id`, and `created_at`, but the detail omits them. The shared fields currently agree. This is additive response-consistency work, not justification to restructure either response.
- Products duplicate common stock fields across list/low-stock serialization; the normal list uses `id`, while low-stock uses `product_id` and omits some aliases. Preserve those established shapes. There is no demonstrated conflicting stock value today; a private shared formatter can reduce future drift without deleting fields.
- Order detail currently returns the same summary as the list, without items/subtotal/shipping timestamps despite its module description. Itemized data exists in the service/tool. Treat adding those fields as a proposed additive improvement, not a proved frontend regression.
- Products, quotes, orders, and invoices have unbounded collection reads; tasks/runs have fixed 50-row caps without exposed pagination. These are limitations, not ignored query parameters. Pagination should be added only if wanted and with backward-compatible defaults.

## Clear optimization opportunities

### O01 — N+1 customer queries on quote and task lists

[QuoteRepository.list_all](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/db/repositories/quote_repository.py:29>) eagerly loads items but not customers; the quote route dereferences every customer's name. [FollowupRepository.list_all](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/backend/app/db/repositories/followup_repository.py:75>) loads neither, and the task route dereferences customer names. Add appropriate eager loading. Extra queries scale with distinct referenced customers because the session identity map may reuse a customer. Invoice/order lists already use joinedload correctly and should retain it.

### O02 — Avoid fresh policy connection pools and redundant reads

[search_business_policy](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/tools/policy_tools.py:44>) calls standalone [retrieve](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/rag/retriever.py:106>), which creates a new engine/session factory for each search and does not explicitly dispose the engine. The existing `retrieve_with_session` can use a session from the shared engine. No dependency is needed.

[get_days_overdue](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/tools/invoice_tools.py:129>) fetches the invoice through the service, then fetches it again for its label. Read it once. [get_communication_history](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/agents/tools/communication_tools.py:98>) fetches all communications then slices to `limit`; apply the limit in SQL when a bounded history is requested. Preserve full-history semantics where intentionally requested.

### O03 — Reduce long-held sessions and duplicate approval sessions

The approval route and resume facade each resolve the same record with separate sessions (B05). The scheduler holds its outer session across LLM execution, while individual tools open their own sessions. Commits expire its loaded task objects, so iterating a prefetched batch can also trigger refresh reads. Claim/read a task in a short transaction and finalize in another short transaction, keeping correctness and idempotency first. A per-tool session is otherwise a reasonable existing design; this audit does not recommend a session-architecture rewrite.

### O04 — Add measured indexes through a new migration

Migration [003](<C:/Users/Adeel Umar/Documents/AI-Operations-Manager/alembic/versions/003_create_domain_tables.py:18>) creates domain tables from ORM metadata. The domain models declare primary/unique constraints but no explicit filter/relationship indexes; migrations 001/002 only address RAG indexes. Existing UUID primary keys and unique business identifiers are already indexed and should not receive duplicates.

Strong candidates tied to current queries:

| Query path | Index candidate |
|---|---|
| Due-task sweep | followup_tasks(status, scheduled_at), or a pending-only scheduled_at index |
| Pending approvals ordered by creation | approval_requests(status, created_at) |
| Quotes found during approval resolution | quotes(approval_id) |
| Run audit logs ordered by time | audit_logs(run_id, timestamp) |
| Customer order/invoice/communication history | orders(customer_id, created_at), invoices(customer_id, issue_date), communications(customer_id, created_at) |
| Eager loading quote/order items and payments | quote_items(quote_id), order_items(order_id), payments(invoice_id) |
| Filtered business lists | quotes(status, created_at), orders(status, created_at), invoices(status, due_date/issue_date), selected for actual dominant query shapes |

Check row counts and EXPLAIN before adding the whole list; these are candidates, not measured bottlenecks. Ordinary B-tree indexes do not solve `%substring%` ILIKE search, and indexing stock_quantity alone does not directly solve comparison to another column. No speculative vector index is proposed for a small policy corpus. Changing model metadata or historical migration 003 alone would not upgrade already-created tables; approved index changes need a new migration.

### O05 — Safe cleanup

Verified unused imports in the requested directories:

- routes: approvals.status; products.UUID/HTTPException/InventoryRepository; tasks.HTTPException.
- nodes: check_inventory.ToolMessage; ChatGroq in check_invoice/create_quote/customer_mgmt/followup/formulate_response/resolve_issue; classify_intent.re/SYSTEM_PROMPT; followup.Any/select.
- tools: customer_tools.settings; invoice_tools.Decimal; quote_tools.json/uuid.

Remove the products route's `hasattr` fallbacks only in favor of direct verified method calls: both methods exist, and silently returning an empty catalog would hide a regression. Unused `check_refund_authorization` and audit helpers represent missing wiring, not code to delete. The misleading follow-up scheduling and stale repository docstrings should be corrected along with their affected behavior. Duplicate `get_db` definitions are cleanup, not evidence of two sessions per request. There is no reason to rename working modules or restructure the architecture.

## Proposed fix order after review

1. Restore real approval enforcement and execution: B01–B05, while preserving API paths/shapes and using the existing state/checkpointer architecture wherever possible. Any change to interruption handling is justified by the reproduced bug, not a redesign.
2. Fix lost discount persistence, incorrect balances/reminder outcomes, wrong-account task creation, stock/task concurrency, and ambiguous mutations: B06, B09–B18.
3. Make policy decisions deterministic, repair existing tool bindings and identifier handoffs, preserve conversation/clarification context, and correct remaining service/API validation: B07–B08 and B19–B30.
4. Apply eager loading, bounded reads, session/pool improvements, logging cleanup, and selected indexes with regression checks.
5. **Only if separately confirmed:** add/register/bind an individual follow-up creation tool, reusing the existing repository and making date/customer resolution explicit. Do not silently interpret an unparseable date as now.

New quote creation/edit tools, customer editing, payment recording tools, actual refund/return execution, delivery integrations, stale-quote discovery, and conversational task management are coverage suggestions for separate scope decisions. They are not included as automatic additions in this refinement pass.

For the approved fixes, the next deliverable will include a before/after diff and one-sentence rationale per fix, regression evidence, and exact Windows-compatible `curl.exe` commands with local fixture prerequisites. Curl can verify endpoint-visible behavior, but concurrency and true checkpoint persistence also require deterministic regression tests; a successful chat sentence alone is not proof. No post-fix commands are represented as verified in this audit-only stage.


# Conversational quote creation — fix and verification

The registered `create_quote` agent tool is now bound to the quotation workflow. It resolves customers by name/email/UUID using the existing CustomerService pattern and products by name/SKU/UUID using inventory_tools._find_product. Ambiguous records require clarification. Every price comes from the product catalog. All items are validated before saving, and one transaction commits the completed quote or rolls it back.

## Repository discrepancy

The brief assumed `POST /api/v1/quotes` and an existing creation service method. This checkout has only quote GET routes and no QuoteService creation method. The fix therefore adds the smallest necessary QuoteService.create_quote factory, reusing **QuoteLineItem**, **recalculate_quote**, **calculate_subtotal**, **calculate_discount_amount** and **calculate_quote_total**. No REST route was added or changed.

## Changed source files

| File | Change |
|---|---|
| `backend/app/services/quote_service.py` | Build a draft with unique identifiers and catalog-priced items, then delegate totals to existing calculations. Caller owns commit/rollback. |
| `agents/tools/quote_tools.py` | Add strict positive-integer item schema and create_quote tool. Reject missing/ambiguous identifiers; return structured JSON including quote_id, quote_number and exact totals. Correct the discount parameter description to the existing 25% cap. |
| `agents/tools/__init__.py` | Register create_quote in ALL_TOOLS. |
| `agents/graph/nodes/create_quote_node.py` | Bind create_quote and the existing catalog-listing tool; remove the unsupported-creation instruction. Return a canonical ASCII quote_id in the existing entities dictionary. |
| `backend/tests/audit/test_quote_creation.py` | Verify name/email/UUID resolution, catalog pricing, invalid quantities, missing later products, ambiguous customers, canonical identifiers, deterministic discount authorization, persisted stock/ledger updates and no repeat deduction. |
| `scripts/verify_quote_chat_live.py` | Reproducible real Groq/PostgreSQL HTTP-handler verification, with a resume option that continues on the same quote. |

The exact source/test/script patch is in **QUOTE_CREATION_CHANGES.diff**. Existing API paths, methods, response fields, environment files, AgentState schema and graph routing were not changed. `entities.quote_id` uses the already-existing response dictionary and entity name.

## Actual real HTTP verification

These requests used FastAPI's in-process HTTP TestClient with **real configured PostgreSQL, real Groq and persistent PostgresSaver**. No model or database mocks were used. They did not target the already-deployed public URL; this updated code still needs deployment. The scheduler was disabled only inside the verification process so unrelated due tasks were not executed.

One real quote was created: **86de2158-63b3-4cd6-8f4b-35e6c6c7778f**, number **Q-86DE215863B34CD68F4B35E6C6C7778F**. All HTTP requests returned **200**. Full unabridged request bodies, response bodies and database snapshots are in **QUOTE_CHAT_LIVE_RESULTS.json**.

| Requested step | Actual result |
|---|---|
| 1. POST /api/v1/chat: “Create a quote for Ahmed Industries for 20 ergonomic chairs.” | Created the draft for 20 Ergonomic Mesh Office Chairs at the stored $249.99 price. Subtotal/total **$4,999.80**; no discount. Response included quote number and UUID. |
| 2. POST /api/v1/chat: apply 15% to that UUID | **approval_required: false**. Discount **$749.97**, stored total **$4,249.83**, status **approved**. Ahmed is a preferred customer with a **15%** automatic threshold. |
| 3. GET /api/v1/approvals after 15% | Actual response: **[]**. A request at the threshold does not require approval. |
| 4. Approve the 15% request | Not applicable: no approval was created. The policy/tier was not modified to force this test. |
| Supplement: POST /api/v1/chat requesting 16% | Response: **“Manager approval required; the operation is paused.”**, **approval_required: true**, approval ID **e824f905-c177-5eb2-b001-a5e3760215bd**. |
| Supplement: GET /api/v1/approvals | Returned that pending **quote_discount_approval**, reason **“Discount of 16.0% exceeds the approval threshold of 15%.”**, with the correct quote UUID and checkpoint thread. |
| Supplement: POST /api/v1/approvals/e824f905-c177-5eb2-b001-a5e3760215bd/approve | **approval_decision: approved**. Actual execution result: **“Discount applied to Q-86DE215863B34CD68F4B35E6C6C7778F. Total: $4199.83. No order was created.”** |

The before-approval database snapshot retained **15%/$4,249.83** while status was pending_approval. The after-approval snapshot showed **16%/$4,199.83**, status approved and the matching approval ID.

The first response used typographic nonbreaking hyphens inside its human-readable UUID, so the verification initially stopped at its overly strict ASCII check. It continued on that same quote after normalizing those display hyphens, without creating a second record. The node now additionally returns the canonical identifier in entities.quote_id; the final regression verifies this. The raw first response is preserved as returned, not rewritten in the results artifact.

## Task 3 checks

**Yes — discount authorization is deterministic and shared.** apply_discount_to_quote calls `discount_limit(existing.customer)` and `check_discount_authorization(percent, threshold)` before calling QuoteService.apply_discount. QuoteService uses that same authorization helper. Thresholds are 10% regular / 15% preferred; above 25% is rejected. The LLM cannot select the threshold. A regression spies on the real shared helper and confirms a regular customer's 15% request calls it with Decimal('15') and Decimal('10'), raising ApprovalRequired before mutation.

**Yes — fulfillment deducts actual stock, not just status.** convert_quote_to_order delegates to QuoteService.convert_to_order and creates a **pending** order; conversion itself does not consume inventory. The fulfillment tool delegates to OrderService.fulfill_order, which calls InventoryService.update_inventory with `change_quantity=-item.quantity`, `reason='order_fulfilled'` and the order reference, then commits. In a separate isolated database regression, conversion retained stock **30**, fulfillment of 20 units reduced persisted stock to **10**, and the ledger recorded **-20/resulting balance 10**. A repeat fulfillment was rejected and stock stayed 10. No order service fix was needed.

## Validation and deployment

**106 offline tests passed**, including the existing service, graph, approval, migration and Vercel regressions. Git whitespace checking passed. The real verification quote remains approved at 16% in the configured database; it was not converted or fulfilled. Deploy the changed backend to make create_quote available on the public chat endpoint. No schema migration or new dependency is needed for this fix.

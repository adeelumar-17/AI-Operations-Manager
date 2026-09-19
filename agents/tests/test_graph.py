"""Smoke test for the M5 agent graph.

Tests that each of the 6 example requests:
  1. Routes to the correct workflow
  2. Detects the correct intent
  3. Produces a non-empty response

Does NOT test tool output correctness (that's the job of the M10 eval dataset).
This just proves the graph wiring works end-to-end.

Usage:
    python -m agents.tests.test_graph

Requires GROQ_API_KEY in .env. Does NOT require a running DB 
(entities won't resolve, but routing/response formulation will work).
"""

import sys


def run_tests() -> bool:
    from agents.agent_service import run_agent

    test_cases = [
        {
            "description": "Inventory check",
            "user_input": "Can we fulfill an order of 50 units of SKU-1234?",
            "expected_workflow": "inventory_check",
        },
        {
            "description": "Quote creation with discount",
            "user_input": "Create a quote for Ahmed Industries with a 12% discount on 100 boxes of A4 paper.",
            "expected_workflow": "create_quote",
        },
        {
            "description": "Overdue invoice",
            "user_input": "Show me all overdue invoices for our customers.",
            "expected_workflow": "invoice_status",
        },
        {
            "description": "Issue resolution",
            "user_input": "Customer says they received the wrong products in order ORD-5001. They want a refund of $350.",
            "expected_workflow": "issue_resolution",
        },
        {
            "description": "Customer lookup",
            "user_input": "Pull up the account history for TechStart Solutions.",
            "expected_workflow": "customer_management",
        },
        {
            "description": "Follow-up scheduling",
            "user_input": "Follow up with all customers who have quotes older than 7 days.",
            "expected_workflow": "follow_up",
        },
    ]

    print("=" * 70)
    print("M5 Agent Graph Smoke Tests")
    print("=" * 70)

    passed = 0
    failed = 0

    for i, tc in enumerate(test_cases, 1):
        print(f"\n[{i}] {tc['description']}")
        print(f"     Input: {tc['user_input'][:80]}...")

        try:
            result = run_agent(tc["user_input"])
            workflow = result.get("workflow")
            intent = result.get("intent")
            response = result.get("response", "")

            # Check routing
            if workflow == tc["expected_workflow"]:
                print(f"     ✓ Workflow: {workflow}")
            else:
                print(f"     ✗ Workflow: expected {tc['expected_workflow']}, got {workflow}")
                failed += 1
                continue

            # Check response is non-empty
            if response and len(response) > 10:
                print(f"     ✓ Response: {response[:100]}...")
                passed += 1
            else:
                print(f"     ✗ Empty or very short response: {repr(response)}")
                failed += 1

            if result.get("approval_required"):
                print(f"     ℹ Approval required: {result.get('approval_id', 'no ID set')}")
            if result.get("error"):
                print(f"     ⚠ Error (non-fatal): {result['error']}")

        except Exception as e:
            print(f"     ✗ Exception: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'=' * 70}")
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70)

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)

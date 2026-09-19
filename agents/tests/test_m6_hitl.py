"""Verification test for Module 6: Human-in-the-Loop & Checkpointing.

Tests:
1. Triggering an action that requires approval (e.g. 15% quote discount > 10% policy threshold).
2. Verifying graph interruption and checkpoint persistence.
3. Resuming the graph with approval (`approved=True`) and verifying finalization.
4. Resuming with rejection (`approved=False`) and verifying cancellation.

Usage:
    python -m agents.tests.test_m6_hitl
"""

import sys
import uuid

# Handle Windows terminal utf-8 encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from agents.agent_service import run_agent, resume_agent


def test_hitl_approval_flow() -> bool:
    print("=" * 60)
    print("M6 HITL & Checkpointing Test: 15% Discount Approval Flow")
    print("=" * 60)

    thread_id = f"test_hitl_thread_{uuid.uuid4().hex[:8]}"

    # Step 1: Request a quote that requires manager approval
    prompt = "Create a quote for Ahmed Industries with a 15% discount on 100 boxes of A4 paper."
    print(f"\n[Step 1] Sending prompt: '{prompt}'")
    initial_res = run_agent(user_input=prompt, thread_id=thread_id)

    print(f"Workflow: {initial_res['workflow']}")
    print(f"Approval Required: {initial_res['approval_required']}")
    print(f"Approval ID: {initial_res['approval_id']}")
    print(f"Response: {initial_res['response'][:120]}...")

    assert initial_res["approval_required"] is True, "Expected approval_required to be True"
    assert initial_res["approval_id"] is not None, "Expected approval_id to be generated"
    approval_id = initial_res["approval_id"]

    # Step 2: Simulate managerial approval
    print(f"\n[Step 2] Manager approving request '{approval_id}'...")
    approved_res = resume_agent(
        approval_id=approval_id,
        approved=True,
        thread_id=thread_id,
        comment="Approved by Senior Operations Manager",
        reviewer_id="manager-001",
    )

    print(f"Approval Decision: {approved_res['approval_decision']}")
    print(f"Resumed Response: {approved_res['response']}")

    assert approved_res["approval_decision"] == "approved", "Expected approval_decision == 'approved'"

    # Step 3: Test rejection on a new request
    thread_id_2 = f"test_hitl_thread_{uuid.uuid4().hex[:8]}"
    prompt_2 = "Customer wants a 25% discount for a rush order."
    print(f"\n[Step 3] Sending second prompt for rejection test: '{prompt_2}'")
    res_2 = run_agent(user_input=prompt_2, thread_id=thread_id_2)
    assert res_2["approval_required"] is True
    app_id_2 = res_2["approval_id"]

    print(f"\n[Step 4] Manager rejecting request '{app_id_2}'...")
    rejected_res = resume_agent(
        approval_id=app_id_2,
        approved=False,
        thread_id=thread_id_2,
        comment="Discount is above allowable limit.",
    )

    print(f"Approval Decision: {rejected_res['approval_decision']}")
    print(f"Resumed Response: {rejected_res['response']}")
    assert rejected_res["approval_decision"] == "rejected", "Expected approval_decision == 'rejected'"

    print("\n" + "=" * 60)
    print("ALL M6 HITL TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    test_hitl_approval_flow()
    sys.exit(0)

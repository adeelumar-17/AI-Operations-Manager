"""Benchmark and evaluation runner for the AI Operations Manager agent (Module 10)."""

import json
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from agents.agent_service import run_agent


def run_evaluation(dataset_path: str = "tests/eval/eval_cases.json") -> dict:
    if not os.path.exists(dataset_path):
        print(f"Dataset file not found at: {dataset_path}")
        return {"error": "Dataset not found"}

    with open(dataset_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    print("=" * 75)
    print(f"AI Operations Manager — M10 Benchmark Suite ({len(cases)} test cases)")
    print("=" * 75)
    print(f"{'ID':<9} | {'Expected Workflow':<20} | {'Actual Workflow':<20} | {'Routing':<8} | {'Approval':<8}")
    print("-" * 75)

    routing_correct = 0
    approval_correct = 0
    total = len(cases)
    results = []

    for case in cases:
        case_id = case["id"]
        expected_wf = case["workflow"]
        expect_approval = case["expect_approval"]
        prompt = case["prompt"]

        t0 = time.time()
        try:
            res = run_agent(user_input=prompt)
            actual_wf = res.get("workflow") or "none"
            actual_approval = bool(res.get("approval_required"))

            is_routing_ok = (actual_wf == expected_wf)
            is_approval_ok = (actual_approval == expect_approval)

            if is_routing_ok:
                routing_correct += 1
            if is_approval_ok:
                approval_correct += 1

            r_mark = "PASS" if is_routing_ok else "FAIL"
            a_mark = "PASS" if is_approval_ok else "FAIL"

            print(f"{case_id:<9} | {expected_wf:<20} | {actual_wf:<20} | {r_mark:<8} | {a_mark:<8}")

            results.append({
                "id": case_id,
                "prompt": prompt,
                "expected_workflow": expected_wf,
                "actual_workflow": actual_wf,
                "routing_passed": is_routing_ok,
                "approval_passed": is_approval_ok,
                "duration_sec": round(time.time() - t0, 2),
            })
        except Exception as exc:
            print(f"{case_id:<9} | {expected_wf:<20} | {'ERROR':<20} | FAIL     | FAIL")
            results.append({
                "id": case_id,
                "error": str(exc),
                "routing_passed": False,
                "approval_passed": False,
            })

    routing_acc = (routing_correct / total) * 100
    approval_acc = (approval_correct / total) * 100

    print("=" * 75)
    print("BENCHMARK SUMMARY:")
    print(f"  • Workflow Routing Accuracy: {routing_correct}/{total} ({routing_acc:.1f}%)")
    print(f"  • Approval Gating Accuracy:  {approval_correct}/{total} ({approval_acc:.1f}%)")
    print("=" * 75)

    return {
        "total_cases": total,
        "routing_accuracy": routing_acc,
        "approval_accuracy": approval_acc,
        "results": results,
    }


if __name__ == "__main__":
    run_evaluation()

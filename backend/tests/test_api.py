"""Integration tests for Module 8: FastAPI REST API Layer."""

import sys
from fastapi.testclient import TestClient

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.app.main import app


def test_api_endpoints():
    print("=" * 60)
    print("M8 API Tests: Health, OpenAPI, and Route Validation")
    print("=" * 60)

    client = TestClient(app)

    # 1. Health check
    res = client.get("/health")
    assert res.status_code == 200, f"Health check failed: {res.status_code}"
    print(f"✓ GET /health: {res.json()}")

    # 2. OpenAPI JSON
    res = client.get("/openapi.json")
    assert res.status_code == 200
    paths = res.json().get("paths", {})
    assert "/api/v1/chat" in paths
    assert "/api/v1/approvals" in paths
    print(f"✓ OpenAPI schema verified: {len(paths)} endpoints mounted.")

    # 3. Tasks trigger endpoint
    manager_headers = {"X-User-Id": "36ae02ac-133d-4ff0-969c-b879d2eb2820"}
    res = client.post("/api/v1/tasks/trigger", headers=manager_headers)
    assert res.status_code == 200
    print(f"✓ POST /api/v1/tasks/trigger: {res.json()}")

    # 4. Chat endpoint
    prompt = "Can we fulfill an order of 50 units of SKU-1234?"
    print(f"\n[Testing POST /api/v1/chat with: '{prompt}']")
    res = client.post("/api/v1/chat", json={"message": prompt}, headers=manager_headers)

    assert res.status_code == 200, f"Chat failed: {res.status_code} - {res.text}"
    chat_data = res.json()
    print(f"✓ Chat workflow: {chat_data.get('workflow')}")
    print(f"✓ Chat response: {chat_data.get('response')[:100]}...")

    print("\n" + "=" * 60)
    print("ALL M8 API TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    test_api_endpoints()

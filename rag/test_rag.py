"""End-to-end test for M3 RAG module.

Tests:
1. Ingests all 5 policy documents
2. Queries for each policy topic
3. Asserts the correct document title is returned as the top result

Usage:
    python -m rag.test_rag

Requires the DB to be up. Embeddings use local sentence-transformers (no API key needed).
"""

import os
import sys


def run_tests() -> bool:
    """Run all M3 RAG tests. Returns True if all pass."""
    from backend.app.core.config import settings
    from rag.ingestion.ingest import ingest_policies
    from rag.retriever import retrieve

    db_url_sync = settings.DATABASE_URL.replace(
        "postgresql+psycopg://", "postgresql+psycopg2://"
    )

    print("=" * 60)
    print("M3 RAG Tests")
    print("=" * 60)

    # Step 1: Ingest
    print("\n[1] Ingesting policies...")
    try:
        count = ingest_policies(db_url_sync, "data/policies", force=False)
        print(f"    ✓ Ingested/skipped. Total chunks available: checked.")
    except Exception as e:
        print(f"    ✗ Ingestion error: {e}")
        return False

    # Step 2: Run queries
    test_cases = [
        ("max discount for regular customers", "OfficeHub Discount Policy"),
        ("what is the return window", "OfficeHub Return Policy"),
        ("how long does shipping take", "OfficeHub Shipping Policy"),
        ("when is manager approval required", "OfficeHub Approval Policy"),
        ("payment terms and methods", "OfficeHub Payment Policy"),
    ]

    print("\n[2] Running retrieval tests...")
    passed = 0
    failed = 0

    for query, expected_title in test_cases:
        try:
            results = retrieve(query, db_url_sync, top_k=3)
            if not results:
                print(f"    ✗ '{query}' → No results returned")
                failed += 1
                continue

            top_result = results[0]
            if top_result.document_title == expected_title:
                print(
                    f"    ✓ '{query}'\n"
                    f"      → {top_result.document_title} (score: {top_result.similarity_score:.4f})"
                )
                passed += 1
            else:
                print(
                    f"    ✗ '{query}'\n"
                    f"      Expected: {expected_title}\n"
                    f"      Got:      {top_result.document_title} (score: {top_result.similarity_score:.4f})"
                )
                # Show all results for debugging
                for r in results:
                    print(f"         [{r.document_title}] score={r.similarity_score:.4f}")
                failed += 1
        except Exception as e:
            print(f"    ✗ '{query}' → Error: {e}")
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)

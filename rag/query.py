"""CLI for querying the RAG policy database.

Usage:
    python -m rag.query "your query here"
    
Example:
    python -m rag.query "discount policy"
    python -m rag.query "What is the refund process?"
"""

import os
import sys
from typing import Optional

from rag.retriever import retrieve


def main(query: str, top_k: int = 3, db_url: Optional[str] = None) -> None:
    """Query the policy database and print results.
    
    Args:
        query: The search query
        top_k: Number of results to return
        db_url: Database URL (defaults to env var DATABASE_URL)
    """
    if not db_url:
        db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        print("Error: DATABASE_URL environment variable not set", file=sys.stderr)
        print("Set it via: export DATABASE_URL='postgresql://user:pass@localhost/db'", file=sys.stderr)
        sys.exit(1)
    
    print(f"\n🔍 Searching for: {query}\n")
    print("-" * 80)
    
    try:
        results = retrieve(query, db_url, top_k=top_k)
    except Exception as e:
        print(f"Error during search: {e}", file=sys.stderr)
        sys.exit(1)
    
    if not results:
        print("No results found.")
        print("-" * 80)
        return
    
    for i, result in enumerate(results, 1):
        print(f"\n📄 Result {i}: {result.document_title}")
        print(f"   Similarity: {result.similarity_score:.4f}")
        print(f"   ---")
        print(f"   {result.content}")
        if result.metadata:
            print(f"   [Source: {result.metadata.get('source_file', 'unknown')}]")
    
    print("\n" + "-" * 80)
    print(f"\n✓ Found {len(results)} results")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    query = " ".join(sys.argv[1:])
    main(query)

"""CLI ingestion entry point for RAG policy documents."""

import argparse
import sys
from rag.ingestion.ingest import ingest_policies
from backend.app.core.config import settings


def main():
    parser = argparse.ArgumentParser(description="Ingest business policy markdown files into pgvector.")
    parser.add_argument(
        "db_url",
        nargs="?",
        default=settings.DATABASE_URL,
        help="Database connection URL (defaults to settings.DATABASE_URL from .env)",
    )
    parser.add_argument(
        "--policies-dir",
        "-d",
        default="data/policies",
        help="Path to directory containing policy markdown files (default: data/policies)",
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force re-ingestion of existing documents (deletes and recreates existing chunks)",
    )

    args = parser.parse_args()

    # Ensure sync driver compatibility for create_engine
    db_url = args.db_url.replace("postgresql+psycopg://", "postgresql+psycopg2://")

    print(f"Ingesting policies from '{args.policies_dir}' into database...")
    print(f"Force re-ingest: {args.force}")

    try:
        count = ingest_policies(db_url=db_url, policies_dir=args.policies_dir, force=args.force)
        print(f"Successfully ingested {count} chunks.")
    except Exception as e:
        print(f"Error during ingestion: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

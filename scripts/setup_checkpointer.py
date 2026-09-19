"""
One-time setup script for LangGraph's PostgreSQL Checkpointer (PostgresSaver).

This script initializes the checkpoint schema tables (checkpoints, checkpoint_blobs,
checkpoint_writes, checkpoint_migrations) in PostgreSQL using DATABASE_URL_DIRECT
(unpooled direct connection).

Usage:
    python scripts/setup_checkpointer.py
"""

import sys
import os
import re

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def mask_password(url: str) -> str:
    """Mask password in connection URL for safe logging."""
    return re.sub(r":([^:@]+)@", ":****@", url)


def main() -> int:
    print("=" * 70)
    print("LangGraph PostgresSaver Schema Initialization")
    print("=" * 70)

    try:
        from backend.app.core.config import settings
    except ImportError as e:
        print(f"Error importing app configuration: {e}")
        print("Ensure you run this script from the project root directory:")
        print("    python scripts/setup_checkpointer.py")
        return 1

    raw_url = settings.DATABASE_URL_DIRECT or settings.DATABASE_URL
    if not raw_url:
        print("Error: Neither DATABASE_URL_DIRECT nor DATABASE_URL is configured.")
        print("Please set DATABASE_URL_DIRECT in your .env file.")
        return 1

    # Convert SQLAlchemy dialect format (postgresql+psycopg://) to libpq format (postgresql://)
    conn_info = raw_url.replace("postgresql+psycopg://", "postgresql://")

    masked_url = mask_password(raw_url)
    print(f"\nTarget Database URL: {masked_url}")
    if settings.DATABASE_URL_DIRECT:
        print("  -> Using direct connection (DATABASE_URL_DIRECT) as recommended.")
    else:
        print("  -> Warning: DATABASE_URL_DIRECT not set. Falling back to DATABASE_URL.")

    try:
        from langgraph.checkpoint.postgres import PostgresSaver
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as e:
        print(f"\nMissing required dependency: {e}")
        print("Please install requirements first:")
        print("    pip install -r requirements.txt")
        return 1

    print("\nConnecting to database and running PostgresSaver.setup()...")
    try:
        # Connect directly with autocommit=True and row_factory=dict_row
        with psycopg.connect(conn_info, autocommit=True, row_factory=dict_row) as conn:
            checkpointer = PostgresSaver(conn)
            checkpointer.setup()

        print("\n" + "=" * 70)
        print("SUCCESS: LangGraph checkpoint tables created successfully!")
        print("Tables initialized:")
        print("  - checkpoints")
        print("  - checkpoint_blobs")
        print("  - checkpoint_writes")
        print("  - checkpoint_migrations")
        print("=" * 70)
        return 0

    except Exception as exc:
        print(f"\nFailed to set up checkpoint tables: {exc}")
        print("\nTroubleshooting tips:")
        print("  1. Verify your database is accessible and credentials are correct.")
        print("  2. Ensure you are using the unpooled direct connection string (DATABASE_URL_DIRECT).")
        print("  3. Check that the database user has CREATE TABLE and CREATE INDEX permissions.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

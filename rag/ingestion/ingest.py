"""Policy ingestion module for RAG system.

Reads markdown policy documents, chunks them by sections, generates embeddings,
and stores them in the PostgreSQL database with pgvector.

Idempotent: re-running on an already-ingested file skips it (based on source_path).
Use --force to delete existing chunks and re-ingest.
"""

import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from rag.embeddings import embed_text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ingest_policies(
    db_url: str,
    policies_dir: str = "data/policies",
    force: bool = False,
) -> int:
    """Ingest all policy markdown files into the vector database.

    Reads all .md files from policies_dir, chunks by ## headings,
    generates embeddings, and inserts into document_chunks table.

    Idempotent by default: files whose source_path already exists in the
    documents table are skipped unless force=True.

    Args:
        db_url: Database connection URL
        policies_dir: Path to directory containing policy markdown files
        force: If True, delete and re-ingest already-ingested documents

    Returns:
        Total number of new chunks ingested

    Raises:
        FileNotFoundError: If policies_dir does not exist
    """
    policies_path = Path(policies_dir)
    if not policies_path.exists():
        raise FileNotFoundError(f"Policies directory not found: {policies_dir}")

    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)

    policy_files = sorted(policies_path.glob("*.md"))
    if not policy_files:
        print(f"No markdown files found in {policies_dir}")
        return 0

    total_chunks = 0

    for policy_file in policy_files:
        print(f"\nIngesting {policy_file.name}...")
        with Session() as session:
            chunks = ingest_policy_file(policy_file, session, force=force)
        total_chunks += chunks
        print(f"  -> Ingested {chunks} chunks")

    print(f"\n[OK] Total: {total_chunks} chunks ingested")
    return total_chunks


def ingest_policy_file(
    file_path: Path,
    session: Session,
    force: bool = False,
) -> int:
    """Ingest a single policy markdown file.

    Args:
        file_path: Path to the markdown file
        session: SQLAlchemy session (caller is responsible for commit/rollback)
        force: If True, delete existing document + chunks before re-ingesting

    Returns:
        Number of chunks ingested (0 if skipped due to idempotency)
    """
    source_path = str(file_path)

    # --- Idempotency check --------------------------------------------------
    existing = session.execute(
        text("SELECT id FROM documents WHERE source_path = :sp"),
        {"sp": source_path},
    ).fetchone()

    if existing and not force:
        print(f"  [skip] {file_path.name} already ingested (use --force to re-ingest)")
        return 0

    if existing and force:
        # Cascade deletes document_chunks via ON DELETE CASCADE
        session.execute(
            text("DELETE FROM documents WHERE source_path = :sp"),
            {"sp": source_path},
        )
        session.commit()
        print(f"  [force] Deleted existing data for {file_path.name}")

    # --- Read and parse file -------------------------------------------------
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    title_match = re.match(r"^#\s+(.+?)$", content, re.MULTILINE)
    title = (
        title_match.group(1)
        if title_match
        else file_path.stem.replace("_", " ").title()
    )

    # --- Insert document record ----------------------------------------------
    doc_id = str(uuid.uuid4())
    session.execute(
        text(
            """
            INSERT INTO documents (id, title, source_path, doc_type, created_at)
            VALUES (:id, :title, :source_path, :doc_type, :created_at)
            """
        ),
        {
            "id": doc_id,
            "title": title,
            "source_path": source_path,
            "doc_type": "policy",
            "created_at": datetime.now(timezone.utc),
        },
    )
    session.commit()

    # --- Chunk, embed, insert ------------------------------------------------
    chunks = _chunk_by_sections(content)
    chunk_count = 0

    for chunk_index, chunk_content in enumerate(chunks, 1):
        stripped = chunk_content.strip()
        if not stripped:
            continue

        embedding = embed_text(stripped)
        # pgvector expects the literal string '[0.1,0.2,...]'
        embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"

        session.execute(
            text(
                """
                INSERT INTO document_chunks
                    (id, document_id, chunk_index, content, metadata, embedding, created_at)
                VALUES
                    (:id, :document_id, :chunk_index, :content, CAST(:metadata AS jsonb),
                     CAST(:embedding AS vector), :created_at)
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "document_id": doc_id,
                "chunk_index": chunk_index,
                "content": stripped,
                "metadata": f'{{"source_file": "{file_path.name}", "section_index": {chunk_index}}}',
                "embedding": embedding_str,
                "created_at": datetime.now(timezone.utc),
            },
        )
        chunk_count += 1

    session.commit()
    return chunk_count


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _chunk_by_sections(content: str) -> list[str]:
    """Split markdown content into chunks by ## (section) headings.

    Includes the heading with each chunk's content.

    Args:
        content: Full markdown content

    Returns:
        List of text chunks, each starting with a ## heading (or the intro text)
    """
    # Split on ## headings; re.split returns the content *between* the separators
    parts = re.split(r"^(##\s+.+)$", content, flags=re.MULTILINE)

    # parts alternates between: [pre-heading-text, heading, body, heading, body, ...]
    # Recombine heading + body pairs
    chunks: list[str] = []

    # The first element is everything before the first ## heading (title + intro)
    intro = parts[0].strip()
    if intro:
        chunks.append(intro)

    # Walk the (heading, body) pairs
    i = 1
    while i < len(parts) - 1:
        heading = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ""
        chunks.append(f"{heading}\n{body}".strip())
        i += 2

    return [c for c in chunks if c]


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m rag.ingestion <database_url> [policies_dir] [--force]")
        sys.exit(1)

    db_url = sys.argv[1]
    policies_dir = "data/policies"
    force_flag = False

    for arg in sys.argv[2:]:
        if arg == "--force":
            force_flag = True
        else:
            policies_dir = arg

    try:
        ingest_policies(db_url, policies_dir, force=force_flag)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

"""Retriever module for semantic search over policy documents.

Uses pgvector cosine similarity to find the most relevant policy sections
in response to a query.

Two entry points:
  retrieve()              — standalone (creates its own DB connection)
  retrieve_with_session() — accepts an existing SQLAlchemy Session (used by agent tools)
"""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from rag.embeddings import embed_query


@dataclass
class SearchResult:
    """Result of a semantic search query."""

    chunk_id: str
    document_title: str
    content: str
    similarity_score: float
    metadata: dict

    def __repr__(self) -> str:
        return (
            f"SearchResult(title={self.document_title!r}, "
            f"score={self.similarity_score:.4f})"
        )


# ---------------------------------------------------------------------------
# Core retrieval logic (shared)
# ---------------------------------------------------------------------------

_SIMILARITY_SQL = text(
    """
    SELECT
        dc.id,
        d.title,
        dc.content,
        1 - (dc.embedding <=> CAST(:query_embedding AS vector)) AS similarity,
        dc.metadata
    FROM document_chunks dc
    JOIN documents d ON dc.document_id = d.id
    WHERE dc.embedding IS NOT NULL
    ORDER BY dc.embedding <=> CAST(:query_embedding AS vector)
    LIMIT :top_k
    """
)


def _rows_to_results(rows) -> list[SearchResult]:
    return [
        SearchResult(
            chunk_id=str(row[0]),
            document_title=row[1],
            content=row[2],
            similarity_score=float(row[3]),
            metadata=row[4] or {},
        )
        for row in rows
    ]


def _embedding_to_str(embedding: list[float]) -> str:
    """Convert a Python list of floats to pgvector's literal format '[v1,v2,...]'."""
    return "[" + ",".join(str(v) for v in embedding) + "]"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def retrieve_with_session(
    query: str,
    session: Session,
    top_k: int = 3,
) -> list[SearchResult]:
    """Retrieve the most relevant policy sections for a query.

    Uses an existing SQLAlchemy session — preferred for agent tools so all
    DB calls share the same transaction context.

    Args:
        query: The search query
        session: An open SQLAlchemy Session
        top_k: Number of results to return (default 3)

    Returns:
        List of SearchResult objects ranked by similarity (highest first)
    """
    query_embedding_str = _embedding_to_str(embed_query(query))
    rows = session.execute(
        _SIMILARITY_SQL,
        {"query_embedding": query_embedding_str, "top_k": top_k},
    ).fetchall()
    return _rows_to_results(rows)


def retrieve(
    query: str,
    db_url: str,
    top_k: int = 3,
) -> list[SearchResult]:
    """Retrieve the most relevant policy sections for a query.

    Standalone variant that manages its own DB connection. Useful for CLI
    scripts and tests that don't have an existing session.

    Args:
        query: The search query
        db_url: Database connection URL
        top_k: Number of results to return (default 3)

    Returns:
        List of SearchResult objects ranked by similarity (highest first)
    """
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as session:
        return retrieve_with_session(query, session, top_k=top_k)

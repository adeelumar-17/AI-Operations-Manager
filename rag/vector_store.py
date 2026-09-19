"""Vector store facade for the RAG system.

Thin wrapper around the retriever and ingestion modules that provides a
single coherent interface for storing and searching policy document embeddings.
Both the agent tools and CLI scripts should import through this module rather
than calling retriever/ingest directly.
"""

from pathlib import Path

from sqlalchemy.orm import Session

from rag.retriever import SearchResult, retrieve, retrieve_with_session
from rag.ingestion.ingest import ingest_policies, ingest_policy_file


class VectorStore:
    """Interface for ingesting and searching policy documents.

    Wraps the retriever and ingestion modules behind a stable API so callers
    don't need to know the underlying implementation details.

    Args:
        db_url: PostgreSQL connection URL with pgvector extension enabled
    """

    def __init__(self, db_url: str) -> None:
        self._db_url = db_url

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def ingest_directory(
        self,
        policies_dir: str = "data/policies",
        force: bool = False,
    ) -> int:
        """Ingest all markdown policy files from a directory.

        Idempotent by default — files already in the DB are skipped.

        Args:
            policies_dir: Path to the directory containing .md files
            force: If True, re-ingest even if documents already exist

        Returns:
            Total number of chunks inserted
        """
        return ingest_policies(self._db_url, policies_dir, force=force)

    def ingest_file(
        self,
        file_path: str | Path,
        session: Session,
        force: bool = False,
    ) -> int:
        """Ingest a single markdown policy file using an existing session.

        Args:
            file_path: Path to the .md file
            session: Open SQLAlchemy session
            force: Re-ingest even if the file was previously ingested

        Returns:
            Number of chunks inserted (0 if skipped)
        """
        return ingest_policy_file(Path(file_path), session, force=force)

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 3,
    ) -> list[SearchResult]:
        """Search policy documents for the most relevant chunks.

        Creates its own DB connection (standalone use).

        Args:
            query: Natural language search query
            top_k: Number of results to return

        Returns:
            Ranked list of SearchResult objects
        """
        return retrieve(query, self._db_url, top_k=top_k)

    def search_with_session(
        self,
        query: str,
        session: Session,
        top_k: int = 3,
    ) -> list[SearchResult]:
        """Search policy documents using an existing DB session.

        Preferred inside agent tools so all DB access shares a single session.

        Args:
            query: Natural language search query
            session: Open SQLAlchemy session
            top_k: Number of results to return

        Returns:
            Ranked list of SearchResult objects
        """
        return retrieve_with_session(query, session, top_k=top_k)

"""RAG (Retrieval-Augmented Generation) package for AI Operations Manager.

Provides semantic search over policy documents stored in PostgreSQL + pgvector.

Primary interfaces:
  - retrieve()        — standalone retrieval (manages its own DB connection)
  - embed_query()     — embed a query string using the configured backend
  - ingest_policies() — ingest markdown policy docs into the vector store
"""

from rag.embeddings import embed_query, embed_text
from rag.retriever import retrieve, retrieve_with_session
from rag.ingestion.ingest import ingest_policies

__all__ = [
    "embed_query",
    "embed_text",
    "retrieve",
    "retrieve_with_session",
    "ingest_policies",
]

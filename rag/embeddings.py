"""Embeddings module for RAG system.

Uses sentence-transformers locally (all-MiniLM-L6-v2, 384 dimensions).
No API key required.

The embedding dimension MUST match the VECTOR(384) column in document_chunks.
If you change the model, run a new Alembic migration to update the column dimension
and re-ingest all documents.

Supported backends:
  - 'sentence-transformers' (default): local, free, 384-dim
  - 'openai': requires OPENAI_API_KEY, 1536-dim (needs schema migration to use)
"""

import os
from functools import lru_cache

# Dimension produced by 'all-MiniLM-L6-v2' — must match VECTOR(384) in DB
EMBEDDING_DIM = 384


def embed_text(text: str) -> list[float]:
    """Generate embedding for a given text.

    Args:
        text: The text to embed.

    Returns:
        A list of floats representing the embedding vector.

    Raises:
        ValueError: If embedding model is not configured or fails.
    """
    backend = _get_embedding_backend()

    if backend == "openai":
        return _embed_with_openai(text)
    else:
        return _embed_with_sentence_transformers(text)


def embed_query(query: str) -> list[float]:
    """Generate embedding for a search query.

    Uses the same model as embed_text for consistency (symmetric embeddings).

    Args:
        query: The query string to embed.

    Returns:
        A list of floats representing the embedding vector.
    """
    return embed_text(query)


def _get_embedding_backend() -> str:
    """Determine which embedding backend to use.

    Priority:
    1. EMBEDDING_BACKEND environment variable
    2. Falls back to 'sentence-transformers'
    """
    backend = os.getenv("EMBEDDING_BACKEND", "sentence-transformers").lower()
    if backend in ("openai", "sentence-transformers"):
        return backend
    return "sentence-transformers"


@lru_cache(maxsize=1)
def _get_sentence_transformer_model():
    """Load the sentence-transformers model (cached after first load)."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise ImportError(
            "sentence-transformers is required. "
            "Install with: pip install sentence-transformers"
        )

    model_name = os.getenv("SENTENCE_TRANSFORMERS_MODEL", "all-MiniLM-L6-v2")
    return SentenceTransformer(model_name)


def _embed_with_sentence_transformers(text: str) -> list[float]:
    """Generate embedding using the local sentence-transformers model.

    Uses all-MiniLM-L6-v2 by default, producing exactly 384-dimensional vectors.
    The model is loaded once and cached for the process lifetime.

    Args:
        text: The text to embed.

    Returns:
        384-dimensional embedding vector.
    """
    model = _get_sentence_transformer_model()
    embedding = model.encode(text, convert_to_numpy=True).tolist()
    return embedding


def _embed_with_openai(text: str) -> list[float]:
    """Generate embedding using OpenAI's API (1536 dims).

    NOTE: Using OpenAI requires a schema migration to change VECTOR(384)
    to VECTOR(1536) and re-ingesting all documents.

    Args:
        text: The text to embed.

    Returns:
        1536-dimensional embedding vector.

    Raises:
        ImportError: If openai package is not installed.
        ValueError: If OPENAI_API_KEY is not set.
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError(
            "openai package required for OpenAI embeddings. "
            "Install with: pip install openai"
        )

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")

    client = OpenAI(api_key=api_key)
    response = client.embeddings.create(
        input=text,
        model="text-embedding-3-small"
    )
    return response.data[0].embedding

"""Change embedding vector dimension from 1536 to 384.

Switches the document_chunks.embedding column from VECTOR(1536) (OpenAI)
to VECTOR(384) (sentence-transformers all-MiniLM-L6-v2, local, no API key).

IMPORTANT: This migration also deletes all existing document_chunks and document
rows because changing a vector column dimension requires dropping and recreating it,
and any existing embeddings at 1536 dims would be invalid at 384 dims anyway.

After running this migration, re-ingest all policy documents:
    python -m rag.ingestion postgresql://... --force

Revision ID: 002
Revises: 001
Create Date: 2026-09-14
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Delete any existing embeddings (they are 1536-dim and invalid for 384-dim)
    op.execute("DELETE FROM document_chunks")
    op.execute("DELETE FROM documents")

    # 2. Drop the IVFFlat index on the embedding column if it exists
    #    (index must be dropped before altering column type)
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE indexname = 'idx_document_chunks_embedding'
            ) THEN
                DROP INDEX idx_document_chunks_embedding;
            END IF;
        END $$;
        """
    )

    # 3. Drop the old 1536-dim embedding column and recreate as 384-dim
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE document_chunks ADD COLUMN embedding vector(384)")

    # 4. Note: We skip recreating the IVFFlat index here because IVFFlat requires
    #    enough rows to build meaningful clusters (typically 100+ rows per list).
    #    The index will be created manually after ingestion, or added in a later migration.
    #    For now, pgvector will use an exact (sequential) scan which is fine for small datasets.


def downgrade() -> None:
    # Revert to 1536-dim (also clears data since we can't resize embeddings)
    op.execute("DELETE FROM document_chunks")
    op.execute("DELETE FROM documents")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE indexname = 'idx_document_chunks_embedding'
            ) THEN
                DROP INDEX idx_document_chunks_embedding;
            END IF;
        END $$;
        """
    )
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE document_chunks ADD COLUMN embedding vector(1536)")

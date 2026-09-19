"""Create all domain tables (customers, products, inventory, quotes, orders, invoices, approvals, tasks, audit_logs).

Revision ID: 003
Revises: 002
Create Date: 2026-09-14
"""

from alembic import op
from backend.app.db.models import Base


# revision identifiers, used by Alembic.
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use SQLAlchemy's metadata.create_all with checkfirst=True
    # This automatically generates all models defined in backend/app/db/models
    # while preserving existing tables like documents and document_chunks.
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    # Dropping non-RAG domain tables
    domain_tables = [
        "audit_logs",
        "agent_messages",
        "agent_runs",
        "agent_conversations",
        "approval_requests",
        "followup_tasks",
        "communications",
        "payments",
        "invoices",
        "order_items",
        "orders",
        "quote_items",
        "quotes",
        "inventory",
        "products",
        "suppliers",
        "customers",
        "users",
    ]
    for table_name in domain_tables:
        op.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")

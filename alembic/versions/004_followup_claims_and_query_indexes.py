"""Track follow-up claims and index existing operational query paths.

Revision ID: 004
Revises: 003
"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None

INDEXES = [
    ("ix_followup_due", "followup_tasks", ["status", "scheduled_at"]),
    ("ix_approval_pending", "approval_requests", ["status", "created_at"]),
    ("ix_quote_approval", "quotes", ["approval_id"]),
    ("ix_audit_run_time", "audit_logs", ["run_id", "timestamp"]),
    ("ix_quote_items_quote", "quote_items", ["quote_id"]),
    ("ix_order_items_order", "order_items", ["order_id"]),
    ("ix_payments_invoice", "payments", ["invoice_id"]),
]


def upgrade():
    inspector = sa.inspect(op.get_bind())
    # 003 imports current metadata, so a fresh installation already has this column.
    if "started_at" not in {c["name"] for c in inspector.get_columns("followup_tasks")}:
        op.add_column("followup_tasks", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    for name, table, columns in INDEXES:
        if name not in {i["name"] for i in inspector.get_indexes(table)}:
            op.create_index(name, table, columns)


def downgrade():
    for name, table, _ in reversed(INDEXES):
        op.drop_index(name, table_name=table)
    op.drop_column("followup_tasks", "started_at")

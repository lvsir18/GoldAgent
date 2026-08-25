"""Initial GoldAgent schema.

Revision ID: 0001
"""
from alembic import op
from backend.app.db.base import Base
from backend.app.db import models  # noqa: F401

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # Keep this historical revision stable as later entities are added.
    tables = [table for table in Base.metadata.sorted_tables if table.name not in {"refresh_tokens", "forecasts"}]
    Base.metadata.create_all(bind=bind, tables=tables)


def downgrade():
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)

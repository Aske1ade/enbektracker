"""Add extended task priority levels

Revision ID: d90b4f1c2a10
Revises: c4f7d5b8e2aa
Create Date: 2026-02-24 10:05:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "d90b4f1c2a10"
down_revision = "c4f7d5b8e2aa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE taskpriority ADD VALUE IF NOT EXISTS 'urgent'")
    op.execute("ALTER TYPE taskpriority ADD VALUE IF NOT EXISTS 'immediate'")


def downgrade() -> None:
    # PostgreSQL enums do not support dropping values without full type recreation.
    pass

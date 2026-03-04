"""Add icon field to projects

Revision ID: c2a6e8d9b4c0
Revises: 7b9d4f1a2c30
Create Date: 2026-03-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c2a6e8d9b4c0"
down_revision = "7b9d4f1a2c30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("project", sa.Column("icon", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("project", "icon")

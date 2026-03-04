"""Expand project icon length and add reader project member role

Revision ID: b2c3d4e5f6a7
Revises: f0d1e2a3b4c5
Create Date: 2026-03-04 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a7"
down_revision = "f0d1e2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "project",
        "icon",
        existing_type=sa.String(length=32),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    op.execute("ALTER TYPE projectmemberrole ADD VALUE IF NOT EXISTS 'reader'")


def downgrade() -> None:
    # PostgreSQL does not support dropping enum values directly.
    # Keep the enum as-is and only revert project icon column length.
    op.alter_column(
        "project",
        "icon",
        existing_type=sa.String(length=255),
        type_=sa.String(length=32),
        existing_nullable=True,
    )

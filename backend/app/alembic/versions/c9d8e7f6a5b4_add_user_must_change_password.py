"""Add must_change_password flag to user

Revision ID: c9d8e7f6a5b4
Revises: b2c3d4e5f6a7
Create Date: 2026-03-04 13:05:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c9d8e7f6a5b4"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.execute('UPDATE "user" SET must_change_password = false WHERE must_change_password IS NULL')
    op.alter_column("user", "must_change_password", server_default=None)


def downgrade() -> None:
    op.drop_column("user", "must_change_password")

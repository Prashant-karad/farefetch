"""publishers can live on their own websites

Revision ID: b7c1d2e3f4a5
Revises: e40a277a2ef3
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7c1d2e3f4a5"
down_revision: Union[str, Sequence[str], None] = "e40a277a2ef3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("publishers", sa.Column("website_url", sa.String(length=500), nullable=True))
    op.add_column("resources", sa.Column("origin_url", sa.String(length=1000), nullable=True))


def downgrade() -> None:
    op.drop_column("resources", "origin_url")
    op.drop_column("publishers", "website_url")

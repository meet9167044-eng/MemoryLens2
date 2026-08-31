"""Add TEMPORAL DOMAIN relationship types

Revision ID: 30e8c0b71561
Revises: 39018a2ee749
Create Date: 2026-08-31 23:51:09.992862

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '30e8c0b71561'
down_revision: Union[str, Sequence[str], None] = '39018a2ee749'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE relationship_type ADD VALUE IF NOT EXISTS 'temporal';")
    op.execute("ALTER TYPE relationship_type ADD VALUE IF NOT EXISTS 'domain';")


def downgrade() -> None:
    pass

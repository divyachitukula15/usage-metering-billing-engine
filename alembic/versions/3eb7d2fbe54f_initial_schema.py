"""initial schema

Revision ID: 3eb7d2fbe54f
Revises: 
Create Date: 2026-11-19 19:44:25.295704

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3eb7d2fbe54f'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Baseline existing database schema."""
    pass


def downgrade() -> None:
    """No changes to revert."""
    pass

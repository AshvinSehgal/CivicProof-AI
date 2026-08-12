"""enable postgis and add incident location

Revision ID: 68e1e5fcc511
Revises: c5a2dbc094c3
Create Date: 2026-08-11 22:58:35.953986

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '68e1e5fcc511'
down_revision: Union[str, Sequence[str], None] = 'c5a2dbc094c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass

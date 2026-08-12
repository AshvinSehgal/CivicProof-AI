"""enable postgis and add incident location

Revision ID: 68e1e5fcc511
Revises: c5a2dbc094c3
Create Date: 2026-08-11 22:58:35.953986

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geography
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '68e1e5fcc511'
down_revision: Union[str, Sequence[str], None] = 'c5a2dbc094c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column(
        'incidents',
        sa.Column(
            'location',
            Geography(geometry_type='POINT', srid=4326, spatial_index=False),
            nullable=True
        )
    )
    op.add_column(
        'incidents',
        sa.Column('embedding', Vector(384), nullable=True)
    )
    op.execute(
        """
        UPDATE incidents
        SET location = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        """
    )
    op.alter_column('incidents', 'location', nullable=False)
    op.create_index(
        'ix_incidents_location_gist',
        'incidents',
        ['location'],
        unique=False,
        postgresql_using='gist'
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_incidents_location_gist', table_name='incidents')
    op.drop_column('incidents', 'embedding')
    op.drop_column('incidents', 'location')

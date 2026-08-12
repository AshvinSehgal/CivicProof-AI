"""create incident clusters

Revision ID: b847f4269a12
Revises: 68e1e5fcc511
Create Date: 2026-08-11 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from geoalchemy2 import Geography

revision: str = 'b847f4269a12'
down_revision: Union[str, Sequence[str], None] = '68e1e5fcc511'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        'incident_clusters',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=50), server_default='active', nullable=False),
        sa.Column('centroid', Geography(geometry_type='POINT', srid=4326, spatial_index=False), nullable=False),
        sa.Column('first_reported_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_reported_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('report_count', sa.Integer(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        'ix_incident_clusters_centroid_gist',
        'incident_clusters',
        ['centroid'],
        unique=False,
        postgresql_using='gist'
    )
    op.create_index(
        'ix_incident_clusters_category_status',
        'incident_clusters',
        ['category', 'status'],
        unique=False
    )
    op.create_table(
        'incident_cluster_members',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cluster_id', sa.Integer(), nullable=False),
        sa.Column('incident_id', sa.Integer(), nullable=False),
        sa.Column('distance_meters', sa.Float(), nullable=False),
        sa.Column('link_score', sa.Float(), nullable=False),
        sa.Column('link_reason', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('linked_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['cluster_id'], ['incident_clusters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('incident_id', name='uq_incident_cluster_members_incident_id')
    )
    op.create_index(
        'ix_incident_cluster_members_cluster_id',
        'incident_cluster_members',
        ['cluster_id'],
        unique=False
    )

def downgrade() -> None:
    op.drop_index('ix_incident_cluster_members_cluster_id', table_name='incident_cluster_members')
    op.drop_table('incident_cluster_members')
    op.drop_index('ix_incident_clusters_category_status', table_name='incident_clusters')
    op.drop_index('ix_incident_clusters_centroid_gist', table_name='incident_clusters')
    op.drop_table('incident_clusters')

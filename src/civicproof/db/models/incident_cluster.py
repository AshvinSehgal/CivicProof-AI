from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from geoalchemy2 import Geography
from civicproof.db.base import Base

class IncidentCluster(Base):
    __tablename__ = 'incident_clusters'

    id = Column(Integer, primary_key=True)
    category = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False, server_default='active')
    centroid = Column(Geography(geometry_type='POINT', srid=4326, spatial_index=False), nullable=False)
    first_reported_at = Column(DateTime(timezone=True), nullable=False)
    last_reported_at = Column(DateTime(timezone=True), nullable=False)
    report_count = Column(Integer, nullable=False, server_default='1')
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('ix_incident_clusters_centroid_gist', 'centroid', postgresql_using='gist'),
        Index('ix_incident_clusters_category_status', 'category', 'status'),
    )

class IncidentClusterMember(Base):
    __tablename__ = 'incident_cluster_members'

    id = Column(Integer, primary_key=True)
    cluster_id = Column(Integer, ForeignKey('incident_clusters.id', ondelete='CASCADE'), nullable=False)
    incident_id = Column(Integer, ForeignKey('incidents.id', ondelete='CASCADE'), nullable=False)
    distance_meters = Column(Float, nullable=False)
    link_score = Column(Float, nullable=False)
    link_reason = Column(JSONB, nullable=False)
    linked_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('incident_id', name='uq_incident_cluster_members_incident_id'),
        Index('ix_incident_cluster_members_cluster_id', 'cluster_id'),
    )

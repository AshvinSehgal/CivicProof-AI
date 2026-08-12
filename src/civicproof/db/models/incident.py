from sqlalchemy import Column, Integer, String, Float, DateTime, Index, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from geoalchemy2 import Geography
from pgvector.sqlalchemy import Vector
from civicproof.db.base import Base

class Incident(Base):
    __tablename__ = "incidents"
    
    id = Column(Integer, primary_key=True)
    source = Column(String(100), nullable=False)
    external_id = Column(String(200), nullable=False)
    complaint_type = Column(String(500), nullable=False)
    descriptor = Column(String(5000), nullable=False)
    description = Column(String(5000), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    location = Column(Geography(geometry_type='POINT', srid=4326, spatial_index=False), nullable=False)
    embedding = Column(Vector(384), nullable=True)
    category = Column(String(100), nullable=False)
    source_created_at = Column(DateTime(timezone=True), nullable=False)
    raw_payload = Column(JSONB, nullable=False)
    ingested_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_incidents_source_external_id"),
        Index("ix_incidents_location_gist", "location", postgresql_using="gist"),
    )

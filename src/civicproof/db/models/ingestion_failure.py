from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from civicproof.db.base import Base

class IngestionFailure(Base):
    __tablename__ = "ingestion_failures"

    id = Column(Integer, primary_key=True)
    source = Column(String(100), nullable=False, index=True)
    external_id = Column(String(500), nullable=True, index=True)
    stage = Column(String(100), nullable=False)
    error_type = Column(String(200), nullable=False)
    error_message = Column(Text, nullable=False)
    raw_payload = Column(JSONB, nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
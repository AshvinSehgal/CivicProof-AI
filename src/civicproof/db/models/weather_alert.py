
from sqlalchemy import Column, Integer, String, DateTime, Text, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from civicproof.db.base import Base

class WeatherAlert(Base):
    __tablename__ = "weather_alerts"
    
    id = Column(Integer, primary_key=True)
    alert_id = Column(String(500), nullable=False)
    event = Column(String(200), nullable=False, index=True)
    severity = Column(String(50), nullable=True)
    urgency = Column(String(50), nullable=True)
    certainty = Column(String(50), nullable=True)
    headline = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    instruction = Column(Text, nullable=True)
    area_description = Column(Text, nullable=True)
    status = Column(String(50), nullable=True, index=True)
    message_type = Column(String(50), nullable=True)
    category = Column(String(100), nullable=True)
    response = Column(String(100), nullable=True)
    effective_at = Column(DateTime(timezone=True), nullable=True, index=True)
    onset_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    ends_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    geometry = Column(JSONB, nullable=True)
    raw_payload = Column(JSONB, nullable=False)
    first_seen_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    
    __table_args__ = (
        UniqueConstraint("alert_id", name="uq_weather_alerts_alert_id"),
    )
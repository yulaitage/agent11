"""Communication log model"""
from sqlalchemy import Column, String, DateTime, Index
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.sql import func
from app.db.session import Base


class CommLog(Base):
    __tablename__ = "comm_logs"

    id = Column(String, primary_key=True)
    device_id = Column(String, index=True)
    event_type = Column(String)  # comm_loss, comm_restored, fault_detected, fault_cleared
    timestamp = Column(DateTime, index=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_comm_logs_device_timestamp", "device_id", "timestamp"),
        Index("ix_comm_logs_event_type", "event_type"),
    )

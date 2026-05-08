"""Fault record model"""
from sqlalchemy import Column, String, Float, DateTime, Index
from sqlalchemy.sql import func
from app.db.session import Base


class FaultRecord(Base):
    __tablename__ = "fault_records"

    id = Column(String, primary_key=True)  # MongoDB ObjectId as string
    device_id = Column(String, index=True)
    geozone = Column(String, nullable=True, index=True)
    fault_type = Column(String)
    fault_status = Column(String)  # active, resolved, delayed
    detected_at = Column(DateTime, index=True)
    resolved_at = Column(DateTime, nullable=True)
    response_time_hours = Column(Float, nullable=True)
    maintenance_action = Column(String, nullable=True)
    technician = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_fault_records_device_detected", "device_id", "detected_at"),
        Index("ix_fault_records_fault_status", "fault_status"),
    )

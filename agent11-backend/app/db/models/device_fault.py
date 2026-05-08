"""Device Fault model"""
from sqlalchemy import Column, String, BigInteger, DateTime, Index
from app.db.session import Base


class DeviceFault(Base):
    __tablename__ = "devices_fault"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(3), nullable=True)
    start_date = Column(DateTime(3), nullable=True)
    end_date = Column(DateTime(3), nullable=True)
    device_id = Column(BigInteger, nullable=False)
    businessGroupId = Column(String(100), nullable=True)
    businessGroupName = Column(String(100), nullable=True)
    businessGroupIdPath = Column(String(100), nullable=True)
    businessGroupNamePath = Column(String(100), nullable=True)
    fault = Column(String(50), nullable=False)  # FAULT enum, stored as string

    __table_args__ = (
        Index("ix_devices_fault_device_id", "device_id"),
        Index("ix_devices_fault_fault", "fault"),
        Index("ix_devices_fault_start_date", "start_date"),
    )

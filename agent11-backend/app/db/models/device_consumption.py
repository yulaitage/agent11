"""Device Consumption model"""
from sqlalchemy import Column, String, BigInteger, Float, Date, DateTime, Index
from sqlalchemy.sql import func
from app.db.session import Base


class DeviceConsumption(Base):
    __tablename__ = "devices_consumption"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    device_id = Column(BigInteger, nullable=False)
    report_date = Column(Date, nullable=True)
    businessGroupId = Column(String(100), nullable=True)
    businessGroupName = Column(String(100), nullable=True)
    businessGroupIdPath = Column(String(100), nullable=True)
    businessGroupNamePath = Column(String(100), nullable=True)
    value = Column(Float, nullable=True)

    __table_args__ = (
        Index("ix_devices_consumption_device_id", "device_id"),
        Index("ix_devices_consumption_report_date", "report_date"),
    )

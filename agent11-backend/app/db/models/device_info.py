"""Device Info model"""
from sqlalchemy import Column, String, BigInteger, Float, DateTime, Index
from sqlalchemy.sql import func
from app.db.session import Base


class DeviceInfo(Base):
    __tablename__ = "devices_info"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    device_id = Column(String(100), unique=True, nullable=False)
    device_name = Column(String(200), nullable=True)
    device_type = Column(String(50), nullable=True)
    businessGroupId = Column(String(100), nullable=True)
    businessGroupName = Column(String(100), nullable=True)
    businessGroupIdPath = Column(String(100), nullable=True)
    businessGroupNamePath = Column(String(100), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    street_name = Column(String(200), nullable=True)
    wattage = Column(Float, nullable=True)
    rated_power = Column(Float, nullable=True)
    controller_id = Column(String(100), nullable=True)
    lamp_id = Column(String(100), nullable=True)
    brightness = Column(Float, nullable=True)
    status = Column(String(20), nullable=True)
    install_date = Column(DateTime, nullable=True)
    last_maintenance = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_devices_info_device_id", "device_id"),
        Index("ix_devices_info_businessGroupId", "businessGroupId"),
    )

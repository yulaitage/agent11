"""Device Threshold model"""
from sqlalchemy import Column, String, BigInteger, Float, DateTime, ForeignKey, Index
from app.db.session import Base


class DeviceThreshold(Base):
    __tablename__ = "devices_threshold"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    device_id = Column(BigInteger, ForeignKey("devices_info.id"), nullable=False)
    param_name = Column(String(100), nullable=True)
    min_value = Column(Float, nullable=True)
    max_value = Column(Float, nullable=True)
    warning_min = Column(Float, nullable=True)
    warning_max = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_devices_threshold_device_id", "device_id"),
    )

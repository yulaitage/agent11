"""Device model"""
from sqlalchemy import Column, String, Float, Integer, DateTime, Index
from sqlalchemy.sql import func
from app.db.session import Base


class Device(Base):
    __tablename__ = "devices"

    device_id = Column(String, primary_key=True)
    device_type = Column(String, nullable=False)  # streetlight, controller, sensor
    geozone = Column(String, index=True)
    street_name = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    status = Column(String, index=True)  # normal, warning, fault, offline
    fault_types = Column(String, nullable=True)  # JSON array as string
    wattage = Column(Integer, nullable=True)
    rated_power = Column(Float, nullable=True)
    controller_id = Column(String, nullable=True)
    lamp_id = Column(String, nullable=True)
    brightness = Column(Float, nullable=True)
    install_date = Column(DateTime, nullable=True)
    last_maintenance = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_devices_device_type", "device_type"),
        Index("ix_devices_geozone_status", "geozone", "status"),
    )

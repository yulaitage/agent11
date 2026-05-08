"""Reading models - device_readings and energy_readings"""
from sqlalchemy import Column, String, Float, Integer, DateTime, Index, ForeignKey
from sqlalchemy.sql import func
from app.db.session import Base


class DeviceReading(Base):
    __tablename__ = "device_readings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String, ForeignKey("devices.device_id"), index=True)
    timestamp = Column(DateTime, index=True)
    voltage = Column(Float, nullable=True)
    current = Column(Float, nullable=True)
    power = Column(Float, nullable=True)
    power_factor = Column(Float, nullable=True)
    energy_kwh = Column(Float, nullable=True)
    comm_status = Column(String, nullable=True)  # online, offline, comm_lost
    raw_data = Column(String, nullable=True)  # hex string
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_device_readings_device_timestamp", "device_id", "timestamp"),
    )


class EnergyReading(Base):
    __tablename__ = "energy_readings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String, index=True)
    geozone = Column(String, index=True)
    timestamp = Column(DateTime, index=True)
    period = Column(String, nullable=True)  # hour, day, week, month
    energy_kwh = Column(Float)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_energy_readings_device_timestamp", "device_id", "timestamp"),
        Index("ix_energy_readings_geozone_timestamp", "geozone", "timestamp"),
    )

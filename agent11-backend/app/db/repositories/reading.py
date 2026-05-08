"""Reading Repository"""
from typing import Optional
from datetime import datetime

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.reading import DeviceReading, EnergyReading
from app.db.session import get_session


class ReadingRepository:
    """Repository for DeviceReading and EnergyReading models"""

    @classmethod
    async def get_device_readings(
        cls,
        device_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> list[dict]:
        """Get device readings with optional time range"""
        async for session in get_session():
            query = select(DeviceReading).where(DeviceReading.device_id == device_id)

            if start_time:
                query = query.where(DeviceReading.timestamp >= start_time)
            if end_time:
                query = query.where(DeviceReading.timestamp <= end_time)

            query = query.order_by(DeviceReading.timestamp.desc()).limit(limit)

            result = await session.execute(query)
            readings = result.scalars().all()
            return [cls._reading_to_dict(r) for r in readings]

    @classmethod
    async def get_energy_readings(
        cls,
        device_id: Optional[str] = None,
        geozone: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000
    ) -> list[dict]:
        """Get energy readings with optional filters"""
        async for session in get_session():
            query = select(EnergyReading)

            conditions = []
            if device_id:
                conditions.append(EnergyReading.device_id == device_id)
            if geozone:
                conditions.append(EnergyReading.geozone == geozone)
            if start_time:
                conditions.append(EnergyReading.timestamp >= start_time)
            if end_time:
                conditions.append(EnergyReading.timestamp <= end_time)

            if conditions:
                query = query.where(and_(*conditions))

            query = query.order_by(EnergyReading.timestamp.desc()).limit(limit)

            result = await session.execute(query)
            readings = result.scalars().all()
            return [cls._energy_to_dict(r) for r in readings]

    @classmethod
    async def create_device_reading(cls, reading_data: dict) -> dict:
        """Create a device reading"""
        async for session in get_session():
            reading = DeviceReading(**reading_data)
            session.add(reading)
            await session.commit()
            await session.refresh(reading)
            return cls._reading_to_dict(reading)

    @classmethod
    async def create_energy_reading(cls, reading_data: dict) -> dict:
        """Create an energy reading"""
        async for session in get_session():
            reading = EnergyReading(**reading_data)
            session.add(reading)
            await session.commit()
            await session.refresh(reading)
            return cls._energy_to_dict(reading)

    @classmethod
    async def sum_energy(
        cls,
        geozone: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> float:
        """Sum energy consumption"""
        async for session in get_session():
            query = select(func.sum(EnergyReading.energy_kwh))

            conditions = []
            if geozone:
                conditions.append(EnergyReading.geozone == geozone)
            if start_time:
                conditions.append(EnergyReading.timestamp >= start_time)
            if end_time:
                conditions.append(EnergyReading.timestamp <= end_time)

            if conditions:
                query = query.where(and_(*conditions))

            result = await session.execute(query)
            return result.scalar() or 0.0

    @classmethod
    def _reading_to_dict(cls, reading: DeviceReading) -> dict:
        return {
            "id": reading.id,
            "device_id": reading.device_id,
            "timestamp": reading.timestamp,
            "voltage": reading.voltage,
            "current": reading.current,
            "power": reading.power,
            "power_factor": reading.power_factor,
            "energy_kwh": reading.energy_kwh,
            "comm_status": reading.comm_status,
            "raw_data": reading.raw_data,
            "created_at": reading.created_at,
        }

    @classmethod
    def _energy_to_dict(cls, reading: EnergyReading) -> dict:
        return {
            "id": reading.id,
            "device_id": reading.device_id,
            "geozone": reading.geozone,
            "timestamp": reading.timestamp,
            "period": reading.period,
            "energy_kwh": reading.energy_kwh,
            "created_at": reading.created_at,
        }

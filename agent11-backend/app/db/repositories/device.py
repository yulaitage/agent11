"""Device Repository"""
from typing import Optional
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.device import Device
from app.db.session import get_session


class DeviceRepository:
    """Repository for Device model"""

    @classmethod
    async def find_by_id(cls, device_id: str) -> Optional[dict]:
        """Find device by ID"""
        async for session in get_session():
            result = await session.execute(
                select(Device).where(Device.device_id == device_id)
            )
            device = result.scalar_one_or_none()
            if device:
                return cls._to_dict(device)
            return None

    @classmethod
    async def find_all(
        cls,
        geozone: Optional[str] = None,
        status: Optional[str] = None,
        device_type: Optional[str] = None,
        limit: int = 100
    ) -> list[dict]:
        """Find all devices with optional filters"""
        async for session in get_session():
            query = select(Device)

            if geozone:
                query = query.where(Device.geozone == geozone)
            if status:
                query = query.where(Device.status == status)
            if device_type:
                query = query.where(Device.device_type == device_type)

            query = query.limit(limit)

            result = await session.execute(query)
            devices = result.scalars().all()
            return [cls._to_dict(d) for d in devices]

    @classmethod
    async def count(
        cls,
        geozone: Optional[str] = None,
        status: Optional[str] = None
    ) -> int:
        """Count devices with optional filters"""
        async for session in get_session():
            query = select(func.count(Device.device_id))

            if geozone:
                query = query.where(Device.geozone == geozone)
            if status:
                query = query.where(Device.status == status)

            result = await session.execute(query)
            return result.scalar() or 0

    @classmethod
    async def create(cls, device_data: dict) -> dict:
        """Create a new device"""
        async for session in get_session():
            device = Device(**device_data)
            session.add(device)
            await session.commit()
            await session.refresh(device)
            return cls._to_dict(device)

    @classmethod
    async def update(cls, device_id: str, updates: dict) -> Optional[dict]:
        """Update a device"""
        async for session in get_session():
            result = await session.execute(
                select(Device).where(Device.device_id == device_id)
            )
            device = result.scalar_one_or_none()
            if not device:
                return None

            for key, value in updates.items():
                if hasattr(device, key):
                    setattr(device, key, value)

            device.updated_at = datetime.utcnow()
            await session.commit()
            await session.refresh(device)
            return cls._to_dict(device)

    @classmethod
    def _to_dict(cls, device: Device) -> dict:
        """Convert device to dictionary"""
        return {
            "device_id": device.device_id,
            "device_type": device.device_type,
            "geozone": device.geozone,
            "street_name": device.street_name,
            "latitude": device.latitude,
            "longitude": device.longitude,
            "status": device.status,
            "fault_types": device.fault_types,
            "wattage": device.wattage,
            "rated_power": device.rated_power,
            "controller_id": device.controller_id,
            "lamp_id": device.lamp_id,
            "brightness": device.brightness,
            "install_date": device.install_date,
            "last_maintenance": device.last_maintenance,
            "created_at": device.created_at,
            "updated_at": device.updated_at,
        }

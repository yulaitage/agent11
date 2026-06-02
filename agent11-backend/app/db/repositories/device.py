"""Device Repository"""
from typing import Optional
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.device_info import DeviceInfo
from app.db.session import get_session


class DeviceRepository:
    """Repository for DeviceInfo model (devices_info table)"""

    @classmethod
    async def find_by_id(cls, device_id: str) -> Optional[dict]:
        """Find device by ID"""
        async for session in get_session():
            result = await session.execute(
                select(DeviceInfo).where(DeviceInfo.device_id == device_id)
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
        street_name: Optional[str] = None,
        business_group: Optional[str] = None,
        limit: int = 100
    ) -> list[dict]:
        """Find all devices with optional filters"""
        async for session in get_session():
            query = select(DeviceInfo)

            if geozone:
                query = query.where(DeviceInfo.businessGroupNamePath.like(f"%{geozone}%"))
            if status:
                query = query.where(DeviceInfo.status == status)
            if device_type:
                query = query.where(DeviceInfo.device_type == device_type)
            if street_name:
                query = query.where(DeviceInfo.street_name.like(f"%{street_name}%"))
            if business_group:
                query = query.where(DeviceInfo.businessGroupName == business_group)

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
            query = select(func.count(DeviceInfo.device_id))

            if geozone:
                query = query.where(DeviceInfo.businessGroupNamePath.like(f"%{geozone}%"))
            if status:
                query = query.where(DeviceInfo.status == status)

            result = await session.execute(query)
            return result.scalar() or 0

    @classmethod
    async def create(cls, device_data: dict) -> dict:
        """Create a new device"""
        async for session in get_session():
            device = DeviceInfo(**device_data)
            session.add(device)
            await session.commit()
            await session.refresh(device)
            return cls._to_dict(device)

    @classmethod
    async def update(cls, device_id: str, updates: dict) -> Optional[dict]:
        """Update a device"""
        async for session in get_session():
            result = await session.execute(
                select(DeviceInfo).where(DeviceInfo.device_id == device_id)
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
    def _to_dict(cls, device: DeviceInfo) -> dict:
        """Convert device to dictionary"""
        return {
            "device_id": device.device_id,
            "device_name": device.device_name,
            "device_type": device.device_type,
            "businessGroupName": device.businessGroupName,
            "businessGroupNamePath": device.businessGroupNamePath,
            "street_name": device.street_name,
            "latitude": device.latitude,
            "longitude": device.longitude,
            "status": device.status,
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

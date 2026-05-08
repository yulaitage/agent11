"""Device Info Repository"""
from typing import Optional
from sqlalchemy import select
from app.db.models.device_info import DeviceInfo
from app.db.session import get_session


class DeviceInfoRepository:
    """Repository for DeviceInfo model"""

    @classmethod
    async def find_by_id(cls, device_id: int) -> Optional[dict]:
        async for session in get_session():
            result = await session.execute(
                select(DeviceInfo).where(DeviceInfo.id == device_id)
            )
            device = result.scalar_one_or_none()
            return cls._to_dict(device) if device else None

    @classmethod
    async def find_by_device_id(cls, device_id: str) -> Optional[dict]:
        """Find by external device_id string (e.g. SLEC674254)"""
        async for session in get_session():
            result = await session.execute(
                select(DeviceInfo).where(DeviceInfo.device_id == device_id)
            )
            device = result.scalar_one_or_none()
            return cls._to_dict(device) if device else None

    @classmethod
    async def find_all(
        cls,
        business_group_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        async for session in get_session():
            query = select(DeviceInfo)
            if business_group_id:
                query = query.where(DeviceInfo.businessGroupId == business_group_id)
            if status:
                query = query.where(DeviceInfo.status == status)
            query = query.limit(limit)
            result = await session.execute(query)
            devices = result.scalars().all()
            return [cls._to_dict(d) for d in devices]

    @classmethod
    async def count(
        cls,
        business_group_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> int:
        from sqlalchemy import func
        async for session in get_session():
            query = select(func.count(DeviceInfo.id))
            if business_group_id:
                query = query.where(DeviceInfo.businessGroupId == business_group_id)
            if status:
                query = query.where(DeviceInfo.status == status)
            result = await session.execute(query)
            return result.scalar() or 0

    @classmethod
    def _to_dict(cls, device: DeviceInfo) -> dict:
        return {
            "id": device.id,
            "device_id": device.device_id,
            "device_name": device.device_name,
            "device_type": device.device_type,
            "businessGroupId": device.businessGroupId,
            "businessGroupName": device.businessGroupName,
            "businessGroupIdPath": device.businessGroupIdPath,
            "businessGroupNamePath": device.businessGroupNamePath,
            "latitude": device.latitude,
            "longitude": device.longitude,
            "street_name": device.street_name,
            "wattage": device.wattage,
            "rated_power": device.rated_power,
            "controller_id": device.controller_id,
            "lamp_id": device.lamp_id,
            "brightness": device.brightness,
            "status": device.status,
            "install_date": device.install_date,
            "last_maintenance": device.last_maintenance,
            "created_at": device.created_at,
            "updated_at": device.updated_at,
            "deleted_at": device.deleted_at,
        }

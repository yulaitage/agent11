"""Device Fault Repository"""
from typing import Optional
from datetime import datetime
from sqlalchemy import select, and_
from app.db.models.device_fault import DeviceFault
from app.db.session import get_session


class DeviceFaultRepository:
    """Repository for DeviceFault model"""

    @classmethod
    async def find_by_id(cls, fault_id: int) -> Optional[dict]:
        async for session in get_session():
            result = await session.execute(
                select(DeviceFault).where(DeviceFault.id == fault_id)
            )
            fault = result.scalar_one_or_none()
            return cls._to_dict(fault) if fault else None

    @classmethod
    async def find_by_device(
        cls,
        device_id: int,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[dict]:
        async for session in get_session():
            query = select(DeviceFault).where(DeviceFault.device_id == device_id)
            if start_time:
                query = query.where(DeviceFault.start_date >= start_time)
            if end_time:
                query = query.where(DeviceFault.start_date <= end_time)
            query = query.order_by(DeviceFault.start_date.desc()).limit(limit)
            result = await session.execute(query)
            faults = result.scalars().all()
            return [cls._to_dict(f) for f in faults]

    @classmethod
    async def find_by_group(
        cls,
        business_group_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[dict]:
        async for session in get_session():
            query = select(DeviceFault).where(
                DeviceFault.businessGroupId == business_group_id
            )
            if start_time:
                query = query.where(DeviceFault.start_date >= start_time)
            if end_time:
                query = query.where(DeviceFault.start_date <= end_time)
            query = query.order_by(DeviceFault.start_date.desc()).limit(limit)
            result = await session.execute(query)
            faults = result.scalars().all()
            return [cls._to_dict(f) for f in faults]

    @classmethod
    async def find_recent(
        cls,
        limit: int = 50,
        start_time: Optional[datetime] = None,
    ) -> list[dict]:
        """Find recent faults across all devices"""
        async for session in get_session():
            query = select(DeviceFault)
            if start_time:
                query = query.where(DeviceFault.start_date >= start_time)
            query = query.order_by(DeviceFault.start_date.desc()).limit(limit)
            result = await session.execute(query)
            faults = result.scalars().all()
            return [cls._to_dict(f) for f in faults]

    @classmethod
    async def count_by_fault_type(
        cls,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> dict[str, int]:
        """Count faults grouped by fault type"""
        from sqlalchemy import func
        async for session in get_session():
            query = select(
                DeviceFault.fault, func.count(DeviceFault.id)
            )
            if start_time:
                query = query.where(DeviceFault.start_date >= start_time)
            if end_time:
                query = query.where(DeviceFault.start_date <= end_time)
            query = query.group_by(DeviceFault.fault)
            result = await session.execute(query)
            return {row[0]: row[1] for row in result}

    @classmethod
    def _to_dict(cls, fault: DeviceFault) -> dict:
        return {
            "id": fault.id,
            "created_at": fault.created_at,
            "start_date": fault.start_date,
            "end_date": fault.end_date,
            "device_id": fault.device_id,
            "businessGroupId": fault.businessGroupId,
            "businessGroupName": fault.businessGroupName,
            "businessGroupIdPath": fault.businessGroupIdPath,
            "businessGroupNamePath": fault.businessGroupNamePath,
            "fault": fault.fault,
        }

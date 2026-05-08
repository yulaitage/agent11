"""Device Consumption Repository"""
from typing import Optional
from datetime import date
from sqlalchemy import select, func
from app.db.models.device_consumption import DeviceConsumption
from app.db.session import get_session


class DeviceConsumptionRepository:
    """Repository for DeviceConsumption model"""

    @classmethod
    async def find_by_device(
        cls,
        device_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100,
    ) -> list[dict]:
        async for session in get_session():
            query = select(DeviceConsumption).where(
                DeviceConsumption.device_id == device_id
            )
            if start_date:
                query = query.where(DeviceConsumption.report_date >= start_date)
            if end_date:
                query = query.where(DeviceConsumption.report_date <= end_date)
            query = query.order_by(DeviceConsumption.report_date.desc()).limit(limit)
            result = await session.execute(query)
            records = result.scalars().all()
            return [cls._to_dict(r) for r in records]

    @classmethod
    async def find_by_group(
        cls,
        business_group_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100,
    ) -> list[dict]:
        async for session in get_session():
            query = select(DeviceConsumption).where(
                DeviceConsumption.businessGroupId == business_group_id
            )
            if start_date:
                query = query.where(DeviceConsumption.report_date >= start_date)
            if end_date:
                query = query.where(DeviceConsumption.report_date <= end_date)
            query = query.order_by(DeviceConsumption.report_date.desc()).limit(limit)
            result = await session.execute(query)
            records = result.scalars().all()
            return [cls._to_dict(r) for r in records]

    @classmethod
    async def sum_by_group(
        cls,
        business_group_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> float:
        async for session in get_session():
            query = select(func.sum(DeviceConsumption.value)).where(
                DeviceConsumption.businessGroupId == business_group_id
            )
            if start_date:
                query = query.where(DeviceConsumption.report_date >= start_date)
            if end_date:
                query = query.where(DeviceConsumption.report_date <= end_date)
            result = await session.execute(query)
            return result.scalar() or 0.0

    @classmethod
    def _to_dict(cls, record: DeviceConsumption) -> dict:
        return {
            "id": record.id,
            "device_id": record.device_id,
            "report_date": record.report_date,
            "businessGroupId": record.businessGroupId,
            "businessGroupName": record.businessGroupName,
            "businessGroupIdPath": record.businessGroupIdPath,
            "businessGroupNamePath": record.businessGroupNamePath,
            "value": record.value,
        }

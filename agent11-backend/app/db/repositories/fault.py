"""Fault Repository"""
from typing import Optional
from datetime import datetime

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.fault import FaultRecord
from app.db.session import get_session


class FaultRepository:
    """Repository for FaultRecord model"""

    @classmethod
    async def find_by_id(cls, fault_id: str) -> Optional[dict]:
        """Find fault by ID"""
        async for session in get_session():
            result = await session.execute(
                select(FaultRecord).where(FaultRecord.id == fault_id)
            )
            fault = result.scalar_one_or_none()
            if fault:
                return cls._to_dict(fault)
            return None

    @classmethod
    async def find_by_device(
        cls,
        device_id: str,
        status: Optional[str] = None,
        limit: int = 100
    ) -> list[dict]:
        """Find faults by device ID"""
        async for session in get_session():
            query = select(FaultRecord).where(FaultRecord.device_id == device_id)

            if status:
                query = query.where(FaultRecord.fault_status == status)

            query = query.order_by(FaultRecord.detected_at.desc()).limit(limit)

            result = await session.execute(query)
            faults = result.scalars().all()
            return [cls._to_dict(f) for f in faults]

    @classmethod
    async def find_resolved_since(
        cls,
        since: datetime,
        limit: int = 200
    ) -> list[dict]:
        """Find faults resolved after a given timestamp"""
        async for session in get_session():
            query = (
                select(FaultRecord)
                .where(
                    and_(
                        FaultRecord.fault_status == "resolved",
                        FaultRecord.resolved_at >= since,
                    )
                )
                .order_by(FaultRecord.resolved_at.desc())
                .limit(limit)
            )
            result = await session.execute(query)
            return [cls._to_dict(f) for f in result.scalars().all()]

    @classmethod
    async def find_active(
        cls,
        geozone: Optional[str] = None,
        limit: int = 100
    ) -> list[dict]:
        """Find active (unresolved) faults"""
        async for session in get_session():
            query = select(FaultRecord).where(FaultRecord.fault_status == "active")

            if geozone:
                query = query.where(FaultRecord.geozone == geozone)

            query = query.order_by(FaultRecord.detected_at.desc()).limit(limit)

            result = await session.execute(query)
            faults = result.scalars().all()
            return [cls._to_dict(f) for f in faults]

    @classmethod
    async def count_by_status(
        cls,
        geozone: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> dict:
        """Count faults by status"""
        async for session in get_session():
            query = select(
                FaultRecord.fault_status,
                func.count(FaultRecord.id)
            ).group_by(FaultRecord.fault_status)

            conditions = []
            if geozone:
                conditions.append(FaultRecord.geozone == geozone)
            if start_time:
                conditions.append(FaultRecord.detected_at >= start_time)
            if end_time:
                conditions.append(FaultRecord.detected_at <= end_time)

            if conditions:
                query = query.where(and_(*conditions))

            result = await session.execute(query)
            return {row[0]: row[1] for row in result.all()}

    @classmethod
    async def count_by_device(
        cls,
        device_id: str,
        fault_status: str = "resolved"
    ) -> int:
        """Count resolved faults for a device (for risk scoring)"""
        async for session in get_session():
            result = await session.execute(
                select(func.count(FaultRecord.id)).where(
                    and_(
                        FaultRecord.device_id == device_id,
                        FaultRecord.fault_status == fault_status
                    )
                )
            )
            return result.scalar() or 0

    @classmethod
    async def create(cls, fault_data: dict) -> dict:
        """Create a new fault record"""
        async for session in get_session():
            fault = FaultRecord(**fault_data)
            session.add(fault)
            await session.commit()
            await session.refresh(fault)
            return cls._to_dict(fault)

    @classmethod
    async def resolve(cls, fault_id: str, resolution: dict) -> Optional[dict]:
        """Resolve a fault"""
        async for session in get_session():
            result = await session.execute(
                select(FaultRecord).where(FaultRecord.id == fault_id)
            )
            fault = result.scalar_one_or_none()
            if not fault:
                return None

            fault.fault_status = "resolved"
            fault.resolved_at = datetime.utcnow()
            if "response_time_hours" in resolution:
                fault.response_time_hours = resolution["response_time_hours"]
            if "maintenance_action" in resolution:
                fault.maintenance_action = resolution["maintenance_action"]
            if "technician" in resolution:
                fault.technician = resolution["technician"]
            if "notes" in resolution:
                fault.notes = resolution["notes"]

            await session.commit()
            await session.refresh(fault)
            return cls._to_dict(fault)

    @classmethod
    def _to_dict(cls, fault: FaultRecord) -> dict:
        return {
            "id": fault.id,
            "device_id": fault.device_id,
            "geozone": fault.geozone,
            "fault_type": fault.fault_type,
            "fault_status": fault.fault_status,
            "detected_at": fault.detected_at,
            "resolved_at": fault.resolved_at,
            "response_time_hours": fault.response_time_hours,
            "maintenance_action": fault.maintenance_action,
            "technician": fault.technician,
            "notes": fault.notes,
            "created_at": fault.created_at,
        }

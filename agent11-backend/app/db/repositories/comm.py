"""Communication Log Repository"""
from typing import Optional
from datetime import datetime

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.comm import CommLog
from app.db.session import get_session


class CommRepository:
    """Repository for CommLog model"""

    @classmethod
    async def find_by_device(
        cls,
        device_id: str,
        event_type: Optional[str] = None,
        limit: int = 100
    ) -> list[dict]:
        """Find comm logs by device ID"""
        async for session in get_session():
            query = select(CommLog).where(CommLog.device_id == device_id)

            if event_type:
                query = query.where(CommLog.event_type == event_type)

            query = query.order_by(CommLog.timestamp.desc()).limit(limit)

            result = await session.execute(query)
            logs = result.scalars().all()
            return [cls._to_dict(l) for l in logs]

    @classmethod
    async def find_by_event_type(
        cls,
        event_type: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> list[dict]:
        """Find comm logs by event type"""
        async for session in get_session():
            query = select(CommLog).where(CommLog.event_type == event_type)

            if start_time:
                query = query.where(CommLog.timestamp >= start_time)
            if end_time:
                query = query.where(CommLog.timestamp <= end_time)

            query = query.order_by(CommLog.timestamp.desc()).limit(limit)

            result = await session.execute(query)
            logs = result.scalars().all()
            return [cls._to_dict(l) for l in logs]

    @classmethod
    async def get_recent_comm_loss_devices(
        cls,
        limit: int = 20
    ) -> list[str]:
        """Get devices with recent comm_loss events"""
        async for session in get_session():
            result = await session.execute(
                select(CommLog.device_id)
                .where(CommLog.event_type == "comm_loss")
                .order_by(CommLog.timestamp.desc())
                .limit(limit)
            )
            # Get unique device IDs
            device_ids = list(set(row[0] for row in result.all()))
            return device_ids[:limit]

    @classmethod
    async def create(cls, log_data: dict) -> dict:
        """Create a new comm log"""
        async for session in get_session():
            log = CommLog(**log_data)
            session.add(log)
            await session.commit()
            await session.refresh(log)
            return cls._to_dict(log)

    @classmethod
    def _to_dict(cls, log: CommLog) -> dict:
        return {
            "id": log.id,
            "device_id": log.device_id,
            "event_type": log.event_type,
            "timestamp": log.timestamp,
            "details": log.details,
            "created_at": log.created_at,
        }

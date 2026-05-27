"""API Call Log repository"""
from typing import Any
from datetime import datetime
import uuid

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.api_call_log import APICallLog
from app.db.session import get_session


class APICallLogRepository:
    """Repository for API call log entries"""

    @classmethod
    async def create(cls, log_data: dict) -> dict:
        """Create a new API call log entry"""
        async for session in get_session():
            log_data["id"] = log_data.get("id", str(uuid.uuid4()))
            log = APICallLog(**log_data)
            session.add(log)
            await session.commit()
            await session.refresh(log)
            return cls._to_dict(log)

    @classmethod
    async def get_recent(
        cls,
        limit: int = 50,
        offset: int = 0,
        status: int | None = None,
        method: str | None = None,
        path_contains: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple[list[dict], int]:
        """Get recent logs with optional filters, returns (logs, total_count)"""
        async for session in get_session():
            conditions = []
            if status is not None:
                conditions.append(APICallLog.response_status == status)
            if method:
                conditions.append(APICallLog.method == method.upper())
            if path_contains:
                conditions.append(APICallLog.path.ilike(f"%{path_contains}%"))
            if start_date:
                conditions.append(APICallLog.timestamp >= start_date)
            if end_date:
                conditions.append(APICallLog.timestamp <= end_date)

            where_clause = and_(*conditions) if conditions else True

            # Count total
            count_query = select(func.count(APICallLog.id)).where(where_clause)
            count_result = await session.execute(count_query)
            total = count_result.scalar() or 0

            # Fetch logs
            query = (
                select(APICallLog)
                .where(where_clause)
                .order_by(APICallLog.timestamp.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(query)
            logs = result.scalars().all()
            return [cls._to_dict(log) for log in logs], int(total)

    @classmethod
    async def get_stats(cls) -> dict:
        """Get summary statistics"""
        async for session in get_session():
            # Total count
            total_result = await session.execute(select(func.count(APICallLog.id)))
            total = total_result.scalar() or 0

            # Avg duration
            avg_result = await session.execute(
                select(func.avg(APICallLog.duration_ms)).where(APICallLog.duration_ms.isnot(None))
            )
            avg_duration = avg_result.scalar() or 0.0

            # Count by status
            status_counts: dict[int, int] = {}
            status_result = await session.execute(
                select(APICallLog.response_status, func.count(APICallLog.id))
                .group_by(APICallLog.response_status)
            )
            for row in status_result:
                status_counts[row[0]] = row[1]

            # Count by method
            method_counts: dict[str, int] = {}
            method_result = await session.execute(
                select(APICallLog.method, func.count(APICallLog.id))
                .group_by(APICallLog.method)
            )
            for row in method_result:
                method_counts[row[0]] = row[1]

            return {
                "total": total,
                "avg_duration_ms": round(float(avg_duration), 2),
                "by_status": status_counts,
                "by_method": method_counts,
            }

    @classmethod
    def _to_dict(cls, log: APICallLog) -> dict[str, Any]:
        return {
            "id": log.id,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            "method": log.method,
            "path": log.path,
            "request_body": log.request_body,
            "response_status": log.response_status,
            "response_body": log.response_body,
            "duration_ms": round(log.duration_ms, 2),
            "user_id": log.user_id,
            "thread_id": log.thread_id,
            "ip_address": log.ip_address,
            "user_agent": log.user_agent,
        }
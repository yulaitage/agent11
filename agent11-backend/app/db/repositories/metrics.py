"""Metrics Repository"""
from typing import Optional
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.metrics import MetricsHistory, SkillHealth
from app.db.session import get_session


class MetricsRepository:
    """Repository for MetricsHistory and SkillHealth models"""

    @classmethod
    async def save_metrics(cls, metrics_data: dict) -> dict:
        """Save metrics snapshot"""
        async for session in get_session():
            metrics = MetricsHistory(**metrics_data)
            session.add(metrics)
            await session.commit()
            await session.refresh(metrics)
            return cls._metrics_to_dict(metrics)

    @classmethod
    async def get_recent_metrics(
        cls,
        limit: int = 100
    ) -> list[dict]:
        """Get recent metrics snapshots"""
        async for session in get_session():
            query = (
                select(MetricsHistory)
                .order_by(MetricsHistory.timestamp.desc())
                .limit(limit)
            )
            result = await session.execute(query)
            metrics_list = result.scalars().all()
            return [cls._metrics_to_dict(m) for m in metrics_list]

    @classmethod
    async def get_skill_health(cls, skill: str) -> Optional[dict]:
        """Get skill health status"""
        async for session in get_session():
            result = await session.execute(
                select(SkillHealth).where(SkillHealth.skill == skill)
            )
            health = result.scalar_one_or_none()
            if health:
                return cls._health_to_dict(health)
            return None

    @classmethod
    async def upsert_skill_health(cls, skill: str, health_data: dict) -> dict:
        """Update or insert skill health"""
        async for session in get_session():
            result = await session.execute(
                select(SkillHealth).where(SkillHealth.skill == skill)
            )
            health = result.scalar_one_or_none()

            if health:
                for key, value in health_data.items():
                    if hasattr(health, key):
                        setattr(health, key, value)
                health.updated_at = datetime.utcnow()
            else:
                health_data["skill"] = skill
                health = SkillHealth(**health_data)
                session.add(health)

            await session.commit()
            await session.refresh(health)
            return cls._health_to_dict(health)

    @classmethod
    async def get_all_skill_health(cls) -> list[dict]:
        """Get all skill health statuses"""
        async for session in get_session():
            result = await session.execute(select(SkillHealth))
            health_list = result.scalars().all()
            return [cls._health_to_dict(h) for h in health_list]

    @classmethod
    def _metrics_to_dict(cls, metrics: MetricsHistory) -> dict:
        return {
            "id": metrics.id,
            "timestamp": metrics.timestamp,
            "skills": metrics.skills,
            "knowledge": metrics.knowledge,
            "memory": metrics.memory,
            "system": metrics.system,
        }

    @classmethod
    def _health_to_dict(cls, health: SkillHealth) -> dict:
        return {
            "skill": health.skill,
            "status": health.status,
            "success_rate": health.success_rate,
            "avg_latency_ms": health.avg_latency_ms,
            "error_rate": health.error_rate,
            "issues": health.issues,
            "recommendations": health.recommendations,
            "updated_at": health.updated_at,
        }

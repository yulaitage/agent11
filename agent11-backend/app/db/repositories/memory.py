"""Memory Repository"""
from typing import Optional
from datetime import datetime

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.memory import (
    MemoryInfraDevices,
    MemoryInfraGeozones,
    MemoryInfraSystems,
    MemoryInfraProtocols,
    MemoryConversEpisodes,
    MemoryConversSessions,
    MemoryConversPreferences,
    MemoryLearningPatterns,
    MemoryLearningRelationships,
    MemoryLearningInsights,
)
from app.db.session import get_session


# Mapping of room names to model classes
MEMORY_MODELS = {
    "memory_infra_devices": MemoryInfraDevices,
    "memory_infra_geozones": MemoryInfraGeozones,
    "memory_infra_systems": MemoryInfraSystems,
    "memory_infra_protocols": MemoryInfraProtocols,
    "memory_convers_episodes": MemoryConversEpisodes,
    "memory_convers_sessions": MemoryConversSessions,
    "memory_convers_preferences": MemoryConversPreferences,
    "memory_learning_patterns": MemoryLearningPatterns,
    "memory_learning_relationships": MemoryLearningRelationships,
    "memory_learning_insights": MemoryLearningInsights,
}


class MemoryRepository:
    """Repository for Memory Palace models"""

    @classmethod
    async def remember(
        cls,
        room: str,
        entity_id: str,
        data: dict,
        source: Optional[str] = None,
        confidence: float = 0.5
    ) -> dict:
        """Store a memory for an entity"""
        model_class = MEMORY_MODELS.get(room)
        if not model_class:
            raise ValueError(f"Unknown memory room: {room}")

        # Add metadata to data
        data["_source"] = source
        data["_confidence"] = confidence

        async for session in get_session():
            memory = model_class(
                id=f"{entity_id}_{datetime.utcnow().timestamp()}",
                entity_id=entity_id,
                data=data
            )
            session.add(memory)
            await session.commit()
            await session.refresh(memory)
            return cls._to_dict(memory)

    @classmethod
    async def recall(
        cls,
        room: str,
        entity_id: str
    ) -> Optional[dict]:
        """Recall memory for an entity"""
        model_class = MEMORY_MODELS.get(room)
        if not model_class:
            raise ValueError(f"Unknown memory room: {room}")

        async for session in get_session():
            result = await session.execute(
                select(model_class)
                .where(
                    and_(
                        model_class.entity_id == entity_id,
                        model_class.archived == False
                    )
                )
                .order_by(model_class.created_at.desc())
                .limit(1)
            )
            memory = result.scalar_one_or_none()
            if memory:
                return cls._to_dict(memory)
            return None

    @classmethod
    async def search(
        cls,
        room: str,
        query: str,
        limit: int = 10
    ) -> list[dict]:
        """Search memories by entity_id pattern"""
        model_class = MEMORY_MODELS.get(room)
        if not model_class:
            raise ValueError(f"Unknown memory room: {room}")

        async for session in get_session():
            result = await session.execute(
                select(model_class)
                .where(
                    and_(
                        model_class.entity_id.ilike(f"%{query}%"),
                        model_class.archived == False
                    )
                )
                .limit(limit)
            )
            memories = result.scalars().all()
            return [cls._to_dict(m) for m in memories]

    @classmethod
    async def find_similar(
        cls,
        room: str,
        data_pattern: dict,
        limit: int = 10
    ) -> list[dict]:
        """Find memories with similar data patterns"""
        model_class = MEMORY_MODELS.get(room)
        if not model_class:
            raise ValueError(f"Unknown memory room: {room}")

        async for session in get_session():
            # For simplicity, search by entity_id prefix
            entity_id = data_pattern.get("entity_id", "")
            if entity_id:
                result = await session.execute(
                    select(model_class)
                    .where(
                        and_(
                            model_class.entity_id.ilike(f"{entity_id}%"),
                            model_class.archived == False
                        )
                    )
                    .limit(limit)
                )
                memories = result.scalars().all()
                return [cls._to_dict(m) for m in memories]
            return []

    @classmethod
    async def archive(cls, room: str, entity_id: str) -> bool:
        """Archive memories for an entity"""
        model_class = MEMORY_MODELS.get(room)
        if not model_class:
            raise ValueError(f"Unknown memory room: {room}")

        async for session in get_session():
            result = await session.execute(
                select(model_class)
                .where(model_class.entity_id == entity_id)
            )
            memories = result.scalars().all()

            for memory in memories:
                memory.archived = True
                memory.archived_at = datetime.utcnow()

            await session.commit()
            return True

    @classmethod
    async def cleanup_old_memories(
        cls,
        room: str,
        max_age_days: int = 365
    ) -> int:
        """Archive memories older than max_age_days"""
        model_class = MEMORY_MODELS.get(room)
        if not model_class:
            raise ValueError(f"Unknown memory room: {room}")

        cutoff = datetime.utcnow() - datetime.timedelta(days=max_age_days)

        async for session in get_session():
            result = await session.execute(
                select(model_class)
                .where(
                    and_(
                        model_class.created_at < cutoff,
                        model_class.archived == False
                    )
                )
            )
            memories = result.scalars().all()

            count = 0
            for memory in memories:
                memory.archived = True
                memory.archived_at = datetime.utcnow()
                count += 1

            await session.commit()
            return count

    @classmethod
    async def find_episodes(cls, limit: int = 20) -> list[dict]:
        """Find conversation episodes"""
        async for session in get_session():
            result = await session.execute(
                select(MemoryConversEpisodes)
                .where(MemoryConversEpisodes.archived == False)
                .order_by(MemoryConversEpisodes.created_at.desc())
                .limit(limit)
            )
            episodes = result.scalars().all()
            return [
                {
                    "entity_id": e.id,
                    "summary": e.summary,
                    "learned_facts": e.learned_facts,
                    "created_at": e.created_at
                }
                for e in episodes
            ]

    @classmethod
    def _to_dict(cls, memory) -> dict:
        """Convert memory to dict"""
        return {
            "id": memory.id,
            "entity_id": memory.entity_id,
            "data": memory.data,
            "created_at": memory.created_at,
            "updated_at": memory.updated_at,
            "archived": memory.archived,
            "archived_at": memory.archived_at,
        }

"""记忆 API"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any

router = APIRouter()


@router.get("/context")
async def get_memory_context(query: str, entity_ids: str | None = None):
    """获取记忆上下文"""
    from app.memory.palace import MemoryPalace

    palace = MemoryPalace.get_instance()

    ids = entity_ids.split(",") if entity_ids else None
    context = await palace.build_context(query, ids)

    return {"context": context}


@router.get("/stats")
async def get_memory_stats():
    """获取记忆统计"""
    from app.memory.palace import MemoryPalace

    palace = MemoryPalace.get_instance()
    stats = await palace.get_stats()

    return stats


@router.get("/entities/{entity_id}")
async def get_entity_memory(entity_id: str, room: str = "room_devices"):
    """获取实体记忆"""
    from app.memory.palace import MemoryPalace

    palace = MemoryPalace.get_instance()
    memory = await palace.recall(room, entity_id)

    return {"entity_id": entity_id, "room": room, "memory": memory}


@router.post("/entities/{entity_id}")
async def update_entity_memory(
    entity_id: str,
    room: str,
    fact: str,
    source: str = "api"
):
    """更新实体记忆"""
    from app.memory.palace import MemoryPalace

    palace = MemoryPalace.get_instance()
    success = await palace.remember(room, entity_id, fact, source)

    return {"success": success}


@router.get("/patterns")
async def search_patterns(query: str, limit: int = 10):
    """搜索模式"""
    from app.memory.palace import MemoryPalace

    palace = MemoryPalace.get_instance()

    # 直接查询 ChromaDB
    from app.knowledge.chromadb import ChromaDBClient
    chroma = ChromaDBClient.get_instance()

    results = await chroma.query(
        collection_name="memory_learning_patterns",
        query=query,
        n_results=limit
    )

    return {"patterns": results}


@router.get("/episodes")
async def list_episodes(limit: int = 20):
    """列出事件记忆 - 使用 PostgreSQL memory_convers_episodes 表"""
    from app.db.repositories.memory import MemoryRepository

    episodes = await MemoryRepository.find_episodes(limit=limit)

    return {
        "episodes": [
            {
                "entity_id": e.get("entity_id"),
                "summary": e.get("summary", {}),
                "created_at": e.get("created_at")
            }
            for e in episodes
        ]
    }

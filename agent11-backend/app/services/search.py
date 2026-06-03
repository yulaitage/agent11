"""跨会话全文搜索服务 - Feature 4"""
import structlog
from typing import Any
from sqlalchemy import text
from app.db.session import get_session

logger = structlog.get_logger()


class SearchService:
    """跨会话全文搜索，支持 sessions/chats/memories 的联合检索"""

    @classmethod
    async def search_all(
        cls,
        query: str,
        limit: int = 10,
        user_id: str | None = None,
    ) -> list[dict]:
        """跨所有数据源搜索"""
        results = []
        results.extend(await cls._search_chats(query, limit, user_id))
        results.extend(await cls._search_memories(query, limit))
        results.extend(await cls._search_knowledge(query, limit))
        # 按相关性排序
        results.sort(key=lambda r: r.get("score", 0), reverse=True)
        return results[:limit]

    @classmethod
    async def _search_chats(
        cls, query: str, limit: int, user_id: str | None = None
    ) -> list[dict]:
        """搜索聊天记录中的消息内容"""
        try:
            async for session in get_session():
                sql = """
                    SELECT c.id as chat_id, c.title,
                           m->>'content' as content,
                           m->>'role' as role,
                           (m->>'timestamp')::timestamp as ts
                    FROM chats c
                    CROSS JOIN LATERAL jsonb_array_elements(c.messages) AS m
                    WHERE m->>'content' ILIKE :q
                    ORDER BY ts DESC
                    LIMIT :lim
                """
                result = await session.execute(
                    text(sql), {"q": f"%{query}%", "lim": limit}
                )
                rows = result.fetchall()
                return [
                    {
                        "type": "chat",
                        "chat_id": r[0],
                        "title": r[1],
                        "content": r[2][:300] if r[2] else "",
                        "role": r[3],
                        "timestamp": str(r[4]) if r[4] else "",
                        "score": 0.8,
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.warning("search_chats_failed", error=str(e))
            return []

    @classmethod
    async def _search_memories(cls, query: str, limit: int) -> list[dict]:
        """搜索记忆表"""
        memory_tables = [
            "memory_infra_devices",
            "memory_convers_episodes",
            "memory_learning_patterns",
        ]
        results = []
        try:
            async for session in get_session():
                for tbl in memory_tables:
                    sql = f"""
                        SELECT entity_id, data, created_at
                        FROM "{tbl}"
                        WHERE archived = false
                          AND data::text ILIKE :q
                        ORDER BY created_at DESC
                        LIMIT :lim
                    """
                    try:
                        result = await session.execute(
                            text(sql), {"q": f"%{query}%", "lim": limit}
                        )
                        for r in result.fetchall():
                            data_str = str(r[1])[:300] if r[1] else ""
                            results.append({
                                "type": "memory",
                                "room": tbl,
                                "entity_id": r[0],
                                "content": data_str,
                                "timestamp": str(r[2]) if r[2] else "",
                                "score": 0.7,
                            })
                    except Exception:
                        continue
        except Exception as e:
            logger.warning("search_memories_failed", error=str(e))
        return results

    @classmethod
    async def _search_knowledge(cls, query: str, limit: int) -> list[dict]:
        """搜索知识库"""
        try:
            from app.knowledge.manager import KnowledgeManager
            km = KnowledgeManager()
            results = await km.search(query, limit=limit)
            return [
                {
                    "type": "knowledge",
                    "filename": r.get("filename", ""),
                    "content": r.get("content", "")[:300],
                    "score": r.get("score", 0.6),
                    "timestamp": "",
                }
                for r in results
            ]
        except Exception as e:
            logger.warning("search_knowledge_failed", error=str(e))
            return []

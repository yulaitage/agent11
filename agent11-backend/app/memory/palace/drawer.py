"""Drawer - 记忆抽屉操作"""
from datetime import datetime
from typing import Any
import structlog

from app.memory.palace.rooms import Room, get_room
from app.db.repositories.memory import MemoryRepository

logger = structlog.get_logger()


class Drawer:
    """
    记忆抽屉 - 对特定房间中特定实体的记忆操作
    """

    def __init__(self, room: Room, entity_id: str):
        self.room = room
        self.entity_id = entity_id

    async def store(self, content: dict) -> str:
        """
        存储记忆
        """
        try:
            await MemoryRepository.remember(
                room=self.room.collection_name,
                entity_id=self.entity_id,
                data=content,
                source="system",
                confidence=0.8
            )
        except Exception as e:
            logger.warning("memory_store_failed", error=str(e))

        return self.entity_id

    async def retrieve(self, query: str | None = None, limit: int = 5) -> dict | list[dict]:
        """
        检索记忆
        """
        if query:
            # 向量搜索
            try:
                from app.knowledge.chromadb import ChromaDBClient

                chroma = ChromaDBClient.get_instance()
                results = await chroma.query(
                    collection_name=self.room.chroma_collection,
                    query=query,
                    n_results=limit,
                    where={"entity_id": self.entity_id}
                )

                if results and results.get("ids"):
                    # 获取完整文档
                    docs = []
                    for idx, ids in enumerate(results["ids"]):
                        doc = await MemoryRepository.recall(self.room.collection_name, ids[0])
                        if doc:
                            docs.append(doc)
                    return docs

            except Exception as e:
                logger.warning("vector_search_failed", error=str(e))

        # 直接获取
        doc = await MemoryRepository.recall(self.room.collection_name, self.entity_id)
        return doc if doc else {}

    async def add_fact(
        self,
        fact: str,
        source: str,
        confidence: float = 0.8
    ) -> bool:
        """
        添加新事实到记忆
        """
        try:
            await MemoryRepository.remember(
                room=self.room.collection_name,
                entity_id=self.entity_id,
                data={"fact": fact, "source": source, "learned_at": datetime.utcnow().isoformat()},
                source=source,
                confidence=confidence
            )
            return True
        except Exception as e:
            logger.warning("memory_add_fact_failed", error=str(e))
            return False

    async def update_fact(
        self,
        fact_index: int,
        updates: dict
    ) -> bool:
        """
        更新特定事实
        """
        # PostgreSQL 版本需要重新设计，这里简化处理
        return False

    async def get_history(self, limit: int = 10) -> list[dict]:
        """
        获取记忆历史
        """
        doc = await MemoryRepository.recall(self.room.collection_name, self.entity_id)

        if not doc:
            return []

        # 从 data 字段中提取 fact，兼容新旧格式
        data = doc.get("data", {})
        if isinstance(data, dict):
            fact_text = data.get("fact", "")
            if fact_text:
                return [{"fact": fact_text, "source": data.get("source", ""), "learned_at": data.get("learned_at", "")}]
        return []

    async def archive(self) -> bool:
        """
        归档记忆（软删除）
        """
        try:
            await MemoryRepository.archive(self.room.collection_name, self.entity_id)
            return True
        except Exception as e:
            logger.warning("memory_archive_failed", error=str(e))
            return False

    async def _index_to_vector(self, content: dict) -> bool:
        """索引内容到向量数据库"""
        from app.knowledge.chromadb import ChromaDBClient

        try:
            chroma = ChromaDBClient.get_instance()

            # 提取可索引的文本
            texts = self._extract_indexable_text(content)

            if texts:
                await chroma.add_knowledge(
                    documents=texts,
                    metadata={
                        "entity_id": self.entity_id,
                        "room": self.room.name
                    }
                )

            return True

        except Exception as e:
            logger.error("vector_indexing_failed", error=str(e))
            return False

    def _extract_indexable_text(self, content: dict) -> list[str]:
        """提取可索引的文本"""
        texts = []

        # 提取字符串字段
        for key, value in content.items():
            if isinstance(value, str) and len(value) > 10:
                texts.append(f"{key}: {value}")
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and len(item) > 10:
                        texts.append(item)
                    elif isinstance(item, dict):
                        texts.extend(self._extract_indexable_text(item))

        return texts[:10]  # 最多 10 个文本片段


# 便捷函数
async def remember(
    room_name: str,
    entity_id: str,
    fact: str,
    source: str,
    confidence: float = 0.8
) -> bool:
    """
    便捷函数：添加记忆
    """
    room = get_room(room_name)
    if not room:
        raise ValueError(f"Unknown room: {room_name}")

    drawer = Drawer(room, entity_id)
    return await drawer.add_fact(fact, source, confidence)


async def recall(
    room_name: str,
    entity_id: str,
    query: str | None = None
) -> dict | list[dict]:
    """
    便捷函数：回忆记忆
    """
    room = get_room(room_name)
    if not room:
        raise ValueError(f"Unknown room: {room_name}")

    drawer = Drawer(room, entity_id)
    return await drawer.retrieve(query)

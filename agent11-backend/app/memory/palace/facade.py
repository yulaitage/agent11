"""Memory Palace Facade - 统一访问接口"""
from __future__ import annotations

import structlog
from typing import Any, Optional

from app.memory.palace.wings import Wing, get_wing, list_wings, WINGS_REGISTRY
from app.memory.palace.rooms import Room, get_room, list_rooms, ROOMS_REGISTRY
from app.memory.palace.drawer import Drawer, remember, recall
from app.memory.palace.tunnels import Tunnel
from app.db.repositories.memory import MemoryRepository

logger = structlog.get_logger()

# Global palace instance
_palace: Optional["MemoryPalace"] = None


class MemoryPalace:
    """
    记忆宫殿 - 统一访问接口

    使用示例:
        palace = MemoryPalace.get_instance()

        # 添加记忆
        await palace.remember("room_devices", "LIGHT-55-A001", "该设备容易在雨天闪烁")

        # 检索记忆
        context = await palace.recall("room_devices", "LIGHT-55-A001")

        # 跨房间检索
        patterns = await palace.find_related_patterns("LIGHT-55-A001")
    """

    @classmethod
    async def initialize(cls):
        """初始化记忆宫殿"""
        global _palace
        _palace = cls()

        # 确保所有集合存在
        await cls._ensure_collections()

        return _palace

    @classmethod
    def get_instance(cls) -> "MemoryPalace":
        """获取单例实例"""
        global _palace
        if _palace is None:
            _palace = cls()
        return _palace

    @classmethod
    async def _ensure_collections(cls):
        """确保必要的集合存在（PostgreSQL 自动创建表）"""
        # PostgreSQL 使用 SQLAlchemy 自动建表，这里只需要记录日志
        for room in ROOMS_REGISTRY.values():
            logger.info("memory_table_check", room=room.name, collection=room.collection_name)

    # ==================== Wings ====================

    def list_wings(self) -> list[dict]:
        """列出所有翼"""
        return [
            {
                "name": w.name,
                "description": w.description,
                "room_count": len(ROOMS_REGISTRY)  # 简化
            }
            for w in list_wings()
        ]

    def get_wing(self, name: str) -> dict | None:
        """获取翼信息"""
        wing = get_wing(name)
        if not wing:
            return None

        rooms = [r for r in list_rooms() if r.wing_name == name]

        return {
            "name": wing.name,
            "description": wing.description,
            "rooms": [
                {
                    "name": r.name,
                    "description": r.description
                }
                for r in rooms
            ]
        }

    # ==================== Rooms ====================

    def list_rooms(self) -> list[dict]:
        """列出所有房间"""
        return [
            {
                "name": r.name,
                "wing": r.wing_name,
                "description": r.description
            }
            for r in list_rooms()
        ]

    def get_room(self, name: str) -> dict | None:
        """获取房间信息"""
        room = get_room(name)
        if not room:
            return None

        return {
            "name": room.name,
            "wing": room.wing_name,
            "description": room.description,
            "collection": room.collection_name
        }

    # ==================== Drawer Operations ====================

    async def remember(
        self,
        room_name: str,
        entity_id: str,
        fact: str,
        source: str,
        confidence: float = 0.8
    ) -> bool:
        """
        存储记忆

        Args:
            room_name: 房间名 (如 "room_devices")
            entity_id: 实体 ID (如设备 ID)
            fact: 事实内容
            source: 来源 (如 "conversation_123", "observation")
            confidence: 置信度
        """
        try:
            return await remember(room_name, entity_id, fact, source, confidence)
        except Exception as e:
            logger.error("remember_failed", room=room_name, entity=entity_id, error=str(e))
            return False

    async def recall(
        self,
        room_name: str,
        entity_id: str,
        query: str | None = None
    ) -> dict | list[dict]:
        """
        检索记忆

        Args:
            room_name: 房间名
            entity_id: 实体 ID
            query: 可选的查询字符串（用于向量搜索）
        """
        try:
            return await recall(room_name, entity_id, query)
        except Exception as e:
            logger.error("recall_failed", room=room_name, entity=entity_id, error=str(e))
            return {}

    async def store(
        self,
        room_name: str,
        entity_id: str,
        content: dict
    ) -> str:
        """
        存储完整内容到房间
        """
        room = get_room(room_name)
        if not room:
            raise ValueError(f"Unknown room: {room_name}")

        drawer = Drawer(room, entity_id)
        return await drawer.store(content)

    # ==================== Tunnel Operations ====================

    async def find_related_patterns(self, device_id: str) -> list[dict]:
        """查找设备相关模式"""
        return await Tunnel.find_device_related_patterns(device_id)

    async def find_similar_episodes(
        self,
        issue: str,
        device_id: str | None = None
    ) -> list[dict]:
        """查找相似事件"""
        return await Tunnel.find_similar_episodes(issue, device_id)

    async def find_related_entities(
        self,
        entity_id: str,
        relationship_type: str | None = None
    ) -> list[dict]:
        """查找相关实体"""
        return await Tunnel.find_related_entities(entity_id, relationship_type)

    async def build_context(
        self,
        query: str,
        entity_ids: list[str] | None = None
    ) -> str:
        """
        为查询构建上下文

        从多个房间聚合相关信息，用于注入到 Agent prompt
        """
        return await Tunnel.build_context_for_query(query, entity_ids)

    # ==================== Stats ====================

    async def get_stats(self) -> dict:
        """获取记忆统计"""
        stats = {
            "entity_count": 0,
            "pattern_count": 0,
            "episode_count": 0,
            "preference_count": 0,
            "rooms": {}
        }

        # PostgreSQL 不需要预创建集合，直接返回默认统计
        # 实际统计通过 MemoryRepository 查询
        for room in ROOMS_REGISTRY.values():
            stats["rooms"][room.name] = 0

        return stats

    # ==================== Maintenance ====================

    async def cleanup(self) -> dict:
        """清理过期记忆"""
        from app.harness.autonomous.memory_optimizer import MemoryOptimizer

        optimizer = MemoryOptimizer()
        results = await optimizer.run_weekly_optimization()

        return results

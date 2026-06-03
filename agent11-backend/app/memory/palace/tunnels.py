"""Tunnels - 跨房间检索"""
from typing import Any
import structlog

from app.memory.palace.rooms import get_room, Room
from app.memory.palace.drawer import Drawer
from app.db.repositories.memory import MemoryRepository

logger = structlog.get_logger()


class Tunnel:
    """
    走廊 - 连接不同房间的路径，用于跨领域检索
    """

    @staticmethod
    async def find_device_related_patterns(device_id: str) -> list[dict]:
        """
        查找与设备相关的所有模式
        从 room_patterns 穿过 room_devices
        """
        # 1. 获取设备信息
        device_room = get_room("room_devices")
        device_drawer = Drawer(device_room, device_id)
        device = await device_drawer.retrieve()

        if not device:
            return []

        # 2. 获取区域
        geozone = device.get("relationship_context", {}).get("geozone")
        device_type = device.get("device_type", "")

        # 3. 在模式房间搜索相关模式
        from app.knowledge.chromadb import ChromaDBClient

        try:
            chroma = ChromaDBClient.get_instance()

            query_text = f"{device_type} {geozone or ''} 故障 模式"
            results = await chroma.query(
                collection_name="memory_learning_patterns",
                query=query_text,
                n_results=10
            )

            if results and results.get("ids"):
                patterns = []

                for ids in results["ids"]:
                    for doc_id in ids:
                        pattern = await MemoryRepository.recall("memory_learning_patterns", doc_id)
                        if pattern:
                            patterns.append(pattern)

                return patterns

        except Exception as e:
            logger.error("pattern_search_failed", error=str(e))

        return []

    @staticmethod
    async def find_similar_episodes(
        current_issue: str,
        device_id: str | None = None,
        limit: int = 5
    ) -> list[dict]:
        """
        查找与当前问题相似的历史事件
        """
        # 1. 获取设备已知问题
        known_issues = []

        if device_id:
            device_room = get_room("room_devices")
            device_drawer = Drawer(device_room, device_id)
            device = await device_drawer.retrieve()

            if device:
                known_issues = device.get("known_issues", [])

        # 2. 在事件中搜索
        from app.knowledge.chromadb import ChromaDBClient

        try:
            chroma = ChromaDBClient.get_instance()

            combined_query = f"{current_issue} {' '.join(known_issues)}"
            results = await chroma.query(
                collection_name="memory_convers_episodes",
                query=combined_query,
                n_results=limit
            )

            if results and results.get("ids"):
                episodes = []

                for ids in results["ids"]:
                    for doc_id in ids:
                        episode = await MemoryRepository.recall("memory_convers_episodes", doc_id)
                        if episode:
                            episodes.append(episode)

                return episodes

        except Exception as e:
            logger.error("episode_search_failed", error=str(e))

        return []

    @staticmethod
    async def find_related_entities(
        entity_id: str,
        relationship_type: str | None = None,
        limit: int = 10
    ) -> list[dict]:
        """
        查找相关实体
        """
        # PostgreSQL 版本需要重新实现关系查询
        # 这里简化处理
        return []

    @staticmethod
    async def build_context_for_query(
        query: str,
        entity_ids: list[str] | None = None
    ) -> str:
        """
        为查询构建上下文字符串
        从多个房间聚合相关信息
        """
        context_parts = []

        # 1. 从相关实体获取信息
        if entity_ids:
            for entity_id in entity_ids[:5]:  # 最多 5 个实体
                for room_name in ["room_devices", "room_patterns", "room_episodes"]:
                    room = get_room(room_name)
                    if room:
                        drawer = Drawer(room, entity_id)
                        entity = await drawer.retrieve()

                        if entity and isinstance(entity, dict):
                            context_parts.append(f"## {room_name.replace('room_', '')}: {entity_id}")
                            # 提取存储的事实内容
                            fact = entity.get("fact") or (entity.get("data") or {}).get("fact", "")
                            if fact:
                                context_parts.append(f"- 事实: {fact}")

        # 2. 使用 Tunnels 搜索相关模式
        if entity_ids and entity_ids[0]:
            patterns = await Tunnel.find_device_related_patterns(entity_ids[0])
            if patterns:
                context_parts.append("## 相关故障模式")
                for pattern in patterns[:3]:
                    context_parts.append(f"- {pattern.get('data', {}).get('trigger', 'N/A')}: {pattern.get('data', {}).get('manifestation', '')}")

        # 3. 使用 Tunnels 搜索相似事件
        episodes = await Tunnel.find_similar_episodes(query, entity_ids[0] if entity_ids else None)
        if episodes:
            context_parts.append("## 相似历史事件")
            for episode in episodes[:2]:
                context_parts.append(f"- {episode.get('data', {}).get('query', 'N/A')}: {episode.get('data', {}).get('findings', '')[:100] if episode.get('data', {}).get('findings') else ''}")

        return "\n".join(context_parts) if context_parts else ""

"""Rooms - 记忆房间定义"""
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.memory.palace.wings import Wing


@dataclass
class Room:
    """记忆房间"""
    wing_name: str
    name: str
    description: str
    collection_name: str  # MongoDB collection name
    chroma_collection: str  # ChromaDB collection name

    @property
    def full_name(self) -> str:
        return f"{self.wing_name}_{self.name}"


# 房间定义
class room_devices(Room):
    """设备记忆"""
    wing_name = "wing_infra"
    name = "room_devices"
    description = "设备相关记忆"
    collection_name = "memory_infra_devices"
    chroma_collection = "memory_infra_devices"


class room_geozones(Room):
    """区域记忆"""
    wing_name = "wing_infra"
    name = "room_geozones"
    description = "地理区域相关记忆"
    collection_name = "memory_infra_geozones"
    chroma_collection = "memory_infra_geozones"


class room_systems(Room):
    """系统拓扑记忆"""
    wing_name = "wing_infra"
    name = "room_systems"
    description = "系统拓扑和关系"
    collection_name = "memory_infra_systems"
    chroma_collection = "memory_infra_systems"


class room_protocols(Room):
    """协议知识"""
    wing_name = "wing_infra"
    name = "room_protocols"
    description = "设备协议知识"
    collection_name = "memory_infra_protocols"
    chroma_collection = "memory_infra_protocols"


class room_episodes(Room):
    """重要事件"""
    wing_name = "wing_convers"
    name = "room_episodes"
    description = "重要历史交互事件"
    collection_name = "memory_convers_episodes"
    chroma_collection = "memory_convers_episodes"


class room_sessions(Room):
    """会话摘要"""
    wing_name = "wing_convers"
    name = "room_sessions"
    description = "会话摘要"
    collection_name = "memory_convers_sessions"
    chroma_collection = "memory_convers_sessions"


class room_preferences(Room):
    """用户偏好"""
    wing_name = "wing_convers"
    name = "room_preferences"
    description = "用户偏好记忆"
    collection_name = "memory_convers_preferences"
    chroma_collection = "memory_convers_preferences"


class room_patterns(Room):
    """故障模式"""
    wing_name = "wing_learning"
    name = "room_patterns"
    description = "从历史数据中学习的故障模式"
    collection_name = "memory_learning_patterns"
    chroma_collection = "memory_learning_patterns"


class room_relationships(Room):
    """实体关系"""
    wing_name = "wing_learning"
    name = "room_relationships"
    description = "实体间关系"
    collection_name = "memory_learning_relationships"
    chroma_collection = "memory_learning_relationships"


class room_insights(Room):
    """洞察"""
    wing_name = "wing_learning"
    name = "room_insights"
    description = "Agent 洞察和学习"
    collection_name = "memory_learning_insights"
    chroma_collection = "memory_learning_insights"


# 房间注册表
ROOMS_REGISTRY: dict[str, Room] = {
    "room_devices": room_devices,
    "room_geozones": room_geozones,
    "room_systems": room_systems,
    "room_protocols": room_protocols,
    "room_episodes": room_episodes,
    "room_sessions": room_sessions,
    "room_preferences": room_preferences,
    "room_patterns": room_patterns,
    "room_relationships": room_relationships,
    "room_insights": room_insights,
}


def get_room(name: str) -> Room | None:
    return ROOMS_REGISTRY.get(name)


def list_rooms() -> list[Room]:
    return list(ROOMS_REGISTRY.values())


def get_rooms_by_wing(wing_name: str) -> list[Room]:
    return [r for r in ROOMS_REGISTRY.values() if r.wing_name == wing_name]

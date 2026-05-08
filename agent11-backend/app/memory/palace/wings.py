"""Wings - 记忆翼定义"""
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.memory.palace.rooms import Room


@dataclass
class Wing:
    """记忆翼"""
    name: str
    description: str
    rooms: list["Room"] = field(default_factory=list)


# 翼定义
class wing_infra(Wing):
    """基础设施知识"""
    name = "wing_infra"
    description = "智能基础设施相关的持久知识"
    rooms = []  # 动态填充


class wing_convers(Wing):
    """对话记忆"""
    name = "wing_convers"
    description = "历史交互和会话"
    rooms = []


class wing_learning(Wing):
    """学习记忆"""
    name = "wing_learning"
    description = "Agent 学习到的知识"
    rooms = []


class wing_user(Wing):
    """用户记忆"""
    name = "wing_user"
    description = "用户相关记忆"
    rooms = []


class wing_meta(Wing):
    """元记忆"""
    name = "wing_meta"
    description = "系统元数据"
    rooms = []


# 翼注册表
WINGS_REGISTRY: dict[str, Wing] = {
    "wing_infra": wing_infra,
    "wing_convers": wing_convers,
    "wing_learning": wing_learning,
    "wing_user": wing_user,
    "wing_meta": wing_meta,
}


def get_wing(name: str) -> Wing | None:
    return WINGS_REGISTRY.get(name)


def list_wings() -> list[Wing]:
    return list(WINGS_REGISTRY.values())

"""对话上下文数据类"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConversationContext:
    """对话上下文"""
    user_id: str
    chat_id: str
    skill: str | None
    query: str
    history: list[dict] = field(default_factory=list)
    context: dict = field(default_factory=dict)

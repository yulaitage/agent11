"""基础技能类"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from app.agent.context import ConversationContext


class BaseSkill(ABC):
    """技能基类"""

    name: str = "base"

    @abstractmethod
    async def execute(
        self,
        llm: Any,
        query: str,
        context: ConversationContext
    ) -> dict[str, Any]:
        """
        执行技能

        Args:
            llm: LLM 服务
            query: 用户查询
            context: 对话上下文

        Returns:
            dict: 包含 answer, reasoning_chain, confidence, map_data, data
        """
        pass

    async def _build_reasoning_chain(
        self,
        steps: list[tuple[str, str, str]]
    ) -> list[dict]:
        """
        构建推理链

        Args:
            steps: [(action, observation, conclusion), ...]
        """
        return [
            {
                "step": i + 1,
                "action": action,
                "observation": observation,
                "conclusion": conclusion
            }
            for i, (action, observation, conclusion) in enumerate(steps)
        ]

    def _extract_entities(self, query: str) -> list[str]:
        """从查询中提取实体（简化实现）"""
        import re

        # 提取设备 ID 模式
        device_patterns = [
            r'LIGHT-\d+-[A-Z]\d+',  # LIGHT-55-A001
            r'CTRL-\d+-[A-Z]\d+',   # CTRL-55-A001
            r'\d+区',                # 55区
        ]

        entities = []
        for pattern in device_patterns:
            matches = re.findall(pattern, query)
            entities.extend(matches)

        return entities

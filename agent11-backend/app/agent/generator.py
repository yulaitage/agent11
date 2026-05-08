"""Agent Generator - 基于 LangGraph 的核心 Agent"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal, Any, Optional
from datetime import datetime
import structlog

from app.config import get_settings
from app.services.llm import LLMService
from app.memory.palace import MemoryPalace
from app.agent.prompt import SYSTEM_PROMPT, SKILL_ROUTER_PROMPT
from app.agent.skills import SkillRegistry
from app.agent.context import ConversationContext
from app.knowledge.manager import KnowledgeManager

logger = structlog.get_logger()

# Global agent instance
_agent: Optional["AgentGenerator"] = None


@dataclass
class AgentResponse:
    """Agent 响应"""
    answer: str
    skill: str
    reasoning_chain: list[dict] = field(default_factory=list)
    confidence: float | None = None
    map_data: dict | None = None
    data: dict | None = None
    sources: list[str] = field(default_factory=list)
    latency_ms: float = 0.0


class AgentGenerator:
    """
    Agent Generator - 基于 LangGraph 的智能 Agent

    架构:
    1. Skill Router - 路由到合适技能
    2. Skill Executor - 执行具体技能
    3. Memory Integration - 记忆集成
    4. Response Formatter - 响应格式化
    """

    @classmethod
    def get_instance(cls) -> "AgentGenerator":
        if _agent is None:
            raise RuntimeError("AgentGenerator not initialized")
        return _agent

    @classmethod
    async def initialize(cls):
        """初始化 Agent"""
        global _agent
        _agent = cls(
            llm=LLMService.get_instance(),
            skill_registry=SkillRegistry(),
            memory=MemoryPalace.get_instance()
        )
        return _agent

    def __init__(
        self,
        llm: LLMService,
        skill_registry: "SkillRegistry",
        memory: MemoryPalace
    ):
        self.llm = llm
        self.skill_registry = skill_registry
        self.memory = memory
        self.knowledge = KnowledgeManager()

        # 技能指标
        self._skill_metrics: dict[str, dict] = {}

    async def execute(
        self,
        skill: str | None,
        query: str,
        context: dict | None = None,
        user_id: str | None = None,
        chat_id: str | None = None
    ) -> AgentResponse:
        """
        执行 Agent 对话

        Args:
            skill: 技能名称（可选，自动检测）
            query: 用户查询
            context: 额外上下文
            user_id: 用户 ID
            chat_id: 聊天 ID

        Returns:
            AgentResponse
        """
        start_time = time.time()

        # skill 为 None 时使用自动路由

        try:
            # 1. 路由到具体技能
            if skill == "auto" or skill is None:
                skill = await self._route_skill(query)

            logger.info("agent_executing", skill=skill, query=query[:100])

            # 2. 构建上下文（包含记忆）
            ctx = ConversationContext(
                user_id=user_id or "anonymous",
                chat_id=chat_id or "default",
                skill=skill,
                query=query,
                context=context or {}
            )

            # 3. 注入记忆上下文
            prepend_context = await self._build_prepend_context(query, ctx)
            system_prompt = SYSTEM_PROMPT + prepend_context

            # 4. 执行技能
            skill_func = self.skill_registry.get(skill)
            if not skill_func:
                raise ValueError(f"Unknown skill: {skill}")

            response = await skill_func(self.llm, query, ctx)

            # 5. 格式化响应
            formatted = await self._format_response(skill, response, ctx)

            # 6. 学习（存储记忆）
            await self._learn_from_interaction(ctx, formatted)

            # 7. 记录指标
            latency_ms = (time.time() - start_time) * 1000
            self._record_skill_metric(skill, success=True, latency_ms=latency_ms)

            formatted.latency_ms = latency_ms
            return formatted

        except Exception as e:
            logger.error("agent_execution_failed", skill=skill, error=str(e))
            self._record_skill_metric(skill or "unknown", success=False, latency_ms=(time.time() - start_time) * 1000)

            return AgentResponse(
                answer=f"抱歉，处理您的请求时遇到错误: {str(e)}",
                skill=skill or "unknown",
                confidence=0.0
            )

    async def _route_skill(self, query: str) -> str:
        """技能路由 - 完全由 LLM 根据语义判断"""
        try:
            response = await self.llm.invoke(
                SKILL_ROUTER_PROMPT + f"\n\n用户查询: {query}\n\n请只返回技能名称:",
                system=False,
                temperature=0.1
            )

            # 解析响应
            skill = response.strip().lower()

            # 验证技能名称
            valid_skills = ["query", "troubleshoot", "prediction", "maintenance_report", "flexible_report", "general_chat"]
            if skill not in valid_skills:
                skill = "general_chat"  # 默认走灵活回复

            return skill

        except Exception as e:
            logger.warning("skill_routing_failed", error=str(e))
            return "general_chat"  # 兜底走灵活回复

    async def _build_prepend_context(self, query: str, ctx: ConversationContext) -> str:
        """构建前置上下文（包含记忆和知识库）"""
        context_parts = []

        # 1. 记忆上下文
        try:
            memory_context = await self.memory.build_context(query)
            if memory_context:
                context_parts.append(memory_context)
        except Exception as e:
            logger.warning("memory_context_failed", error=str(e))

        # 2. 知识库语义搜索
        try:
            kb_results = await self.knowledge.search(query, limit=3)
            if kb_results:
                kb_context = "\n\n".join([
                    f"## 相关知识: {r['filename']}\n{r['content'][:500]}"
                    for r in kb_results
                ])
                context_parts.append(kb_context)
        except Exception as e:
            logger.warning("kb_search_failed", error=str(e))

        # 3. 相关实体
        entity_ids = ctx.context.get("entity_ids", [])
        if entity_ids:
            for entity_id in entity_ids[:3]:
                try:
                    entity_data = await self.memory.recall("room_devices", entity_id)
                    if entity_data:
                        context_parts.append(f"## 相关设备: {entity_id}\n{str(entity_data)[:500]}")
                except:
                    pass

        if context_parts:
            return "\n\n---\n\n# 记忆上下文\n" + "\n\n".join(context_parts)

        return ""

    async def _format_response(
        self,
        skill: str,
        raw_response: dict,
        ctx: ConversationContext
    ) -> AgentResponse:
        """格式化响应"""
        return AgentResponse(
            answer=raw_response.get("answer", ""),
            skill=skill,
            reasoning_chain=raw_response.get("reasoning_chain", []),
            confidence=raw_response.get("confidence"),
            map_data=raw_response.get("map_data"),
            data=raw_response.get("data"),
            sources=raw_response.get("sources", [])
        )

    async def _learn_from_interaction(
        self,
        ctx: ConversationContext,
        response: AgentResponse
    ):
        """从交互中学习"""
        try:
            # 从响应中提取实体并存储
            if ctx.context.get("entity_ids"):
                for entity_id in ctx.context["entity_ids"]:
                    # 检查是否有新的问题被提及
                    if "故障" in response.answer or "问题" in response.answer:
                        await self.memory.remember(
                            "room_devices",
                            entity_id,
                            f"在对话中被提及: {response.answer[:200]}",
                            source=f"conversation_{ctx.chat_id}",
                            confidence=0.5
                        )

            # 保存重要内容到 summaries 文件夹
            await self._maybe_save_to_summaries(ctx, response)

        except Exception as e:
            logger.warning("learning_failed", error=str(e))

    async def _maybe_save_to_summaries(
        self,
        ctx: ConversationContext,
        response: AgentResponse
    ):
        """检测重要内容并保存到 summaries 文件夹"""
        important_keywords = [
            "建议", "维护", "计划", "故障分析", "预测", "总结",
            "报告", "结论", "方案", "步骤", "原因", "分析"
        ]

        # 检测是否为重要内容
        is_important = False
        trigger_reason = ""

        # 1. 检查关键词
        for keyword in important_keywords:
            if keyword in response.answer:
                is_important = True
                trigger_reason = f"包含关键词: {keyword}"
                break

        # 2. 检查特定技能（这些技能通常产生重要内容）
        important_skills = ["maintenance_report", "prediction", "flexible_report"]
        if response.skill in important_skills:
            is_important = True
            trigger_reason = f"技能: {response.skill}"

        # 3. 检查回答长度（较长的回答更可能是重要内容）
        if len(response.answer) > 500:
            is_important = True
            trigger_reason = f"内容长度: {len(response.answer)} 字符"

        if not is_important:
            return

        try:
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_skill = response.skill.replace("_", "-")
            filename = f"summaries/{timestamp}_{safe_skill}.md"

            # 构建 markdown 内容
            content = f"""# {ctx.skill.upper()} - {datetime.now().strftime("%Y-%m-%d %H:%M")}

## 用户问题
{ctx.query}

## Agent 回答
{response.answer}

---
*保存原因: {trigger_reason}*
*对话ID: {ctx.chat_id}*
"""

            # 保存到知识库
            success = await self.knowledge.save_file(filename, content)
            if success:
                logger.info("saved_to_summaries", filename=filename, reason=trigger_reason)
            else:
                logger.warning("failed_to_save_summaries", filename=filename)

        except Exception as e:
            logger.warning("save_to_summaries_failed", error=str(e))

    def _record_skill_metric(self, skill: str, success: bool, latency_ms: float):
        """记录技能指标"""
        if skill not in self._skill_metrics:
            self._skill_metrics[skill] = {
                "total_calls": 0,
                "success_count": 0,
                "failure_count": 0,
                "total_latency_ms": 0,
                "latencies": []
            }

        m = self._skill_metrics[skill]
        m["total_calls"] += 1

        if success:
            m["success_count"] += 1
        else:
            m["failure_count"] += 1

        m["total_latency_ms"] += latency_ms
        m["latencies"].append(latency_ms)

        # 保持最近 100 条延迟记录
        if len(m["latencies"]) > 100:
            m["latencies"] = m["latencies"][-100:]

    def get_skill_metrics(self) -> dict[str, Any]:
        """获取技能指标"""
        from app.harness.loop_operator.metrics import SkillMetric

        result = {}
        for skill, m in self._skill_metrics.items():
            latencies = m["latencies"]
            latencies.sort()

            result[skill] = SkillMetric(
                name=skill,
                total_calls=m["total_calls"],
                success_count=m["success_count"],
                failure_count=m["failure_count"],
                avg_latency_ms=m["total_latency_ms"] / max(m["total_calls"], 1),
                p95_latency_ms=latencies[int(len(latencies) * 0.95)] if latencies else 0
            )

        return result

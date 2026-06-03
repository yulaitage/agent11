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

            # Feature 2: Skill 自我改进 — 分析失败原因，尝试改进技能
            if skill and skill not in ("general_chat", "unknown", None):
                try:
                    await self._improve_skill_on_failure(skill, query, str(e))
                except Exception as improve_err:
                    logger.warning("skill_improvement_failed", error=str(improve_err))

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
        """从交互中学习 - 使用 LLM 判断哪些信息值得存储"""
        try:
            # 1. 用 LLM 分析交互内容，提取值得记忆的信息
            memory_items = await self._extract_memory_items(ctx, response)

            # 2. 存储提取出的记忆
            for item in memory_items:
                room = item.get("room", "room_devices")
                entity_id = item.get("entity_id", ctx.chat_id or "default")
                fact = item.get("fact", "")
                source = item.get("source", f"conversation_{ctx.chat_id}")
                if fact and len(fact) > 10:
                    # 先检查是否已有类似记忆
                    existing = await self.memory.recall(room, entity_id, query=fact[:50])
                    if existing and isinstance(existing, dict):
                        existing_fact = existing.get("fact", "")
                        if existing_fact and self._is_similar(fact, existing_fact):
                            continue  # 跳过重复
                    await self.memory.remember(
                        room, entity_id, fact,
                        source=source,
                        confidence=item.get("confidence", 0.7)
                    )

            # 3. LLM 判断是否保存为摘要
            if await self._llm_judge_important(ctx, response):
                await self._save_summary(ctx, response)

        except Exception as e:
            logger.warning("learning_failed", error=str(e))

    async def _extract_memory_items(
        self,
        ctx: ConversationContext,
        response: AgentResponse
    ) -> list[dict]:
        """使用 LLM 从交互中提取值得记忆的信息"""
        prompt = (
            "分析以下对话，提取值得长期记住的信息。\n\n"
            f"用户问题: {ctx.query}\n"
            f"Agent回答: {response.answer[:500]}\n"
            f"使用的技能: {response.skill}\n\n"
            "输出 JSON 数组，每项包含:\n"
            "  room: 记忆房间 (room_devices/room_episodes/room_patterns/room_preferences)\n"
            "  entity_id: 关联的设备ID或实体名\n"
            "  fact: 要记住的事实（中文，简洁完整的一句话）\n"
            "  source: 来源\n"
            "  confidence: 0-1 置信度\n\n"
            "规则：\n"
            "- 仅提取有价值的信息（设备状态、故障模式、用户偏好、重要结论）\n"
            "- 如果本次对话没有值得长期记住的内容，返回 []\n"
            "- 不要重复已存在的常识\n"
            "- 事实要具体、可验证，不要模糊概括\n"
            "仅输出 JSON 数组，不要解释。"
        )
        try:
            resp = await self.llm.invoke(prompt, system=False, temperature=0.1)
            import re, json
            cleaned = re.sub(r'<think>.*?</think>', '', resp, flags=re.DOTALL)
            cleaned = re.sub(r'```json|```', '', cleaned).strip()
            start = cleaned.find('[')
            end = cleaned.rfind(']')
            if start != -1 and end != -1:
                items = json.loads(cleaned[start:end+1])
                return items if isinstance(items, list) else []
        except Exception as e:
            logger.warning("memory_extraction_failed", error=str(e))
        return []

    def _is_similar(self, fact1: str, fact2: str) -> bool:
        """简单判断两条事实是否相似（基于关键词重叠）"""
        if not fact1 or not fact2:
            return False
        words1 = set(fact1.replace("，", " ").replace("。", " ").replace("、", " ").split()[:10])
        words2 = set(fact2.replace("，", " ").replace("。", " ").replace("、", " ").split()[:10])
        if not words1 or not words2:
            return False
        overlap = len(words1 & words2)
        return overlap / min(len(words1), len(words2)) > 0.6

    async def _llm_judge_important(self, ctx: ConversationContext, response: AgentResponse) -> bool:
        """用 LLM 判断本次交互是否值得保存为摘要"""
        prompt = (
            "判断以下对话内容是否值得长期保存为知识库摘要。\n"
            "值得保存的场景：故障分析结论、维护方案、预测结果、数据报告、操作步骤\n"
            "不值得保存的场景：简单问候、普通查询、日常闲聊\n\n"
            f"用户: {ctx.query[:200]}\n"
            f"Agent: {response.answer[:300]}\n"
            f"技能: {response.skill}\n\n"
            "只回复 YES 或 NO。"
        )
        try:
            resp = await self.llm.invoke(prompt, system=False, temperature=0.1)
            return resp.strip().upper().startswith("YES")
        except Exception:
            return False

    async def _save_summary(self, ctx: ConversationContext, response: AgentResponse):
        """保存交互摘要到知识库"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_skill = response.skill.replace("_", "-")
            filename = f"summaries/{timestamp}_{safe_skill}.md"

            content = f"""# {ctx.skill.upper()} - {datetime.now().strftime("%Y-%m-%d %H:%M")}

## 用户问题
{ctx.query}

## Agent 回答
{response.answer}

---
*对话ID: {ctx.chat_id}*
"""
            success = await self.knowledge.save_file(filename, content)
            if success:
                logger.info("saved_summary", filename=filename)
        except Exception as e:
            logger.warning("save_summary_failed", error=str(e))

    async def _improve_skill_on_failure(self, skill: str, query: str, error: str):
        """Feature 2: 技能执行失败时，用 LLM 分析原因并尝试改进技能"""
        metadata = self.skill_registry.get_metadata(skill)
        if not metadata or metadata.get("is_builtin"):
            return  # 内置技能不自动修改

        prompt = (
            "一个技能执行时发生了错误。分析原因并给出改进方案。\n\n"
            f"技能名称: {skill}\n"
            f"用户查询: {query}\n"
            f"错误信息: {error}\n\n"
            "请分析：\n"
            "1. 错误的原因是什么\n"
            "2. 技能代码需要如何修复（给出具体的代码修改）\n"
            "3. 修复后的完整技能代码\n\n"
            "输出 JSON 格式：\n"
            '{"analysis": "...", "fix_description": "...", "fixed_code": "..."}\n'
            "如果无法确定修复方案，返回 {\"analysis\": \"无法确定\"}"
        )
        try:
            resp = await self.llm.invoke(prompt, system=False, temperature=0.2)

            import re, json
            cleaned = re.sub(r'<think>.*?</think>', '', resp, flags=re.DOTALL)
            cleaned = re.sub(r'```json|```', '', cleaned).strip()
            start = cleaned.find('{')
            end = cleaned.rfind('}')
            if start != -1 and end != -1:
                result = json.loads(cleaned[start:end+1])
                if result.get("fixed_code") and result.get("analysis") != "无法确定":
                    success = self.skill_registry.reload_skill(skill)
                    if success:
                        logger.info("skill_improved", skill=skill,
                                    fix=result.get("fix_description", ""))
        except Exception as e:
            logger.warning("skill_improvement_analysis_failed", error=str(e))

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

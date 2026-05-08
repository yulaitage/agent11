"""优化决策器 - Optimization Decider"""
from dataclasses import dataclass
from typing import Literal
from app.harness.loop_operator.metrics import AgentMetrics, Trend
from app.harness.loop_operator.trend_analyzer import TrendAnalyzer


@dataclass
class Action:
    """优化行动"""
    type: Literal[
        "switch_llm_fallback",
        "adjust_temperature",
        "trigger_knowledge_update",
        "add_knowledge",
        "human_review",
        "monitor",
        "scale_up",
        "rebuild_index"
    ]
    priority: Literal["low", "medium", "high", "critical"]
    skill: str | None = None
    reason: str = ""
    details: dict | None = None


@dataclass
class ActionResult:
    success: bool
    message: str
    error: str | None = None


class OptimizationDecider:
    """
    优化决策器 - 基于趋势和指标决定行动
    """

    def __init__(self):
        self.trend_analyzer = TrendAnalyzer()

    async def decide(
        self,
        trends: list[Trend],
        metrics: AgentMetrics
    ) -> list[Action]:
        """
        基于趋势和当前指标决定优化行动
        """
        actions = []

        for trend in trends:
            if trend.type == "success_rate_decline":
                action = self._handle_success_rate_decline(trend, metrics)
                if action:
                    actions.append(action)

            elif trend.type == "latency_increase":
                action = self._handle_latency_increase(trend, metrics)
                if action:
                    actions.append(action)

            elif trend.type == "error_rate_increase":
                action = self._handle_error_rate_increase(trend, metrics)
                if action:
                    actions.append(action)

            elif trend.type == "low_knowledge_hit_rate":
                actions.append(Action(
                    type="trigger_knowledge_update",
                    priority="high",
                    reason="知识库命中率低"
                ))

        # 系统级检查
        system_actions = self._check_system_health(metrics)
        actions.extend(system_actions)

        # 按优先级排序
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        actions.sort(key=lambda a: priority_order.get(a.priority, 3))

        return actions

    def _handle_success_rate_decline(
        self,
        trend: Trend,
        metrics: AgentMetrics
    ) -> Action | None:
        """处理成功率下降"""
        skill_metric = metrics.skill_metrics.get(trend.skill)

        if not skill_metric:
            return None

        if skill_metric.failure_count < 5:
            return Action(
                type="monitor",
                priority="low",
                skill=trend.skill,
                reason=f"失败次数 {skill_metric.failure_count} < 5，继续观察"
            )

        # 分析失败模式
        dominant_error = self._get_dominant_error(skill_metric.error_types)

        if dominant_error in ["timeout", "connection"]:
            return Action(
                type="switch_llm_fallback",
                priority="high",
                skill=trend.skill,
                reason="LLM 连接问题，切换到备用模型"
            )

        elif dominant_error == "knowledge_gap":
            return Action(
                type="add_knowledge",
                priority="medium",
                skill=trend.skill,
                reason="知识库缺少相关领域知识"
            )

        else:
            return Action(
                type="human_review",
                priority="high",
                skill=trend.skill,
                reason="需要人工审查失败案例"
            )

    def _handle_latency_increase(
        self,
        trend: Trend,
        metrics: AgentMetrics
    ) -> Action | None:
        """处理延迟增加"""
        if trend.severity == "critical":
            return Action(
                type="switch_llm_fallback",
                priority="critical",
                skill=trend.skill,
                reason="延迟严重超时，切换模型"
            )

        return Action(
            type="adjust_temperature",
            priority="medium",
            skill=trend.skill,
            reason="调整 LLM 温度参数以加快响应",
            details={"temperature": 0.5}
        )

    def _handle_error_rate_increase(
        self,
        trend: Trend,
        metrics: AgentMetrics
    ) -> Action | None:
        """处理错误率增加"""
        return Action(
            type="human_review",
            priority="critical",
            skill=trend.skill,
            reason=f"错误率 {trend.current_value:.2%} 超过阈值"
        )

    def _check_system_health(self, metrics: AgentMetrics) -> list[Action]:
        """检查系统整体健康状态"""
        actions = []

        # LLM 健康检查
        if metrics.system_metrics.llm_status == "down":
            actions.append(Action(
                type="switch_llm_fallback",
                priority="critical",
                reason="LLM 服务不可用"
            ))

        elif metrics.system_metrics.llm_status == "degraded":
            actions.append(Action(
                type="switch_llm_fallback",
                priority="high",
                reason="LLM 服务降级"
            ))

        # ChromaDB 检查
        if metrics.system_metrics.chromadb_status == "down":
            actions.append(Action(
                type="rebuild_index",
                priority="critical",
                reason="ChromaDB 不可用"
            ))

        return actions

    def _get_dominant_error(self, error_types: dict[str, int]) -> str | None:
        """获取主要错误类型"""
        if not error_types:
            return None

        return max(error_types.items(), key=lambda x: x[1])[0]

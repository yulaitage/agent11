"""技能监控 - Skill Monitor"""
import structlog
from dataclasses import dataclass
from typing import Literal
from datetime import datetime

from app.db.repositories.metrics import MetricsRepository

logger = structlog.get_logger()


@dataclass
class HealthStatus:
    """技能健康状态"""
    skill: str
    status: Literal["healthy", "degraded", "critical"]
    success_rate: float
    avg_latency_ms: float
    error_rate: float
    issues: list[str]
    recommendations: list[str]


class SkillMonitor:
    """
    技能监控循环 - 监控技能健康状态
    """

    # 健康阈值
    HEALTHY_SUCCESS_RATE = 0.9
    DEGRADED_SUCCESS_RATE = 0.7
    HEALTHY_LATENCY_MS = 10000
    DEGRADED_LATENCY_MS = 20000

    async def run_health_check(self) -> dict[str, HealthStatus]:
        """
        执行技能健康检查
        """
        logger.info("running_skill_health_check")

        from app.agent.generator import AgentGenerator

        agent = AgentGenerator.get_instance()
        skill_metrics = agent.get_skill_metrics()

        health_statuses = {}

        for skill_name, metrics in skill_metrics.items():
            status = self._evaluate_health(skill_name, metrics)
            health_statuses[skill_name] = status

            if status.status in ["degraded", "critical"]:
                logger.warning(
                    "skill_health_degraded",
                    skill=skill_name,
                    status=status.status,
                    success_rate=status.success_rate
                )

            # 存储健康状态
            await self._store_health_status(skill_name, status)

        # 触发恢复（如果需要）
        await self._trigger_recovery_if_needed(health_statuses)

        return health_statuses

    def _evaluate_health(
        self,
        skill: str,
        metrics
    ) -> HealthStatus:
        """评估技能健康状态"""
        success_rate = metrics.success_rate if hasattr(metrics, 'success_rate') else 1.0
        avg_latency = metrics.avg_latency_ms if hasattr(metrics, 'avg_latency_ms') else 0
        error_rate = 1 - success_rate

        issues = []
        recommendations = []

        # 评估状态
        if success_rate < self.DEGRADED_SUCCESS_RATE or avg_latency > self.DEGRADED_LATENCY_MS:
            status = "critical"
            issues.append(f"成功率过低: {success_rate:.2%}" if success_rate < self.DEGRADED_SUCCESS_RATE else "")
            issues.append(f"延迟过高: {avg_latency}ms" if avg_latency > self.DEGRADED_LATENCY_MS else "")
            recommendations.append("立即检查 LLM 连接和知识库")
            recommendations.append("考虑切换到备用模型")

        elif success_rate < self.HEALTHY_SUCCESS_RATE or avg_latency > self.HEALTHY_LATENCY_MS:
            status = "degraded"
            issues.append(f"成功率下降: {success_rate:.2%}" if success_rate < self.HEALTHY_SUCCESS_RATE else "")
            issues.append(f"延迟增加: {avg_latency}ms" if avg_latency > self.HEALTHY_LATENCY_MS else "")
            recommendations.append("监控趋势")
            recommendations.append("如持续下降，考虑优化")

        else:
            status = "healthy"

        issues = [i for i in issues if i]
        recommendations = recommendations[:2]  # 最多 2 条建议

        return HealthStatus(
            skill=skill,
            status=status,
            success_rate=success_rate,
            avg_latency_ms=avg_latency,
            error_rate=error_rate,
            issues=issues,
            recommendations=recommendations
        )

    async def _store_health_status(self, skill: str, status: HealthStatus):
        """存储健康状态到数据库"""
        await MetricsRepository.upsert_skill_health(skill, {
            "status": status.status,
            "success_rate": status.success_rate,
            "avg_latency_ms": status.avg_latency_ms,
            "error_rate": status.error_rate,
            "issues": status.issues,
            "recommendations": status.recommendations,
        })

    async def _trigger_recovery_if_needed(self, statuses: dict[str, HealthStatus]):
        """触发恢复流程（如果需要）"""
        critical_skills = [
            skill for skill, status in statuses.items()
            if status.status == "critical"
        ]

        if critical_skills:
            logger.error("critical_skills_detected", skills=critical_skills)

            # 通知
            await self._notify_operators(critical_skills)

            # 触发自愈
            from app.harness.autonomous import AutonomousLoops
            for skill in critical_skills:
                await AutonomousLoops.run_emergency_healing(f"skill_critical_{skill}")

    async def _notify_operators(self, skills: list[str]):
        """通知运维人员"""
        # TODO: 实现通知逻辑（邮件、Slack 等）
        logger.error("operators_notified", skills=skills)

    async def get_skill_health(self, skill: str) -> HealthStatus | None:
        """获取特定技能的健康状态"""
        health = await MetricsRepository.get_skill_health(skill)

        if health:
            return HealthStatus(
                skill=health["skill"],
                status=health["status"],
                success_rate=health["success_rate"],
                avg_latency_ms=health["avg_latency_ms"],
                error_rate=health["error_rate"],
                issues=health.get("issues", []),
                recommendations=health.get("recommendations", [])
            )
        return None

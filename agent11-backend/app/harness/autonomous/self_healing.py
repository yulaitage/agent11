"""故障自愈 - Self Healing"""
import structlog
from dataclasses import dataclass
from typing import Literal

logger = structlog.get_logger()


@dataclass
class HealingResult:
    success: bool
    action_taken: str
    message: str
    error: str | None = None


class SelfHealingManager:
    """
    故障自愈管理器 - 尝试自动修复常见问题
    """

    HEALING_RULES = [
        {
            "condition": "skill_timeout",
            "action": "increase_timeout_and_retry",
            "max_retries": 2
        },
        {
            "condition": "chroma_query_slow",
            "action": "rebuild_index",
            "trigger": "query_latency > 5000ms"
        },
        {
            "condition": "llm_connection_failed",
            "action": "switch_to_backup_provider",
            "fallback": "use_cached_response"
        },
        {
            "condition": "memory_fragmented",
            "action": "defragment_memory",
            "trigger": "fragmentation > 30%"
        },
        {
            "condition": "low_confidence_predictions",
            "action": "retrain_model",
            "trigger": "avg_confidence < 0.5"
        }
    ]

    async def heal(self, issue_type: str) -> HealingResult:
        """
        尝试自愈
        """
        logger.info("attempting_self_healing", issue_type=issue_type)

        if issue_type.startswith("skill_critical_"):
            skill = issue_type.replace("skill_critical_", "")
            return await self._heal_skill_issue(skill)

        elif issue_type == "llm_down":
            return await self._heal_llm_failure()

        elif issue_type == "chroma_down":
            return await self._heal_chroma_failure()

        elif issue_type == "memory_issue":
            return await self._heal_memory_issue()

        elif issue_type == "low_confidence_predictions":
            return await self._heal_low_confidence_predictions()

        else:
            return HealingResult(
                success=False,
                action_taken="none",
                message=f"未知问题类型: {issue_type}"
            )

    async def _heal_skill_issue(self, skill: str) -> HealingResult:
        """修复技能问题"""
        # 1. 尝试增加超时时间
        try:
            from app.services.llm import LLMService

            llm = LLMService.get_instance()
            current_config = llm.get_config()

            # 增加超时
            new_timeout = min((current_config.get("timeout", 120) or 120) * 2, 300)
            await llm.update_config({"timeout": new_timeout})

            logger.info("increased_timeout", skill=skill, new_timeout=new_timeout)

            return HealingResult(
                success=True,
                action_taken="increased_timeout",
                message=f"已增加 {skill} 超时到 {new_timeout}秒"
            )

        except Exception as e:
            logger.error("skill_healing_failed", error=str(e))
            return HealingResult(
                success=False,
                action_taken="increase_timeout",
                message=f"增加超时失败: {str(e)}",
                error=str(e)
            )

    async def _heal_llm_failure(self) -> HealingResult:
        """修复 LLM 故障"""
        try:
            from app.services.llm import LLMService

            llm = LLMService.get_instance()

            # 尝试切换到备用 provider
            current = llm.get_config().get("provider", "ollama")
            backup = "lmstudio" if current == "ollama" else "ollama"

            success = await llm.switch_provider(backup)

            if success:
                return HealingResult(
                    success=True,
                    action_taken="switched_provider",
                    message=f"已切换到备用 LLM: {backup}"
                )
            else:
                return HealingResult(
                    success=False,
                    action_taken="switch_provider",
                    message="切换失败，备用 provider 也不可用"
                )

        except Exception as e:
            return HealingResult(
                success=False,
                action_taken="switch_provider",
                message=str(e),
                error=str(e)
            )

    async def _heal_chroma_failure(self) -> HealingResult:
        """修复 ChromaDB 故障"""
        try:
            from app.knowledge.chromadb import ChromaDBClient

            client = ChromaDBClient.get_instance()

            # 重建索引
            await client.rebuild_index()

            return HealingResult(
                success=True,
                action_taken="rebuild_index",
                message="ChromaDB 索引已重建"
            )

        except Exception as e:
            return HealingResult(
                success=False,
                action_taken="rebuild_index",
                message=str(e),
                error=str(e)
            )

    async def _heal_memory_issue(self) -> HealingResult:
        """修复内存问题"""
        try:
            from app.harness.autonomous.memory_optimizer import MemoryOptimizer

            optimizer = MemoryOptimizer()

            # 运行清理
            cleaned = await optimizer.cleanup_old_episodes()

            return HealingResult(
                success=True,
                action_taken="memory_cleanup",
                message=f"已清理 {cleaned} 个过期记忆"
            )

        except Exception as e:
            return HealingResult(
                success=False,
                action_taken="memory_cleanup",
                message=str(e),
                error=str(e)
            )

    async def _heal_low_confidence_predictions(self) -> HealingResult:
        """修复低置信度预测 - 重置预测缓存，触发重新训练"""
        try:
            # 清除预测技能中的缓存预测数据，触发重新计算
            from app.agent.skills.prediction_skill import PredictionSkill

            skill = PredictionSkill()
            cleared = await skill.clear_prediction_cache()

            # 通知技能创建器分析是否需要新模型
            from app.harness.autonomous.skill_creator import SkillCreator
            creator = SkillCreator()
            await creator.run_daily_analysis()

            logger.info("low_confidence_predictions_healed")

            return HealingResult(
                success=True,
                action_taken="retrain_model",
                message=f"已清除预测缓存{'并清空 '+str(cleared)+' 条' if cleared else ''}，触发重新训练"
            )

        except Exception as e:
            logger.error("low_confidence_healing_failed", error=str(e))
            return HealingResult(
                success=False,
                action_taken="retrain_model",
                message=f"低置信度预测自愈失败: {str(e)}",
                error=str(e)
            )

    async def get_health_rules(self) -> list[dict]:
        """获取健康规则"""
        return self.HEALING_RULES

"""Autonomous Loops - 自治循环"""
from app.harness.autonomous.skill_monitor import SkillMonitor
from app.harness.autonomous.knowledge_updater import KnowledgeUpdater
from app.harness.autonomous.memory_optimizer import MemoryOptimizer
from app.harness.autonomous.self_healing import SelfHealingManager
from app.harness.autonomous.skill_creator import SkillCreator

# Global autonomous loops instance
_autonomous_loops = None


class AutonomousLoops:
    """
    自治循环管理器 - 自我监控、自我修复、自我进化
    """

    @classmethod
    async def start(cls):
        """启动自治循环"""
        global _autonomous_loops

        skill_monitor = SkillMonitor()
        knowledge_updater = KnowledgeUpdater()
        memory_optimizer = MemoryOptimizer()
        self_healer = SelfHealingManager()
        skill_creator = SkillCreator()

        _autonomous_loops = cls(
            skill_monitor=skill_monitor,
            knowledge_updater=knowledge_updater,
            memory_optimizer=memory_optimizer,
            self_healer=self_healer,
            skill_creator=skill_creator
        )

        await _autonomous_loops._start_all_loops()

    @classmethod
    async def stop(cls):
        """停止自治循环"""
        global _autonomous_loops
        _autonomous_loops = None

    def __init__(
        self,
        skill_monitor: SkillMonitor,
        knowledge_updater: KnowledgeUpdater,
        memory_optimizer: MemoryOptimizer,
        self_healer: SelfHealingManager,
        skill_creator: SkillCreator
    ):
        self.skill_monitor = skill_monitor
        self.knowledge_updater = knowledge_updater
        self.memory_optimizer = memory_optimizer
        self.self_healer = self_healer
        self.skill_creator = skill_creator

    async def _start_all_loops(self):
        """启动所有自治循环"""
        import asyncio
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from app.config import get_settings

        settings = get_settings()
        scheduler = AsyncIOScheduler(timezone=settings.scheduler_timezone)

        # 技能监控 - 每小时
        scheduler.add_job(
            self.skill_monitor.run_health_check,
            "interval",
            minutes=settings.skill_monitor_interval_minutes,
            id="skill_monitor",
            name="技能健康检查"
        )

        # 知识更新 - 每天凌晨 2:00
        scheduler.add_job(
            self.knowledge_updater.run_daily_extraction,
            "cron",
            hour=2,
            minute=0,
            id="knowledge_update",
            name="每日知识提取"
        )

        # 记忆优化 - 每周日凌晨 3:00
        scheduler.add_job(
            self.memory_optimizer.run_weekly_optimization,
            "cron",
            day_of_week=6,
            hour=3,
            minute=0,
            id="memory_optimize",
            name="每周记忆优化"
        )

        # 技能自动创建 - 每天凌晨 4:00
        scheduler.add_job(
            self.skill_creator.run_daily_analysis,
            "cron",
            hour=4,
            minute=0,
            id="skill_creator",
            name="每日技能创建分析"
        )

        scheduler.start()

    async def run_emergency_healing(self, issue_type: str) -> dict:
        """运行紧急自愈"""
        return await self.self_healer.heal(issue_type)

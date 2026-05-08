"""Loop Operator - 持续优化循环"""
from __future__ import annotations

from typing import Optional
from app.harness.loop_operator.metrics import MetricsCollector, AgentMetrics
from app.harness.loop_operator.trend_analyzer import TrendAnalyzer
from app.harness.loop_operator.optimizer import OptimizationDecider, Action
from app.harness.loop_operator.executor import LoopExecutor

# Global loop operator instance
_loop_operator: Optional["LoopOperator"] = None


class LoopOperator:
    """
    Loop Operator - 持续优化引擎
    感知 -> 分析 -> 决策 -> 执行 -> 验证
    """

    _running = False

    @classmethod
    async def start(cls):
        """启动 Loop Operator"""
        global _loop_operator

        metrics = MetricsCollector()
        trend_analyzer = TrendAnalyzer()
        decider = OptimizationDecider()
        executor = LoopExecutor()

        _loop_operator = cls(
            metrics=metrics,
            trend_analyzer=trend_analyzer,
            decider=decider,
            executor=executor
        )

        cls._running = True
        await _loop_operator._start_loops()

    @classmethod
    async def stop(cls):
        """停止 Loop Operator"""
        cls._running = False
        global _loop_operator
        _loop_operator = None

    @classmethod
    def get_instance(cls) -> "LoopOperator":
        if _loop_operator is None:
            raise RuntimeError("LoopOperator not started")
        return _loop_operator

    def __init__(
        self,
        metrics: MetricsCollector,
        trend_analyzer: TrendAnalyzer,
        decider: OptimizationDecider,
        executor: LoopExecutor
    ):
        self.metrics = metrics
        self.trend_analyzer = trend_analyzer
        self.decider = decider
        self.executor = executor

    async def _start_loops(self):
        """启动各个循环任务"""
        import asyncio
        from app.config import get_settings

        settings = get_settings()

        # 指标收集循环
        asyncio.create_task(self._metrics_collection_loop(
            interval_minutes=settings.loop_metrics_interval_minutes
        ))

        # 趋势分析循环
        asyncio.create_task(self._trend_analysis_loop(
            interval_hours=settings.loop_trend_interval_hours
        ))

        # 优化决策循环
        asyncio.create_task(self._optimization_loop(
            interval_hours=settings.loop_optimize_interval_hours
        ))

    async def _metrics_collection_loop(self, interval_minutes: int):
        """指标收集循环"""
        import asyncio
        import structlog

        logger = structlog.get_logger()

        while self._running:
            try:
                await self.metrics.collect_all()
                logger.debug("metrics_collected", metrics=self.metrics.get_current())
            except Exception as e:
                logger.error("metrics_collection_failed", error=str(e))

            await asyncio.sleep(interval_minutes * 60)

    async def _trend_analysis_loop(self, interval_hours: int):
        """趋势分析循环"""
        import asyncio
        import structlog

        logger = structlog.get_logger()

        while self._running:
            try:
                trends = await self.trend_analyzer.analyze(
                    self.metrics.get_history()
                )

                if trends:
                    logger.info("trends_detected", count=len(trends))

                    # 存储趋势
                    await self.metrics.store_trends(trends)

            except Exception as e:
                logger.error("trend_analysis_failed", error=str(e))

            await asyncio.sleep(interval_hours * 3600)

    async def _optimization_loop(self, interval_hours: int):
        """优化决策循环"""
        import asyncio
        import structlog

        logger = structlog.get_logger()

        while self._running:
            try:
                current_metrics = self.metrics.get_current()
                if current_metrics is None:
                    await asyncio.sleep(60)  # 等待首次指标收集
                    continue
                trends = await self.trend_analyzer.analyze(
                    self.metrics.get_history()
                )

                # 决策
                actions = await self.decider.decide(trends, current_metrics)

                # 执行
                for action in actions:
                    result = await self.executor.execute(action)
                    logger.info("optimization_action_executed",
                               action=action.type,
                               result=result)

            except Exception as e:
                logger.error("optimization_loop_failed", error=str(e))

            await asyncio.sleep(interval_hours * 3600)

    async def trigger_immediate_optimization(self):
        """触发立即优化"""
        current_metrics = self.metrics.get_current()
        if current_metrics is None:
            return {"actions": [], "error": "指标尚未收集，请稍后再试"}
        trends = await self.trend_analyzer.analyze(self.metrics.get_history())
        actions = await self.decider.decide(trends, current_metrics)

        results = []
        for action in actions:
            result = await self.executor.execute(action)
            results.append({"action": action.type, "result": result})

        return {"actions": results}

"""回归测试套件 - Regression Suite"""
import structlog
from app.harness.evaluator.executor import EvalExecutor
from app.config import get_settings

logger = structlog.get_logger()


class RegressionSuite:
    """
    回归测试套件 - 确保代码变更不破坏现有功能
    """

    def __init__(self, executor: EvalExecutor):
        self.executor = executor
        self.settings = get_settings()
        self._last_report = None

    async def run_pre_deployment_check(self) -> dict:
        """
        部署前回归检查
        必须通过才能部署
        """
        logger.info("running_regression_suite", type="pre_deployment")

        report = await self.executor.run_regression()

        self._last_report = report

        # 检查是否通过
        passed = report.pass_rate >= self.settings.eval_pass_threshold

        if not passed:
            logger.warning(
                "regression_failed",
                pass_rate=report.pass_rate,
                threshold=self.settings.eval_pass_threshold,
                failed_cases=[
                    r.test_case_id for r in report.results if not r.passed
                ]
            )

        return {
            "passed": passed,
            "pass_rate": report.pass_rate,
            "threshold": self.settings.eval_pass_threshold,
            "total_cases": report.total_cases,
            "failed_cases": [
                {
                    "test_id": r.test_case_id,
                    "skill": r.skill,
                    "score": r.overall_score,
                    "error": r.error
                }
                for r in report.results if not r.passed
            ],
            "dimension_breakdown": report.dimension_breakdown,
            "avg_latency_ms": report.avg_latency_ms
        }

    async def run_skill_regression(self, skill: str) -> dict:
        """运行单个技能的回归测试"""
        logger.info("running_skill_regression", skill=skill)

        report = await self.executor.run_skill_eval(skill)

        return {
            "skill": skill,
            "passed": report.pass_rate >= self.settings.eval_pass_threshold,
            "pass_rate": report.pass_rate,
            "total_cases": report.total_cases,
            "avg_score": report.avg_score,
            "avg_latency_ms": report.avg_latency_ms,
            "dimension_breakdown": report.dimension_breakdown
        }

    async def run_continuous_check(self, sample_size: int = 10) -> dict:
        """
        持续检查 - 从生产流量中抽样评估
        """
        # 从 eval_test_cases 随机抽样
        import random
        all_cases = await self.executor.test_repo.get_test_suite()
        sample = random.sample(all_cases, min(sample_size, len(all_cases)))

        agent = self.executor.test_repo  # 获取 agent

        results = []
        for case in sample:
            result = await self.executor.evaluate_test_case(
                case,
                self.executor.test_repo  # placeholder
            )
            results.append(result)

        # 检测异常
        low_scores = [r for r in results if r.overall_score < 0.6]

        if low_scores:
            logger.warning(
                "low_score_detected_in_production",
                count=len(low_scores),
                tests=[r.test_case_id for r in low_scores]
            )

        return {
            "sample_size": len(sample),
            "avg_score": sum(r.overall_score for r in results) / len(results) if results else 0,
            "low_score_count": len(low_scores),
            "low_score_tests": [
                {"test_id": r.test_case_id, "score": r.overall_score}
                for r in low_scores
            ]
        }

    def get_last_report(self) -> dict | None:
        """获取上次回归报告"""
        if self._last_report:
            return {
                "total_cases": self._last_report.total_cases,
                "passed_cases": self._last_report.passed_cases,
                "pass_rate": self._last_report.pass_rate,
                "avg_score": self._last_report.avg_score,
                "avg_latency_ms": self._last_report.avg_latency_ms,
            }
        return None

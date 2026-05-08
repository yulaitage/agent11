"""评估执行器 - Eval Executor"""
import time
from dataclasses import dataclass
from typing import Any
from app.harness.evaluator.rubric import RubricScorer, SKILL_RUBRICS
from app.db.repositories.eval import EvalRepository


@dataclass
class EvalResult:
    """单个评估结果"""
    test_case_id: str
    skill: str
    query: str
    overall_score: float
    dimension_scores: dict[str, float]
    latency_ms: float
    passed: bool
    response_snapshot: dict | None = None
    error: str | None = None


@dataclass
class EvalReport:
    """评估报告"""
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float
    avg_score: float
    avg_latency_ms: float
    dimension_breakdown: dict[str, float]
    results: list[EvalResult]


class EvalExecutor:
    """
    评估执行器 - 运行测试并评分
    """

    def __init__(
        self,
        scorer: RubricScorer
    ):
        self.scorer = scorer

    async def evaluate_response(
        self,
        skill: str,
        query: str,
        context: dict,
        response: dict
    ) -> EvalResult:
        """评估单个响应"""
        start_time = time.time()

        try:
            # 评分
            scores = self.scorer.score_response(skill, response)
            latency_ms = (time.time() - start_time) * 1000

            # 确定是否通过
            rubric = SKILL_RUBRICS.get(skill)
            threshold = 0.7  # 默认阈值
            passed = scores.get("overall", 0) >= threshold

            result = EvalResult(
                test_case_id="realtime_eval",
                skill=skill,
                query=query,
                overall_score=scores.get("overall", 0),
                dimension_scores={k: v for k, v in scores.items() if k != "overall"},
                latency_ms=latency_ms,
                passed=passed,
                response_snapshot=response
            )

            # 存储结果
            await self._store_result(result)

            return result

        except Exception as e:
            return EvalResult(
                test_case_id="realtime_eval",
                skill=skill,
                query=query,
                overall_score=0.0,
                dimension_scores={},
                latency_ms=(time.time() - start_time) * 1000,
                passed=False,
                error=str(e)
            )

    async def evaluate_test_case(
        self,
        test_case: dict,
        agent
    ) -> EvalResult:
        """执行单个测试用例并评估"""
        start_time = time.time()

        try:
            # 调用 Agent
            response = await agent.execute(
                skill=test_case["skill"],
                query=test_case["query"],
                context=test_case.get("context", {})
            )

            # 评分
            scores = self.scorer.score_response(
                test_case["skill"],
                response,
                test_case.get("expected")
            )

            latency_ms = (time.time() - start_time) * 1000

            passed = scores.get("overall", 0) >= 0.7

            result = EvalResult(
                test_case_id=test_case["id"],
                skill=test_case["skill"],
                query=test_case["query"],
                overall_score=scores.get("overall", 0),
                dimension_scores={k: v for k, v in scores.items() if k != "overall"},
                latency_ms=latency_ms,
                passed=passed,
                response_snapshot=response
            )

            # 存储结果
            await self._store_result(result)

            return result

        except Exception as e:
            return EvalResult(
                test_case_id=test_case["id"],
                skill=test_case["skill"],
                query=test_case["query"],
                overall_score=0.0,
                dimension_scores={},
                latency_ms=(time.time() - start_time) * 1000,
                passed=False,
                error=str(e)
            )

    async def run_regression(self) -> EvalReport:
        """运行回归测试"""
        regression_cases = await EvalRepository.find_test_cases(is_regression=True)
        agent = AgentGenerator.get_instance()

        results = []
        for case in regression_cases:
            result = await self.evaluate_test_case(case, agent)
            results.append(result)

        return self._aggregate_results(results)

    async def run_skill_eval(self, skill: str) -> EvalReport:
        """运行某个技能的完整评估"""
        cases = await EvalRepository.find_test_cases(skill=skill)
        agent = AgentGenerator.get_instance()

        results = []
        for case in cases:
            result = await self.evaluate_test_case(case, agent)
            results.append(result)

        return self._aggregate_results(results)

    def _aggregate_results(self, results: list[EvalResult]) -> EvalReport:
        """聚合评估结果"""
        if not results:
            return EvalReport(
                total_cases=0,
                passed_cases=0,
                failed_cases=0,
                pass_rate=0.0,
                avg_score=0.0,
                avg_latency_ms=0.0,
                dimension_breakdown={},
                results=[]
            )

        passed = sum(1 for r in results if r.passed)
        total_score = sum(r.overall_score for r in results)
        total_latency = sum(r.latency_ms for r in results)

        # 维度分解
        dimension_totals: dict[str, float] = {}
        dimension_counts: dict[str, int] = {}

        for r in results:
            for dim, score in r.dimension_scores.items():
                dimension_totals[dim] = dimension_totals.get(dim, 0) + score
                dimension_counts[dim] = dimension_counts.get(dim, 0) + 1

        dimension_breakdown = {
            dim: dimension_totals[dim] / dimension_counts[dim]
            for dim in dimension_totals
        }

        return EvalReport(
            total_cases=len(results),
            passed_cases=passed,
            failed_cases=len(results) - passed,
            pass_rate=passed / len(results),
            avg_score=total_score / len(results),
            avg_latency_ms=total_latency / len(results),
            dimension_breakdown=dimension_breakdown,
            results=results
        )

    async def _store_result(self, result: EvalResult):
        """存储评估结果"""
        await EvalRepository.save_result({
            "id": f"eval_{result.test_case_id}_{time.time()}",
            "test_case_id": result.test_case_id,
            "skill": result.skill,
            "query": result.query,
            "overall_score": result.overall_score,
            "dimension_scores": result.dimension_scores,
            "latency_ms": result.latency_ms,
            "passed": result.passed,
            "response_snapshot": result.response_snapshot,
            "error": result.error,
            "evaluated_at": datetime.utcnow()
        })

"""Evaluator - AGENT 11 Eval Harness"""
from app.harness.evaluator.rubric import SkillRubric, RubricScorer
from app.harness.evaluator.test_cases import TestCase, TestCaseRepository
from app.harness.evaluator.executor import EvalExecutor
from app.harness.evaluator.regression import RegressionSuite

# Global evaluator instance
_evaluator: EvalExecutor | None = None


class EvalHarness:
    """
    Eval Harness - Agent 评估体系
    负责测试用例管理、自动评分、回归检测
    """

    @classmethod
    async def initialize(cls):
        """初始化评估系统"""
        global _evaluator
        rubric = RubricScorer()
        _evaluator = EvalExecutor(rubric)
        return _evaluator

    @classmethod
    def get_instance(cls) -> EvalExecutor:
        if _evaluator is None:
            raise RuntimeError("EvalHarness not initialized")
        return _evaluator

    @classmethod
    async def evaluate_skill(
        cls,
        skill: str,
        query: str,
        context: dict,
        response: dict
    ) -> dict:
        """评估单个技能响应"""
        evaluator = cls.get_instance()
        return await evaluator.evaluate_response(skill, query, context, response)

    @classmethod
    async def run_regression_suite(cls) -> dict:
        """运行回归测试"""
        evaluator = cls.get_instance()
        return await evaluator.run_regression()

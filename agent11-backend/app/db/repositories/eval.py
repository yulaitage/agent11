"""Evaluation Repository"""
from typing import Optional
from datetime import datetime

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.eval import EvalResult, EvalTestCase
from app.db.session import get_session


class EvalRepository:
    """Repository for EvalResult and EvalTestCase models"""

    @classmethod
    async def save_result(cls, result_data: dict) -> dict:
        """Save an evaluation result"""
        async for session in get_session():
            result = EvalResult(**result_data)
            session.add(result)
            await session.commit()
            await session.refresh(result)
            return cls._result_to_dict(result)

    @classmethod
    async def find_results_by_skill(
        cls,
        skill: str,
        limit: int = 100
    ) -> list[dict]:
        """Find evaluation results by skill"""
        async for session in get_session():
            query = (
                select(EvalResult)
                .where(EvalResult.skill == skill)
                .order_by(EvalResult.evaluated_at.desc())
                .limit(limit)
            )
            result = await session.execute(query)
            results = result.scalars().all()
            return [cls._result_to_dict(r) for r in results]

    @classmethod
    async def find_results_by_test_case(
        cls,
        test_case_id: str,
        limit: int = 50
    ) -> list[dict]:
        """Find evaluation results by test case ID"""
        async for session in get_session():
            query = (
                select(EvalResult)
                .where(EvalResult.test_case_id == test_case_id)
                .order_by(EvalResult.evaluated_at.desc())
                .limit(limit)
            )
            result = await session.execute(query)
            results = result.scalars().all()
            return [cls._result_to_dict(r) for r in results]

    @classmethod
    async def get_test_case(cls, test_case_id: str) -> Optional[dict]:
        """Get a test case by ID"""
        async for session in get_session():
            result = await session.execute(
                select(EvalTestCase).where(EvalTestCase.id == test_case_id)
            )
            tc = result.scalar_one_or_none()
            if tc:
                return cls._test_case_to_dict(tc)
            return None

    @classmethod
    async def find_test_cases(
        cls,
        skill: Optional[str] = None,
        difficulty: Optional[str] = None,
        is_regression: bool = False,
        limit: int = 100
    ) -> list[dict]:
        """Find test cases with filters"""
        async for session in get_session():
            query = select(EvalTestCase)

            conditions = []
            if skill:
                conditions.append(EvalTestCase.skill == skill)
            if difficulty:
                conditions.append(EvalTestCase.difficulty == difficulty)
            if is_regression:
                conditions.append(EvalTestCase.is_regression == True)

            if conditions:
                query = query.where(and_(*conditions))

            query = query.limit(limit)

            result = await session.execute(query)
            cases = result.scalars().all()
            return [cls._test_case_to_dict(c) for c in cases]

    @classmethod
    async def create_test_case(cls, case_data: dict) -> dict:
        """Create a new test case"""
        async for session in get_session():
            tc = EvalTestCase(**case_data)
            session.add(tc)
            await session.commit()
            await session.refresh(tc)
            return cls._test_case_to_dict(tc)

    @classmethod
    def _result_to_dict(cls, result: EvalResult) -> dict:
        return {
            "id": result.id,
            "test_case_id": result.test_case_id,
            "skill": result.skill,
            "query": result.query,
            "overall_score": result.overall_score,
            "dimension_scores": result.dimension_scores,
            "latency_ms": result.latency_ms,
            "passed": result.passed,
            "response_snapshot": result.response_snapshot,
            "error": result.error,
            "evaluated_at": result.evaluated_at,
        }

    @classmethod
    def _test_case_to_dict(cls, tc: EvalTestCase) -> dict:
        return {
            "id": tc.id,
            "skill": tc.skill,
            "query": tc.query,
            "context": tc.context,
            "expected": tc.expected,
            "acceptable_responses": tc.acceptable_responses,
            "difficulty": tc.difficulty,
            "category": tc.category,
            "is_regression": tc.is_regression,
            "created_by": tc.created_by,
            "created_at": tc.created_at,
        }

"""Evaluation models"""
from sqlalchemy import Column, String, Float, Boolean, DateTime, Index, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.sql import func
from app.db.session import Base


class EvalResult(Base):
    __tablename__ = "eval_results"

    id = Column(String, primary_key=True)
    test_case_id = Column(String, index=True)
    skill = Column(String, index=True)
    query = Column(Text)
    overall_score = Column(Float)
    dimension_scores = Column(JSON)
    latency_ms = Column(Float)
    passed = Column(Boolean)
    response_snapshot = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    evaluated_at = Column(DateTime, server_default=func.now(), index=True)

    __table_args__ = (
        Index("ix_eval_results_skill_evaluated", "skill", "evaluated_at"),
    )


class EvalTestCase(Base):
    __tablename__ = "eval_test_cases"

    id = Column(String, primary_key=True)
    skill = Column(String, index=True)
    query = Column(Text)
    context = Column(JSON)
    expected = Column(JSON)
    acceptable_responses = Column(JSON)
    difficulty = Column(String)  # easy, medium, hard
    category = Column(String)
    is_regression = Column(Boolean, default=False)
    created_by = Column(String)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_eval_test_cases_skill_category", "skill", "category"),
    )

"""Metrics models"""
from sqlalchemy import Column, String, Float, DateTime, Index
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.sql import func
from app.db.session import Base


class MetricsHistory(Base):
    __tablename__ = "metrics_history"

    id = Column(String, primary_key=True)
    timestamp = Column(DateTime, server_default=func.now(), index=True)
    skills = Column(JSON)
    knowledge = Column(JSON)
    memory = Column(JSON)
    system = Column(JSON)


class SkillHealth(Base):
    __tablename__ = "skill_health"

    skill = Column(String, primary_key=True)
    status = Column(String)  # healthy, degraded, critical
    success_rate = Column(Float)
    avg_latency_ms = Column(Float)
    error_rate = Column(Float)
    issues = Column(JSON)
    recommendations = Column(JSON)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

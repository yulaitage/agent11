"""API Call Log model"""
from sqlalchemy import Column, String, DateTime, Integer, Float, JSON, Index
from sqlalchemy.sql import func
from app.db.session import Base


class APICallLog(Base):
    __tablename__ = "api_call_logs"

    id = Column(String, primary_key=True)
    timestamp = Column(DateTime, server_default=func.now(), index=True)
    method = Column(String, nullable=False)  # GET, POST, etc.
    path = Column(String, nullable=False, index=True)
    request_body = Column(JSON, nullable=True)
    response_status = Column(Integer, nullable=False, index=True)
    response_body = Column(JSON, nullable=True)
    duration_ms = Column(Float, nullable=False)
    user_id = Column(String, nullable=True)
    thread_id = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)

    __table_args__ = (
        Index("ix_api_call_logs_path_timestamp", "path", "timestamp"),
        Index("ix_api_call_logs_response_status_timestamp", "response_status", "timestamp"),
    )
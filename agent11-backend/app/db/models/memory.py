"""Memory Palace models - 10 tables for structured memory"""
from sqlalchemy import Column, String, Boolean, DateTime, Index
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.sql import func
from app.db.session import Base


class MemoryBase:
    """Common fields for all memory tables"""
    entity_id = Column(String, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    archived = Column(Boolean, default=False)
    archived_at = Column(DateTime, nullable=True)


class MemoryInfraDevices(Base, MemoryBase):
    __tablename__ = "memory_infra_devices"

    id = Column(String, primary_key=True)
    data = Column(JSON)


class MemoryInfraGeozones(Base, MemoryBase):
    __tablename__ = "memory_infra_geozones"

    id = Column(String, primary_key=True)
    data = Column(JSON)


class MemoryInfraSystems(Base, MemoryBase):
    __tablename__ = "memory_infra_systems"

    id = Column(String, primary_key=True)
    data = Column(JSON)


class MemoryInfraProtocols(Base, MemoryBase):
    __tablename__ = "memory_infra_protocols"

    id = Column(String, primary_key=True)
    data = Column(JSON)


class MemoryConversEpisodes(Base, MemoryBase):
    __tablename__ = "memory_convers_episodes"

    id = Column(String, primary_key=True)
    summary = Column(JSON)
    learned_facts = Column(JSON)


class MemoryConversSessions(Base, MemoryBase):
    __tablename__ = "memory_convers_sessions"

    id = Column(String, primary_key=True)
    summary = Column(JSON)
    data = Column(JSON)


class MemoryConversPreferences(Base, MemoryBase):
    __tablename__ = "memory_convers_preferences"

    id = Column(String, primary_key=True)
    preference_type = Column(String)
    data = Column(JSON)


class MemoryLearningPatterns(Base, MemoryBase):
    __tablename__ = "memory_learning_patterns"

    id = Column(String, primary_key=True)
    pattern_type = Column(String)
    pattern_data = Column(JSON)


class MemoryLearningRelationships(Base, MemoryBase):
    __tablename__ = "memory_learning_relationships"

    id = Column(String, primary_key=True)
    source_entity = Column(String)
    target_entity = Column(String)
    relationship_type = Column(String)
    data = Column(JSON)


class MemoryLearningInsights(Base, MemoryBase):
    __tablename__ = "memory_learning_insights"

    id = Column(String, primary_key=True)
    insight_type = Column(String)
    data = Column(JSON)

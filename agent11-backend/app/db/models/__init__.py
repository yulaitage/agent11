"""SQLAlchemy Models"""
from app.db.models.device import Device
from app.db.models.reading import DeviceReading, EnergyReading
from app.db.models.fault import FaultRecord
from app.db.models.comm import CommLog
from app.db.models.chat import Chat
from app.db.models.eval import EvalResult, EvalTestCase
from app.db.models.metrics import MetricsHistory, SkillHealth
from app.db.models.user import User
from app.db.models.memory import (
    MemoryInfraDevices,
    MemoryInfraGeozones,
    MemoryInfraSystems,
    MemoryInfraProtocols,
    MemoryConversEpisodes,
    MemoryConversSessions,
    MemoryConversPreferences,
    MemoryLearningPatterns,
    MemoryLearningRelationships,
    MemoryLearningInsights,
)
from app.db.models.group import GroupInfo
from app.db.models.device_info import DeviceInfo
from app.db.models.device_threshold import DeviceThreshold
from app.db.models.device_fault import DeviceFault
from app.db.models.device_consumption import DeviceConsumption
from app.db.models.group_consumption import GroupConsumption

__all__ = [
    "Device",
    "DeviceReading",
    "EnergyReading",
    "FaultRecord",
    "CommLog",
    "Chat",
    "EvalResult",
    "EvalTestCase",
    "MetricsHistory",
    "SkillHealth",
    "User",
    "MemoryInfraDevices",
    "MemoryInfraGeozones",
    "MemoryInfraSystems",
    "MemoryInfraProtocols",
    "MemoryConversEpisodes",
    "MemoryConversSessions",
    "MemoryConversPreferences",
    "MemoryLearningPatterns",
    "MemoryLearningRelationships",
    "MemoryLearningInsights",
    "GroupInfo",
    "DeviceInfo",
    "DeviceThreshold",
    "DeviceFault",
    "DeviceConsumption",
    "GroupConsumption",
]

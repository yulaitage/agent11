"""Repositories"""
from app.db.repositories.device import DeviceRepository
from app.db.repositories.reading import ReadingRepository
from app.db.repositories.fault import FaultRepository
from app.db.repositories.comm import CommRepository
from app.db.repositories.chat import ChatRepository
from app.db.repositories.eval import EvalRepository
from app.db.repositories.metrics import MetricsRepository
from app.db.repositories.memory import MemoryRepository
from app.db.repositories.group import GroupRepository
from app.db.repositories.device_info import DeviceInfoRepository
from app.db.repositories.device_fault import DeviceFaultRepository
from app.db.repositories.device_consumption import DeviceConsumptionRepository
from app.db.repositories.api_call_log import APICallLogRepository

__all__ = [
    "DeviceRepository",
    "ReadingRepository",
    "FaultRepository",
    "CommRepository",
    "ChatRepository",
    "EvalRepository",
    "MetricsRepository",
    "MemoryRepository",
    "GroupRepository",
    "DeviceInfoRepository",
    "DeviceFaultRepository",
    "DeviceConsumptionRepository",
    "APICallLogRepository",
]

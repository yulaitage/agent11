"""设备 API"""
from fastapi import APIRouter, HTTPException
from typing import Literal

from app.db.repositories.device import DeviceRepository
from app.db.repositories.reading import ReadingRepository
from app.db.repositories.fault import FaultRepository
from app.db.repositories.comm import CommRepository

router = APIRouter()


@router.get("/")
async def list_devices(
    geozone: str | None = None,
    device_type: Literal["streetlight", "controller", "sensor"] | None = None,
    status: Literal["normal", "warning", "fault", "offline"] | None = None,
    limit: int = 100
):
    """列出设备"""
    devices = await DeviceRepository.find_all(
        geozone=geozone,
        status=status,
        device_type=device_type,
        limit=limit
    )

    return {
        "devices": [
            {
                "id": d.get("device_id"),
                "type": d.get("device_type"),
                "status": d.get("status"),
                "geozone": d.get("geozone"),
                "location": {
                    "lat": d.get("latitude"),
                    "lng": d.get("longitude")
                }
            }
            for d in devices
        ]
    }


@router.get("/{device_id}")
async def get_device(device_id: str):
    """获取设备详情"""
    device = await DeviceRepository.find_by_id(device_id)

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    return device


@router.get("/{device_id}/readings")
async def get_device_readings(
    device_id: str,
    limit: int = 100
):
    """获取设备读数"""
    readings = await ReadingRepository.get_device_readings(
        device_id=device_id,
        limit=limit
    )

    return {
        "device_id": device_id,
        "readings": readings
    }


@router.get("/{device_id}/history")
async def get_device_history(
    device_id: str,
    limit: int = 50
):
    """获取设备历史"""
    # 获取故障历史
    faults = await FaultRepository.find_by_device(
        device_id=device_id,
        limit=limit
    )

    # 获取通信日志
    comm_logs = await CommRepository.find_by_device(
        device_id=device_id,
        limit=limit
    )

    return {
        "device_id": device_id,
        "faults": faults,
        "comm_logs": comm_logs
    }

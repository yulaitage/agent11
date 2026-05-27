"""API Logs routes"""
from datetime import datetime
from typing import Any
from fastapi import APIRouter, Query
from app.db.repositories.api_call_log import APICallLogRepository

router = APIRouter()


@router.get("/")
async def list_logs(
    status: int | None = Query(None, description="Filter by HTTP status code"),
    method: str | None = Query(None, description="Filter by HTTP method (GET, POST, etc.)"),
    path: str | None = Query(None, description="Search path containing this string"),
    start_date: str | None = Query(None, description="ISO date string, e.g. 2026-04-01"),
    end_date: str | None = Query(None, description="ISO date string, e.g. 2026-04-28"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List API call logs with optional filters"""
    # Parse dates
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None

    logs, total = await APICallLogRepository.get_recent(
        limit=limit,
        offset=offset,
        status=status,
        method=method,
        path_contains=path,
        start_date=start,
        end_date=end,
    )

    return {
        "logs": logs,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/stats")
async def get_stats() -> dict[str, Any]:
    """Get summary statistics for API calls"""
    stats = await APICallLogRepository.get_stats()
    return stats
"""可观测性 API"""
from fastapi import APIRouter
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

router = APIRouter()


@router.get("/metrics")
async def get_metrics():
    """Prometheus 格式指标"""
    from prometheus_client import REGISTRY

    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST
    )


@router.get("/health")
async def observability_health():
    """可观测性健康状态"""
    return {
        "status": "healthy",
        "components": {
            "metrics": "active",
            "logging": "active",
            "tracing": "pending"
        }
    }


@router.get("/trends")
async def get_trends(limit: int = 50):
    """获取趋势数据 - 使用 PostgreSQL metrics_history 表"""
    from app.db.repositories.metrics import MetricsRepository

    metrics = await MetricsRepository.get_recent_metrics(limit=limit)

    return {"trends": metrics}


@router.get("/skill-health")
async def get_skill_health():
    """获取技能健康状态 - 使用 PostgreSQL skill_health 表"""
    from app.db.repositories.metrics import MetricsRepository

    health = await MetricsRepository.get_all_skill_health()

    return {
        "skills": [
            {
                "skill": s.get("skill"),
                "status": s.get("status"),
                "success_rate": s.get("success_rate"),
                "avg_latency_ms": s.get("avg_latency_ms"),
                "issues": s.get("issues", []),
                "recommendations": s.get("recommendations", [])
            }
            for s in health
        ]
    }

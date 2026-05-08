"""健康检查 API"""
from fastapi import APIRouter
from app.db.postgres import Database
from app.services.llm import LLMService

router = APIRouter()


@router.get("/")
async def health_check():
    """基础健康检查"""
    return {"status": "healthy"}


@router.get("/detailed")
async def detailed_health():
    """详细健康状态"""
    from app.config import get_settings
    settings = get_settings()

    # LLM 健康
    llm_healthy = False
    try:
        llm = LLMService.get_instance()
        llm_healthy = await llm.health_check()
    except:
        pass

    # PostgreSQL 健康
    pg_healthy = False
    try:
        pg_healthy = await Database.health_check()
    except:
        pass

    # ChromaDB 健康
    chroma_healthy = False
    try:
        from app.knowledge.chromadb import ChromaDBClient
        chroma = ChromaDBClient.get_instance()
        chroma_healthy = await chroma.health_check()
    except:
        pass

    overall = "healthy" if (llm_healthy and pg_healthy) else "degraded"
    if not llm_healthy or not pg_healthy:
        overall = "unhealthy"

    return {
        "status": overall,
        "components": {
            "llm": {
                "status": "healthy" if llm_healthy else "down",
                "provider": settings.llm_provider,
                "model": settings.llm_model
            },
            "postgresql": {
                "status": "healthy" if pg_healthy else "down"
            },
            "chromadb": {
                "status": "healthy" if chroma_healthy else "down"
            }
        }
    }

"""跨会话搜索 API - Feature 4"""
from fastapi import APIRouter, Query
from pydantic import BaseModel
import structlog

from app.services.search import SearchService

logger = structlog.get_logger()
router = APIRouter()


class SearchResponse(BaseModel):
    results: list[dict]
    total: int


@router.get("/search", response_model=SearchResponse)
async def search_all(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    limit: int = Query(10, ge=1, le=50),
):
    """跨聊天记录、记忆、知识库的全文搜索"""
    results = await SearchService.search_all(q, limit=limit)
    return SearchResponse(results=results, total=len(results))

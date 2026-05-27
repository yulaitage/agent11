"""API 路由"""
from fastapi import APIRouter
from app.api.routes import chats, knowledge, memory, reports, devices, health, llm, observability, skills, auth, protocols, models, import_excel, api_logs

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(chats.router, prefix="/chats", tags=["chats"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
api_router.include_router(memory.router, prefix="/memory", tags=["memory"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(devices.router, prefix="/devices", tags=["devices"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(llm.router, prefix="/llm", tags=["llm"])
api_router.include_router(observability.router, prefix="/observability", tags=["observability"])
api_router.include_router(skills.router, prefix="/skills", tags=["skills"])
api_router.include_router(protocols.router, prefix="/protocols", tags=["protocols"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(import_excel.router, prefix="/import", tags=["import"])
api_router.include_router(api_logs.router, prefix="/logs", tags=["logs"])

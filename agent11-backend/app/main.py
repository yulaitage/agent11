"""
AGENT 11 - GAN Harness Architecture
====================================

基于 Claude Code Harness 框架的智能基础设施管理 Agent

架构组件:
- Generator: 基于 LangGraph 的 Agent (skills/agent)
- Evaluator: 评估 Agent 表现 (harness/evaluator)
- Loop Operator: 持续优化循环 (harness/loop_operator)
- Autonomous Loops: 自治监控系统 (harness/autonomous)
- Memory Palace: 结构化记忆系统 (memory/palace)
- Observability: 可观测性 (observability/)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import get_settings
from app.api.router import api_router
from app.db.postgres import Database
from app.db.session import init_db, close_db
from app.services.llm import LLMService
from app.agent.generator import AgentGenerator
from app.agent.skills import SkillRegistry
from app.harness.evaluator import EvalHarness
from app.harness.loop_operator import LoopOperator
from app.harness.autonomous import AutonomousLoops
from app.memory.palace import MemoryPalace
from app.observability.metrics import MetricsCollector

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown"""
    # Startup
    await init_db()
    await Database.connect()
    await LLMService.initialize()
    await AgentGenerator.initialize()

    # Load custom skills from database
    skill_registry = SkillRegistry.get_instance()
    await skill_registry.load_from_database()

    await EvalHarness.initialize()
    await LoopOperator.start()
    await AutonomousLoops.start()
    await MemoryPalace.initialize()

    # Register metrics collector
    MetricsCollector.register_default_metrics()

    yield

    # Shutdown
    await LoopOperator.stop()
    await AutonomousLoops.stop()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes
app.include_router(api_router, prefix="/api")


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": settings.app_version,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
    }

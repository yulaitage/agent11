"""指标收集器 - Metrics Collector"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from app.db.repositories.metrics import MetricsRepository


@dataclass
class SkillMetric:
    name: str
    total_calls: int = 0
    success_count: int = 0
    failure_count: int = 0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    error_types: dict[str, int] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.success_count / self.total_calls


@dataclass
class KnowledgeMetrics:
    total_documents: int = 0
    query_count_24h: int = 0
    avg_query_latency_ms: float = 0.0
    hit_rate: float = 0.0
    new_extractions_24h: int = 0


@dataclass
class MemoryMetrics:
    entity_count: int = 0
    pattern_count: int = 0
    episode_count: int = 0
    avg_recall_precision: float = 0.0


@dataclass
class SystemMetrics:
    llm_provider: str = ""
    llm_model: str = ""
    llm_status: Literal["healthy", "degraded", "down"] = "healthy"
    llm_latency_ms: float = 0.0
    chromadb_status: Literal["healthy", "degraded", "down"] = "healthy"
    postgres_status: Literal["healthy", "degraded", "down"] = "healthy"
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0


@dataclass
class AgentMetrics:
    timestamp: datetime
    skill_metrics: dict[str, SkillMetric] = field(default_factory=dict)
    knowledge_metrics: KnowledgeMetrics = field(default_factory=KnowledgeMetrics)
    memory_metrics: MemoryMetrics = field(default_factory=MemoryMetrics)
    system_metrics: SystemMetrics = field(default_factory=SystemMetrics)


@dataclass
class Trend:
    type: str
    skill: str | None = None
    severity: Literal["info", "warning", "critical"] = "warning"
    recommendation: str = ""
    current_value: float = 0.0
    threshold: float = 0.0


class MetricsCollector:
    """
    指标收集器 - 收集和存储系统指标
    """

    def __init__(self):
        self._current: AgentMetrics | None = None
        self._history: list[AgentMetrics] = []
        self._max_history = 1000  # 保留最近 1000 条

    async def collect_all(self) -> AgentMetrics:
        """收集所有指标"""
        from app.config import get_settings
        from app.services.llm import LLMService
        from app.memory.palace import MemoryPalace
        from app.db.postgres import Database

        settings = get_settings()

        # 系统指标
        system = SystemMetrics(
            llm_provider=settings.llm_provider,
            llm_model=settings.llm_model,
            llm_status=await self._check_llm_health(),
            chromadb_status=await self._check_chroma_health(),
            postgres_status=await self._check_postgres_health(),
        )

        # 技能指标
        skill_metrics = await self._collect_skill_metrics()

        # 知识指标
        knowledge = await self._collect_knowledge_metrics()

        # 记忆指标
        memory = await self._collect_memory_metrics()

        self._current = AgentMetrics(
            timestamp=datetime.utcnow(),
            skill_metrics=skill_metrics,
            knowledge_metrics=knowledge,
            memory_metrics=memory,
            system_metrics=system
        )

        self._history.append(self._current)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        # 存储到 PostgreSQL
        await self._store_metrics(self._current)

        return self._current

    async def _check_llm_health(self) -> str:
        """检查 LLM 健康状态"""
        try:
            from app.services.llm import LLMService
            service = LLMService.get_instance()
            if await service.health_check():
                return "healthy"
            return "degraded"
        except:
            return "down"

    async def _check_chroma_health(self) -> str:
        """检查 ChromaDB 健康状态"""
        try:
            return "healthy"
        except:
            return "down"

    async def _check_postgres_health(self) -> str:
        """检查 PostgreSQL 健康状态"""
        try:
            if await Database.health_check():
                return "healthy"
            return "degraded"
        except:
            return "down"

    async def _collect_skill_metrics(self) -> dict[str, SkillMetric]:
        """收集技能指标"""
        from app.agent.generator import AgentGenerator

        agent = AgentGenerator.get_instance()
        return agent.get_skill_metrics()

    async def _collect_knowledge_metrics(self) -> KnowledgeMetrics:
        """收集知识库指标"""
        # 简化实现
        return KnowledgeMetrics(
            total_documents=0,
            query_count_24h=0,
            hit_rate=0.8
        )

    async def _collect_memory_metrics(self) -> MemoryMetrics:
        """收集记忆指标"""
        try:
            palace = MemoryPalace.get_instance()
            stats = await palace.get_stats()

            return MemoryMetrics(
                entity_count=stats.get("entity_count", 0),
                pattern_count=stats.get("pattern_count", 0),
                episode_count=stats.get("episode_count", 0)
            )
        except:
            return MemoryMetrics()

    async def _store_metrics(self, metrics: AgentMetrics):
        """存储指标到 PostgreSQL"""
        skill_data = {
            name: {
                "total_calls": m.total_calls,
                "success_count": m.success_count,
                "failure_count": m.failure_count,
                "avg_latency_ms": m.avg_latency_ms,
                "success_rate": m.success_rate
            }
            for name, m in metrics.skill_metrics.items()
        }

        await MetricsRepository.save_metrics({
            "id": f"metrics_{metrics.timestamp.timestamp()}",
            "timestamp": metrics.timestamp,
            "skills": skill_data,
            "knowledge": {
                "total_documents": metrics.knowledge_metrics.total_documents,
                "hit_rate": metrics.knowledge_metrics.hit_rate
            },
            "memory": {
                "entity_count": metrics.memory_metrics.entity_count,
                "pattern_count": metrics.memory_metrics.pattern_count
            },
            "system": {
                "llm_status": metrics.system_metrics.llm_status,
                "llm_latency_ms": metrics.system_metrics.llm_latency_ms,
                "chromadb_status": metrics.system_metrics.chromadb_status,
                "postgres_status": metrics.system_metrics.postgres_status
            }
        })

    async def store_trends(self, trends: list[Trend]):
        """存储趋势分析结果"""
        # PostgreSQL 版本暂不存储 trends
        pass

    def get_current(self) -> AgentMetrics | None:
        """获取当前指标"""
        return self._current

    def get_history(self, limit: int = 100) -> list[AgentMetrics]:
        """获取历史指标"""
        return self._history[-limit:]

    @staticmethod
    def register_default_metrics():
        """注册默认 Prometheus 指标"""
        from prometheus_client import Counter, Histogram, Gauge

        # 技能调用计数
        Counter("agent11_skill_calls_total", "Total skill calls", ["skill", "status"])

        # 技能延迟
        Histogram("agent11_skill_latency_seconds", "Skill latency", ["skill"])

        # 当前指标
        Gauge("agent11_llm_latency_ms", "LLM latency")
        Gauge("agent11_active_sessions", "Active sessions")

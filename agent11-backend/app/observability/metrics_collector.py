"""Metrics 收集器 - Prometheus 兼容"""
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry

# 全局注册表
REGISTRY = CollectorRegistry()

# 指标定义
AGENT_REQUESTS = Counter(
    "agent11_requests_total",
    "Total agent requests",
    ["skill", "status"],
    registry=REGISTRY
)

AGENT_LATENCY = Histogram(
    "agent11_request_latency_seconds",
    "Agent request latency",
    ["skill"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
    registry=REGISTRY
)

SKILL_CALLS = Counter(
    "agent11_skill_calls_total",
    "Total skill calls",
    ["skill", "status"],
    registry=REGISTRY
)

LLM_REQUESTS = Counter(
    "agent11_llm_requests_total",
    "Total LLM requests",
    ["status"],
    registry=REGISTRY
)

LLM_LATENCY = Histogram(
    "agent11_llm_latency_seconds",
    "LLM request latency",
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
    registry=REGISTRY
)

ACTIVE_SESSIONS = Gauge(
    "agent11_active_sessions",
    "Number of active sessions",
    registry=REGISTRY
)

MEMORY_ENTITIES = Gauge(
    "agent11_memory_entities",
    "Number of memory entities",
    registry=REGISTRY
)

KNOWLEDGE_DOCS = Gauge(
    "agent11_knowledge_documents",
    "Number of knowledge documents",
    registry=REGISTRY
)


class MetricsCollector:
    """Prometheus 指标收集器"""

    @staticmethod
    def record_request(skill: str, status: str, latency: float):
        """记录请求"""
        AGENT_REQUESTS.labels(skill=skill, status=status).inc()
        AGENT_LATENCY.labels(skill=skill).observe(latency)

    @staticmethod
    def record_skill_call(skill: str, success: bool):
        """记录技能调用"""
        status = "success" if success else "failure"
        SKILL_CALLS.labels(skill=skill, status=status).inc()

    @staticmethod
    def record_llm_request(status: str, latency: float):
        """记录 LLM 请求"""
        LLM_REQUESTS.labels(status=status).inc()
        LLM_LATENCY.observe(latency)

    @staticmethod
    def set_active_sessions(count: int):
        """设置活跃会话数"""
        ACTIVE_SESSIONS.set(count)

    @staticmethod
    def set_memory_entities(count: int):
        """设置记忆实体数"""
        MEMORY_ENTITIES.set(count)

    @staticmethod
    def set_knowledge_documents(count: int):
        """设置知识文档数"""
        KNOWLEDGE_DOCS.set(count)

    @staticmethod
    def register_default_metrics():
        """注册默认指标"""
        # 指标已在模块级别注册
        pass

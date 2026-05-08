"""AGENT 11 Backend Configuration - Llama/LM Studio"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Literal


class Settings(BaseSettings):
    """Application settings"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_name: str = "AGENT 11 Backend"
    app_version: str = "0.1.0"
    debug: bool = False

    # PostgreSQL - MUST be overridden via environment variable
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "agent11"
    postgres_password: str = ""
    postgres_database: str = "agent11db"

    # ChromaDB
    chromadb_path: str = "./data/chromadb"

    # Knowledge Base
    knowledge_base_path: str = "./data/knowledge"

    # LLM - Llama/LM Studio (OpenAI-compatible API)
    llm_provider: Literal["ollama", "lmstudio"] = "lmstudio"
    llm_base_url: str = "http://localhost:1234/v1"  # LM Studio default
    llm_model: str = "qwen3.5:9b"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 4096
    llm_timeout: int = 120

    # Embeddings
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_device: str = "cpu"

    # JWT - MUST be overridden via environment variable
    secret_key: str = ""
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # APScheduler
    scheduler_timezone: str = "Asia/Shanghai"

    # Eval Harness
    eval_enabled: bool = True
    eval_sample_rate: float = 0.05  # 5% sampling in production
    eval_pass_threshold: float = 0.7

    # Loop Operator
    loop_metrics_interval_minutes: int = 5
    loop_trend_interval_hours: int = 1
    loop_optimize_interval_hours: int = 4

    # Memory Palace
    memory_max_episode_age_days: int = 365
    memory_pattern_merge_similarity: float = 0.85

    # Autonomous
    skill_monitor_interval_minutes: int = 60
    knowledge_update_cron: str = "0 2 * * *"  # Daily at 2 AM
    memory_opt_cron: str = "0 3 * * 0"  # Weekly Sunday at 3 AM


@lru_cache
def get_settings() -> Settings:
    return Settings()

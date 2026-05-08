"""ChromaDB 客户端"""
from __future__ import annotations

import chromadb
from chromadb.config import Settings
from typing import Optional
import structlog

from app.config import get_settings

logger = structlog.get_logger()

# Global ChromaDB instance
_chroma: Optional["ChromaDBClient"] = None


class ChromaDBClient:
    """ChromaDB 封装"""

    @classmethod
    async def initialize(cls) -> "ChromaDBClient":
        """初始化 ChromaDB"""
        global _chroma
        _chroma = cls()
        return _chroma

    @classmethod
    def get_instance(cls) -> "ChromaDBClient":
        """获取单例"""
        global _chroma
        if _chroma is None:
            try:
                _chroma = cls()
            except Exception as e:
                logger.error("chroma_init_failed", error=str(e))
                _chroma = None
        return _chroma

    def __init__(self):
        settings = get_settings()

        self.client = chromadb.PersistentClient(
            path=settings.chromadb_path,
            settings=Settings(anonymized_telemetry=False)
        )

        # 创建集合
        self._ensure_collections()

    def _ensure_collections(self):
        """确保必要的集合"""
        self.client.get_or_create_collection("user_knowledge")
        self.client.get_or_create_collection("internal_fault_knowledge")
        self.client.get_or_create_collection("agent_memory")
        self.client.get_or_create_collection("protocol_definitions")
        self.client.get_or_create_collection("equipment_manuals")

    async def query(
        self,
        collection_name: str,
        query: str,
        n_results: int = 5,
        where: dict | None = None
    ) -> dict:
        """查询向量"""
        try:
            collection = self.client.get_collection(collection_name)

            results = collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where
            )

            return results

        except Exception as e:
            logger.error("chroma_query_failed", error=str(e))
            return {"ids": [], "distances": [], "metadatas": [], "documents": []}

    async def add_knowledge(
        self,
        documents: list[str],
        metadata: dict | None = None
    ):
        """添加知识"""
        import uuid

        collection = self.client.get_or_create_collection("agent_memory")

        ids = [str(uuid.uuid4()) for _ in documents]

        collection.add(
            documents=documents,
            ids=ids,
            metadatas=[metadata or {} for _ in documents]
        )

        return ids

    async def add_to_collection(
        self,
        collection_name: str,
        documents: list[str],
        ids: list[str] | None = None,
        metadata: list[dict] | None = None
    ):
        """添加到指定集合"""
        import uuid

        collection = self.client.get_or_create_collection(collection_name)

        if ids is None:
            ids = [str(uuid.uuid4()) for _ in documents]

        collection.add(
            documents=documents,
            ids=ids,
            metadatas=metadata
        )

        return ids

    async def rebuild_index(self):
        """重建索引"""
        # ChromaDB 不需要显式重建索引
        # 这个方法主要用于兼容性和未来扩展
        logger.info("chroma_index_rebuild_skipped")
        pass

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            # 简单测试查询
            collection = self.client.get_collection("agent_memory")
            collection.count()
            return True
        except Exception:
            return False

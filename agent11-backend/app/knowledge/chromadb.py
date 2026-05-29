"""ChromaDB 客户端"""
from __future__ import annotations

import chromadb
from chromadb.config import Settings
from chromadb.api.types import EmbeddingFunction
from typing import Optional, List
import structlog
import os
import numpy as np
import onnxruntime as ort

from app.config import get_settings

logger = structlog.get_logger()

# Global ChromaDB instance
_chroma: Optional["ChromaDBClient"] = None

# Local ONNX model path
LOCAL_ONNX_MODEL = os.environ.get(
    "ONNX_MODEL_PATH",
    "/home/ubuntu/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2/onnx"
)


class LocalONNXEmbeddingFunction(EmbeddingFunction):
    """使用本地 ONNX 模型的 embedding 函数"""

    def __init__(self, model_path: str):
        model_file = os.path.join(model_path, "model_qint8_avx512.onnx")
        self.session = ort.InferenceSession(model_file)
        self.input_names = [i.name for i in self.session.get_inputs()]
        self.output_names = [o.name for o in self.session.get_outputs()]

        # 加载 tokenizer 相关词汇
        tokenizer_path = model_path
        self._load_tokenizer(tokenizer_path)

    def _load_tokenizer(self, tokenizer_path: str):
        """加载 tokenizer 词汇"""
        # 加载 vocab
        vocab_file = os.path.join(tokenizer_path, "vocab.txt")
        if os.path.exists(vocab_file):
            self.vocab = {}
            with open(vocab_file, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    word = line.strip()
                    self.vocab[word] = i
        else:
            self.vocab = {}

        # 加载 tokenizer.json
        import json
        tokenizer_file = os.path.join(tokenizer_path, "tokenizer.json")
        if os.path.exists(tokenizer_file):
            with open(tokenizer_file, "r", encoding="utf-8") as f:
                self.tokenizer_data = json.load(f)
        else:
            self.tokenizer_data = None

    def _tokenize(self, texts: List[str]) -> np.ndarray:
        """简单 tokenize"""
        # 使用基础 tokenize 逻辑
        max_len = 256
        input_ids = np.zeros((len(texts), max_len), dtype=np.int64)
        attention_mask = np.zeros((len(texts), max_len), dtype=np.int64)

        for i, text in enumerate(texts):
            if self.tokenizer_data:
                # 使用 tokenizer.json
                tokens = self.tokenizer_data.get("model", {}).get("vocab", {})
                # 简单的空格分词
                words = text.lower().split()
                token_ids = []
                for w in words[:max_len-2]:
                    token_ids.append(tokens.get(w, tokens.get("[UNK]", 100)))
                # 添加 [CLS] 和 [SEP]
                token_ids = [101] + token_ids + [102]
            else:
                # 回退到简单字符映射
                token_ids = [self.vocab.get(c, 0) for c in text[:max_len-2]]
                token_ids = [101] + token_ids + [102]

            for j, tid in enumerate(token_ids[:max_len]):
                input_ids[i, j] = tid
                attention_mask[i, j] = 1

        return input_ids, attention_mask

    def __call__(self, input: List[str]) -> List[List[float]]:
        """生成 embeddings"""
        input_ids, attention_mask = self._tokenize(input)

        embeddings = self.session.run(
            self.output_names,
            {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "token_type_ids": np.zeros_like(input_ids)
            }
        )

        # 返回 [CLS] 向量 (batch, seq_len, hidden) -> (batch, hidden)
        result = embeddings[0][:, 0, :].astype(np.float32)
        # L2 normalize
        norms = np.linalg.norm(result, axis=1, keepdims=True)
        result = result / (norms + 1e-8)

        return result.tolist()


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

        # 使用本地 ONNX embedding 函数
        local_onnx = LocalONNXEmbeddingFunction(LOCAL_ONNX_MODEL)

        self.client = chromadb.PersistentClient(
            path=settings.chromadb_path,
            settings=Settings(anonymized_telemetry=False)
        )

        # Store the embedding function for use in add operations
        self._embedding_function = local_onnx

        # 创建集合
        self._ensure_collections()

    def _ensure_collections(self):
        """确保必要的集合"""
        collection_names = [
            "user_knowledge",
            "internal_fault_knowledge",
            "agent_memory",
            "protocol_definitions",
            "equipment_manuals"
        ]
        for name in collection_names:
            self.client.get_or_create_collection(name)

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

            # 使用本地 embedding 函数生成查询向量
            query_embedding = self._embedding_function([query])

            results = collection.query(
                query_embeddings=query_embedding,
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
        """添加知识，使用本地 embedding 函数生成向量"""
        import uuid

        collection = self.client.get_or_create_collection("agent_memory")

        ids = [str(uuid.uuid4()) for _ in documents]

        # 使用本地 embedding 函数生成向量
        embeddings = self._embedding_function(documents)

        collection.add(
            documents=documents,
            ids=ids,
            embeddings=embeddings,
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
        """添加到指定集合，使用本地 embedding 函数生成向量"""
        import uuid

        collection = self.client.get_or_create_collection(collection_name)

        if ids is None:
            ids = [str(uuid.uuid4()) for _ in documents]

        # 使用本地 embedding 函数生成向量
        embeddings = self._embedding_function(documents)

        collection.add(
            documents=documents,
            ids=ids,
            embeddings=embeddings,
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

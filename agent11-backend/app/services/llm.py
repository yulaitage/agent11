"""LLM 服务 - Llama/LM Studio"""
from __future__ import annotations

import httpx
from typing import Literal, Optional
import structlog

from app.config import get_settings

logger = structlog.get_logger()

# Global LLM instance
_llm: Optional["LLMService"] = None


class LLMService:
    """
    LLM 服务 - 支持 Ollama 和 LM Studio (OpenAI-compatible API)
    """

    @classmethod
    async def initialize(cls) -> "LLMService":
        """初始化 LLM 服务"""
        global _llm
        _llm = cls()
        return _llm

    @classmethod
    def get_instance(cls) -> "LLMService":
        """获取单例"""
        if _llm is None:
            raise RuntimeError("LLMService not initialized")
        return _llm

    def __init__(self):
        self.settings = get_settings()
        self._config = {
            "provider": self.settings.llm_provider,
            "base_url": self.settings.llm_base_url,
            "model": self.settings.llm_model,
            "temperature": self.settings.llm_temperature,
            "max_tokens": self.settings.llm_max_tokens,
            "timeout": self.settings.llm_timeout
        }

    def get_config(self) -> dict:
        """获取当前配置"""
        return self._config.copy()

    async def invoke(
        self,
        prompt: str,
        system: bool | str = True,
        temperature: float | None = None
    ) -> str:
        """
        调用 LLM

        Args:
            prompt: 提示词
            system: True 使用默认系统提示，Fasle 不使用，传入字符串作为自定义系统提示
            temperature: 温度参数

        Returns:
            LLM 响应文本
        """
        url = f"{self._config['base_url']}/chat/completions"

        messages = []
        if system:
            system_content = (
                system
                if isinstance(system, str)
                else "你是 AGENT 11，一个智能基础设施管理 AI 助手。"
            )
            messages.append({
                "role": "system",
                "content": system_content,
            })
        messages.append({
            "role": "user",
            "content": prompt
        })

        payload = {
            "model": self._config["model"],
            "messages": messages,
            "temperature": temperature or self._config["temperature"],
            "max_tokens": self._config["max_tokens"]
        }

        try:
            async with httpx.AsyncClient(timeout=self._config["timeout"]) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()

                data = response.json()
                return data["choices"][0]["message"]["content"]

        except httpx.TimeoutException:
            logger.error("llm_timeout", url=url)
            raise TimeoutError("LLM 请求超时")

        except httpx.HTTPStatusError as e:
            logger.error("llm_http_error", status=e.response.status_code)
            raise RuntimeError(f"LLM 请求失败: {e.response.status_code}")

        except Exception as e:
            logger.error("llm_error", error=str(e))
            raise RuntimeError(f"LLM 调用失败: {str(e)}")

    async def invoke_streaming(
        self,
        prompt: str,
        system: bool = True,
        callback=None
    ):
        """流式调用 LLM"""
        url = f"{self._config['base_url']}/chat/completions"

        messages = []
        if system:
            messages.append({
                "role": "system",
                "content": "你是 AGENT 11，一个智能基础设施管理 AI 助手。"
            })
        messages.append({
            "role": "user",
            "content": prompt
        })

        payload = {
            "model": self._config["model"],
            "messages": messages,
            "temperature": self._config["temperature"],
            "max_tokens": self._config["max_tokens"],
            "stream": True
        }

        async with httpx.AsyncClient(timeout=self._config["timeout"]) as client:
            async with client.stream("POST", url, json=payload) as response:
                async for chunk in response.aiter_lines():
                    if chunk:
                        import json
                        try:
                            data = json.loads(chunk)
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                if delta.get("content"):
                                    content = delta["content"]
                                    if callback:
                                        callback(content)
                                    yield content
                        except json.JSONDecodeError:
                            continue

    async def update_config(self, updates: dict):
        """更新配置"""
        self._config.update(updates)
        logger.info("llm_config_updated", updates=updates)

    async def switch_provider(self, provider: Literal["ollama", "lmstudio"]) -> bool:
        """切换到备用 provider"""
        settings = get_settings()

        if provider == "ollama":
            base_url = "http://localhost:11434/v1"
        elif provider == "lmstudio":
            base_url = "http://localhost:1234/v1"
        else:
            return False

        # 测试连接
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    json={
                        "model": self._config["model"],
                        "messages": [{"role": "user", "content": "hi"}],
                        "max_tokens": 10
                    }
                )
                if response.status_code == 200:
                    self._config["provider"] = provider
                    self._config["base_url"] = base_url
                    logger.info("llm_provider_switched", provider=provider)
                    return True
        except Exception as e:
            logger.warning("llm_provider_switch_failed", provider=provider, error=str(e))
            return False

        return False

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.post(
                    f"{self._config['base_url']}/chat/completions",
                    json={
                        "model": self._config["model"],
                        "messages": [{"role": "user", "content": "."}],
                        "max_tokens": 1
                    }
                )
                return response.status_code == 200
        except Exception:
            return False

    async def get_available_models(self) -> list[dict]:
        """获取可用模型列表"""
        try:
            # 尝试从 /v1/models 获取
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self._config['base_url'].replace('/v1', '')}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    return data.get("models", [])
        except Exception:
            pass

        # 返回默认模型
        return [
            {"name": self._config["model"], "modified_at": ""}
        ]

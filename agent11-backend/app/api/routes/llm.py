"""LLM 配置 API"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Literal

router = APIRouter()


class LLMConfig(BaseModel):
    provider: Literal["ollama", "lmstudio"]
    base_url: str
    model: str
    temperature: float = 0.7
    timeout: int = 120


@router.get("/config")
async def get_llm_config():
    """获取当前 LLM 配置"""
    from app.services.llm import LLMService

    llm = LLMService.get_instance()
    return llm.get_config()


@router.put("/config")
async def update_llm_config(config: LLMConfig):
    """更新 LLM 配置"""
    from app.services.llm import LLMService

    llm = LLMService.get_instance()
    await llm.update_config(config.model_dump())

    return {"success": True, "config": llm.get_config()}


@router.get("/models")
async def get_available_models():
    """获取可用模型列表"""
    from app.services.llm import LLMService

    llm = LLMService.get_instance()
    models = await llm.get_available_models()

    return {"models": models}


@router.get("/connection-status")
async def check_connection():
    """检查 LLM 连接状态"""
    from app.services.llm import LLMService

    llm = LLMService.get_instance()
    healthy = await llm.health_check()

    return {
        "connected": healthy,
        "provider": llm.get_config()["provider"],
        "model": llm.get_config()["model"]
    }


@router.post("/test")
async def test_connection(config: LLMConfig):
    """测试连接"""
    from app.services.llm import LLMService

    # 临时更新配置
    llm = LLMService.get_instance()
    old_config = llm.get_config()

    await llm.update_config(config.model_dump())

    # 测试
    healthy = await llm.health_check()

    # 恢复原配置
    await llm.update_config(old_config)

    if healthy:
        return {"success": True, "message": "连接成功"}
    else:
        raise HTTPException(status_code=400, detail="连接失败")

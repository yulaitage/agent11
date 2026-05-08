"""聊天 API"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
import structlog
import uuid

from app.agent.generator import AgentGenerator
from app.db.repositories.chat import ChatRepository

logger = structlog.get_logger()

router = APIRouter()


class SendMessageRequest(BaseModel):
    message: str
    skill: str | None = None


class CreateChatRequest(BaseModel):
    title: str | None = None


@router.get("/")
async def list_chats(user_id: str = "default"):
    """列出用户的聊天"""
    chats = await ChatRepository.find_by_user(user_id=user_id, limit=50)

    return {
        "chats": [
            {
                "id": c["id"],
                "title": c.get("chat_title", "新对话"),
                "createdAt": c.get("created_at"),
                "updatedAt": c.get("updated_at")
            }
            for c in chats
        ]
    }


@router.post("/")
async def create_chat(request: CreateChatRequest, user_id: str = "default"):
    """创建新聊天"""
    chat = await ChatRepository.create({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "chat_title": request.title or "新对话",
        "messages": [],
        "archived": False,
    })

    return {
        "id": chat["id"],
        "title": chat["chat_title"]
    }


@router.get("/{chat_id}")
async def get_chat(chat_id: str):
    """获取聊天详情"""
    chat = await ChatRepository.find_by_id(chat_id)

    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    return {
        "id": chat["id"],
        "title": chat.get("chat_title"),
        "messages": chat.get("messages", []),
        "createdAt": chat.get("created_at"),
        "updatedAt": chat.get("updated_at")
    }


@router.delete("/{chat_id}")
async def delete_chat(chat_id: str):
    """删除聊天"""
    success = await ChatRepository.archive(chat_id)

    if not success:
        raise HTTPException(status_code=404, detail="Chat not found")

    return {"success": True}


@router.post("/{chat_id}/messages")
async def send_message(chat_id: str, request: SendMessageRequest, user_id: str = "default"):
    """发送消息并获取 AI 响应"""
    # 获取聊天
    chat = await ChatRepository.find_by_id(chat_id)

    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # 添加用户消息
    user_message = {
        "role": "user",
        "content": request.message,
        "skill": request.skill,
        "timestamp": datetime.utcnow().isoformat()
    }

    await ChatRepository.add_message(chat_id, user_message)

    # 调用 Agent
    agent = AgentGenerator.get_instance()

    try:
        response = await agent.execute(
            skill=request.skill,
            query=request.message,
            context={},
            user_id=user_id,
            chat_id=chat_id
        )

        # 添加 AI 响应
        assistant_message = {
            "role": "assistant",
            "content": response.answer,
            "skill": response.skill,
            "confidence": response.confidence,
            "map_data": response.map_data,
            "data": response.data,
            "sources": response.sources,
            "timestamp": datetime.utcnow().isoformat()
        }

        await ChatRepository.add_message(chat_id, assistant_message)

        return {
            "success": True,
            "message": assistant_message
        }

    except Exception as e:
        logger.error("agent_execution_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

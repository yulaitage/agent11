"""聊天 API"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from datetime import datetime
import structlog
import uuid
import json
import asyncio
import re

from app.agent.generator import AgentGenerator
from app.agent.prompt import SKILL_ROUTER_PROMPT
from app.db.repositories.chat import ChatRepository
from app.services.llm import LLMService

logger = structlog.get_logger()

router = APIRouter()


async def _llm_detect_skill_route(message: str, llm: LLMService) -> str | None:
    """
    使用 LLM 分析消息，自动路由到合适的 skill。
    返回 None 表示继续使用 general_chat。
    """
    try:
        response = await llm.invoke(
            f"用户查询: {message}\n\n请只返回技能名称（query/fault_query/troubleshoot/prediction/maintenance_report/flexible_report/general_chat），不要解释。",
            system=False,
            temperature=0.1
        )

        # 提取技能名称（处理 LLM 返回的思考过程或额外文本）
        skill = response.strip().lower()
        # 移除可能包含的思考标签内容
        skill = re.sub(r'<think>.*?', '', skill, flags=re.DOTALL).strip()
        # 取第一行或最后一个单词
        lines = skill.split('\n')
        skill = lines[-1].strip() if lines else skill.strip()
        # 如果包含引号，取引号内容
        if '"' in skill:
            skill = skill.strip('"').strip()
        if "'" in skill:
            skill = skill.strip("'").strip()
        # 如果包含中文冒号或英文冒号，提取冒号后的内容
        if '：' in skill:
            skill = skill.split('：')[-1].strip()
        if ':' in skill:
            skill = skill.split(':')[-1].strip()

        valid_skills = ["query", "troubleshoot", "prediction", "maintenance_report",
                       "flexible_report", "fault_query", "general_chat"]
        if skill not in valid_skills:
            logger.warning("llm_routing_invalid_skill", response=response[:100], extracted=skill)
            return None

        logger.info("llm_routing_success", skill=skill, original_query=message[:50])
        return skill

    except Exception as e:
        logger.warning("llm_skill_routing_failed", error=str(e))
        return None


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
    """永久删除聊天"""
    success = await ChatRepository.delete(chat_id)

    if not success:
        raise HTTPException(status_code=404, detail="Chat not found")

    return {"success": True}


class UpdateChatTitleRequest(BaseModel):
    title: str


@router.put("/{chat_id}")
async def update_chat_title(chat_id: str, request: UpdateChatTitleRequest):
    """更新聊天标题"""
    success = await ChatRepository.update_title(chat_id, request.title)

    if not success:
        raise HTTPException(status_code=404, detail="Chat not found")

    return {"success": True}


@router.post("/{chat_id}/messages/stream")
async def send_message_stream(chat_id: str, request: SendMessageRequest, user_id: str = "default"):
    """发送消息并流式返回 AI 响应（真流式）"""
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

    llm = LLMService.get_instance()

    async def event_stream():
        try:
            full_content = ""
            skill_used = request.skill or "general_chat"

            # general_chat 自动路由：使用 LLM 分析消息意图
            if skill_used == "general_chat":
                detected_skill = await _llm_detect_skill_route(request.message, llm)
                if detected_skill:
                    skill_used = detected_skill
                    agent = AgentGenerator.get_instance()
                    response = await agent.execute(
                        skill=detected_skill,
                        query=request.message,
                        context={},
                        user_id=user_id,
                        chat_id=chat_id
                    )
                    full_content = response.answer

                    assistant_message = {
                        "role": "assistant",
                        "content": full_content,
                        "skill": response.skill,
                        "confidence": response.confidence,
                        "map_data": response.map_data,
                        "data": response.data,
                        "sources": response.sources,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    await ChatRepository.add_message(chat_id, assistant_message)

                    # 流式输出
                    for i in range(0, len(full_content), 10):
                        chunk = full_content[i:i+10]
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
                        await asyncio.sleep(0.02)
                    yield f"data: {json.dumps({'type': 'done', 'message': assistant_message})}\n\n"
                    return

            # 如果有特定 skill，使用完整 agent 流程（非流式）
            if request.skill and request.skill != "general_chat":
                agent = AgentGenerator.get_instance()
                response = await agent.execute(
                    skill=request.skill,
                    query=request.message,
                    context={},
                    user_id=user_id,
                    chat_id=chat_id
                )
                full_content = response.answer

                # 立即发送完成信号
                assistant_message = {
                    "role": "assistant",
                    "content": full_content,
                    "skill": response.skill,
                    "confidence": response.confidence,
                    "map_data": response.map_data,
                    "data": response.data,
                    "sources": response.sources,
                    "timestamp": datetime.utcnow().isoformat()
                }
                await ChatRepository.add_message(chat_id, assistant_message)

                yield f"data: {json.dumps({'type': 'content', 'content': full_content})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'message': assistant_message})}\n\n"
                return

            # general_chat 使用 LLM 流式输出
            data_summary = ""
            if any(kw in request.message.lower() for kw in ["故障", "设备", "路灯", "能耗", "功率", "状态"]):
                try:
                    from app.db.postgres import Database
                    pool = Database.get_pool()
                    async with pool.acquire() as conn:
                        total = await conn.fetchval("SELECT count(*) FROM devices_info")
                        normal = await conn.fetchval("SELECT count(*) FROM devices_info WHERE status = 'normal'")
                        fault = await conn.fetchval("SELECT count(*) FROM devices_info WHERE status = 'fault'")
                        data_summary = f"\n\n## 系统实时数据\n设备概览：共 {total or 0} 台（正常 {normal or 0} | 故障 {fault or 0}）"
                except:
                    pass

            system_prompt = """你是 AGENT 11，一个智能基础设施管理 AI 助手。
回答原则：
1. 直接回答问题，不要解释你在思考什么
2. 用自然、友好的中文回答
3. 数据中涉及的具体数字、设备、区域必须准确引用
4. 保持专业、友好、简洁的语调"""

            user_prompt = f"## 用户问题\n{request.message}{data_summary}\n\n请直接回答用户问题。"

            collected = []
            in_thinking = False
            output_buffer = ""

            # 真流式调用 LLM
            async for chunk in llm.invoke_streaming(user_prompt, system=system_prompt):
                collected.append(chunk)
                # 处理思考块
                i = 0
                while i < len(chunk):
                    if chunk[i:].startswith("<think>"):
                        in_thinking = True
                        i += 7  # len("<think>")
                    elif chunk[i:].startswith("</think>"):
                        in_thinking = False
                        i += 7  # len("</think>")
                    elif not in_thinking:
                        output_buffer += chunk[i]
                        # 当缓冲区有一定内容或遇到换行时发送
                        if chunk[i] in "\n " or len(output_buffer) >= 5:
                            yield f"data: {json.dumps({'type': 'content', 'content': output_buffer})}\n\n"
                            output_buffer = ""
                        i += 1
                    else:
                        i += 1

            # 输出剩余内容
            if output_buffer:
                yield f"data: {json.dumps({'type': 'content', 'content': output_buffer})}\n\n"

            full_content = "".join(collected)
            # 过滤思考块
            import re
            full_content = re.sub(r'<think>.*?</think>', '', full_content, flags=re.DOTALL)

            # 构建并保存响应消息
            assistant_message = {
                "role": "assistant",
                "content": full_content,
                "skill": "general_chat",
                "confidence": 0.9,
                "timestamp": datetime.utcnow().isoformat()
            }
            await ChatRepository.add_message(chat_id, assistant_message)

            yield f"data: {json.dumps({'type': 'done', 'message': assistant_message})}\n\n"

        except Exception as e:
            logger.error("agent_stream_execution_failed", error=str(e))
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


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

    # 使用 LLM 自动路由：分析消息意图
    llm = LLMService.get_instance()
    skill_used = request.skill or "general_chat"
    if skill_used == "general_chat":
        detected_skill = await _llm_detect_skill_route(request.message, llm)
        if detected_skill:
            skill_used = detected_skill

    # 调用 Agent
    agent = AgentGenerator.get_instance()

    try:
        response = await agent.execute(
            skill=skill_used,
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

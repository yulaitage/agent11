"""Loop 执行器 - Loop Executor"""
import structlog
from app.harness.loop_operator.optimizer import Action, ActionResult
from app.services.llm import LLMService
from app.config import get_settings

logger = structlog.get_logger()


class LoopExecutor:
    """
    Loop 执行器 - 执行优化决策
    """

    def __init__(self):
        self.settings = get_settings()

    async def execute(self, action: Action) -> ActionResult:
        """
        执行优化行动
        """
        logger.info("executing_action", action=action.type, priority=action.priority)

        try:
            if action.type == "switch_llm_fallback":
                return await self._switch_llm_fallback()

            elif action.type == "adjust_temperature":
                return await self._adjust_temperature(action.details)

            elif action.type == "trigger_knowledge_update":
                return await self._trigger_knowledge_update()

            elif action.type == "add_knowledge":
                return await self._curate_knowledge(action)

            elif action.type == "human_review":
                return await self._request_human_review(action)

            elif action.type == "monitor":
                return ActionResult(
                    success=True,
                    message=f"继续监控: {action.reason}"
                )

            elif action.type == "rebuild_index":
                return await self._rebuild_chroma_index()

            else:
                return ActionResult(
                    success=False,
                    message=f"未知行动类型: {action.type}"
                )

        except Exception as e:
            logger.error("action_execution_failed", action=action.type, error=str(e))
            return ActionResult(
                success=False,
                message=f"执行失败: {str(e)}",
                error=str(e)
            )

    async def _switch_llm_fallback(self) -> ActionResult:
        """切换到备用 LLM 模型"""
        try:
            llm = LLMService.get_instance()
            current_config = llm.get_config()

            # 切换 provider
            if current_config["provider"] == "ollama":
                new_provider = "lmstudio"
            else:
                new_provider = "ollama"

            success = await llm.switch_provider(new_provider)

            if success:
                return ActionResult(
                    success=True,
                    message=f"已切换 LLM 提供商到 {new_provider}"
                )
            else:
                return ActionResult(
                    success=False,
                    message=f"切换失败，提供商 {new_provider} 不可用"
                )

        except Exception as e:
            return ActionResult(success=False, message=str(e), error=str(e))

    async def _adjust_temperature(self, details: dict | None) -> ActionResult:
        """调整 LLM 温度参数"""
        try:
            llm = LLMService.get_instance()
            new_temp = details.get("temperature", 0.5) if details else 0.5

            await llm.update_config({"temperature": new_temp})

            return ActionResult(
                success=True,
                message=f"已调整温度到 {new_temp}"
            )

        except Exception as e:
            return ActionResult(success=False, message=str(e), error=str(e))

    async def _trigger_knowledge_update(self) -> ActionResult:
        """触发知识更新"""
        try:
            # 触发知识提取循环
            from app.harness.autonomous.knowledge_updater import KnowledgeUpdater

            updater = KnowledgeUpdater()
            await updater.run_extraction()

            return ActionResult(
                success=True,
                message="已触发知识提取"
            )

        except Exception as e:
            return ActionResult(success=False, message=str(e), error=str(e))

    async def _curate_knowledge(self, action: Action) -> ActionResult:
        """添加知识"""
        try:
            # 记录需要专家审查的知识缺口 - 使用 ChromaDB
            from app.knowledge.chromadb import ChromaDBClient

            chroma = ChromaDBClient.get_instance()
            await chroma.add_to_collection(
                collection_name="agent_memory",
                documents=[f"Knowledge gap identified for skill: {action.skill}. Reason: {action.reason}"],
                metadata={
                    "type": "knowledge_curation",
                    "skill": action.skill,
                    "reason": action.reason,
                    "status": "pending"
                }
            )

            return ActionResult(
                success=True,
                message="已添加到知识审查队列"
            )

        except Exception as e:
            return ActionResult(success=False, message=str(e), error=str(e))

    async def _request_human_review(self, action: Action) -> ActionResult:
        """请求人工审查"""
        try:
            # 记录需要人工审查的问题 - 使用 ChromaDB
            from app.knowledge.chromadb import ChromaDBClient

            chroma = ChromaDBClient.get_instance()
            await chroma.add_to_collection(
                collection_name="agent_memory",
                documents=[f"Human review requested for skill: {action.skill}. Reason: {action.reason}"],
                metadata={
                    "type": "human_review",
                    "skill": action.skill,
                    "reason": action.reason,
                    "priority": action.priority,
                    "status": "pending"
                }
            )

            # TODO: 发送通知

            return ActionResult(
                success=True,
                message="已提交人工审查请求"
            )

        except Exception as e:
            return ActionResult(success=False, message=str(e), error=str(e))

    async def _rebuild_chroma_index(self) -> ActionResult:
        """重建 ChromaDB 索引"""
        try:
            # 清理并重建索引
            from app.knowledge.chromadb import ChromaDBClient

            client = ChromaDBClient.get_instance()
            await client.rebuild_index()

            return ActionResult(
                success=True,
                message="ChromaDB 索引已重建"
            )

        except Exception as e:
            return ActionResult(success=False, message=str(e), error=str(e))

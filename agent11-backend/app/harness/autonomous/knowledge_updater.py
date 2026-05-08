"""知识更新器 - Knowledge Updater"""
import structlog
from datetime import datetime, timedelta

logger = structlog.get_logger()


class KnowledgeUpdater:
    """
    知识更新循环 - 从已解决故障中提取新知识
    """

    EXTRACTION_PROMPT = """
分析以下已解决的故障记录，提取可用于未来诊断的知识：

设备ID: {device_id}
故障类型: {fault_type}
症状描述: {symptoms}
根本原因: {root_cause}
解决方法: {resolution}
解决时间: {response_time_hours}小时

请提取以下结构化知识（用中文）：
1. symptom_pattern: 此故障的典型表现模式
2. root_cause: 根本原因
3. fix_procedure: 修复步骤
4. related_fault_types: 可能相关的其他故障类型
5. confidence: 置信度 0-1
"""

    async def run_daily_extraction(self):
        """
        每日知识提取 - 从昨天解决的故障中提取知识
        """
        logger.info("running_daily_knowledge_extraction")

        yesterday = datetime.now() - timedelta(days=1)

        try:
            # 获取昨天解决的故障 - 使用 PostgreSQL
            from app.db.repositories.fault import FaultRepository

            resolved_faults = await FaultRepository.find_resolved_since(since=yesterday)

            logger.info("found_resolved_faults", count=len(resolved_faults))

            extracted_count = 0

            for fault in resolved_faults:
                # 检查是否已提取（通过 ChromaDB 元数据）
                if await self._is_already_extracted(fault["id"]):
                    continue

                # LLM 提取知识
                extracted = await self._extract_knowledge(fault)

                if extracted:
                    # 存储到内部知识库
                    await self._store_knowledge(extracted, fault)
                    extracted_count += 1

            logger.info("knowledge_extraction_complete", extracted=extracted_count)

            return {"extracted": extracted_count, "total": len(resolved_faults)}

        except Exception as e:
            logger.error("knowledge_extraction_failed", error=str(e))
            return {"error": str(e)}

    async def run_extraction(self):
        """手动触发提取（用于 Loop Operator）"""
        return await self.run_daily_extraction()

    async def _is_already_extracted(self, fault_id: str) -> bool:
        """检查故障是否已提取 - 使用 PostgreSQL 追踪记录"""
        from app.db.repositories.memory import MemoryRepository

        try:
            existing = await MemoryRepository.recall(
                room="memory_learning_patterns",
                entity_id=f"extracted_fault:{fault_id}",
            )
            return existing is not None
        except Exception as e:
            logger.warning("extraction_check_failed", fault_id=fault_id, error=str(e))
            return False

    async def _extract_knowledge(self, fault: dict) -> dict | None:
        """使用 LLM 提取知识"""
        try:
            from app.services.llm import LLMService

            llm = LLMService.get_instance()

            prompt = self.EXTRACTION_PROMPT.format(
                device_id=fault.get("device_id", ""),
                fault_type=fault.get("fault_type", ""),
                symptoms=fault.get("notes", ""),
                root_cause="",  # PostgreSQL 模型中可能没有这个字段
                resolution=fault.get("maintenance_action", ""),
                response_time_hours=fault.get("response_time_hours", 0)
            )

            response = await llm.invoke(prompt)

            # 解析 LLM 返回的文本，提取结构化知识
            import json
            import re

            knowledge = {
                "symptom_pattern": "",
                "root_cause": "",
                "fix_procedure": "",
                "related_fault_types": [],
                "confidence": 0.5,
            }

            # 尝试提取 JSON
            json_match = re.search(r"\{[^}]+\}", str(response), re.DOTALL)
            if json_match:
                try:
                    parsed = json.loads(json_match.group())
                    if isinstance(parsed, dict):
                        knowledge["symptom_pattern"] = parsed.get("symptom_pattern") or parsed.get("1", "")
                        knowledge["root_cause"] = parsed.get("root_cause") or parsed.get("2", "")
                        knowledge["fix_procedure"] = parsed.get("fix_procedure") or parsed.get("3", "")
                        related = parsed.get("related_fault_types") or parsed.get("4", [])
                        knowledge["related_fault_types"] = related if isinstance(related, list) else [str(related)]
                        knowledge["confidence"] = float(parsed.get("confidence", 0.5))
                except (json.JSONDecodeError, ValueError):
                    pass

            # 如果 JSON 解析失败，用正则提取各字段
            if not knowledge["symptom_pattern"]:
                labels = {
                    r"symptom_pattern[：:]\s*(.+)": "symptom_pattern",
                    r"root_cause[：:]\s*(.+)": "root_cause",
                    r"fix_procedure[：:]\s*(.+)": "fix_procedure",
                    r"related_fault_types[：:]\s*(.+)": "related_fault_types",
                }
                text = str(response)
                for pattern, key in labels.items():
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        val = match.group(1).strip()
                        if key == "related_fault_types":
                            knowledge[key] = [t.strip() for t in val.split(",") if t.strip()]
                        else:
                            knowledge[key] = val

            # 如果依然提取失败，用 LLM 回复全文作为 symptom_pattern
            if not any([knowledge["symptom_pattern"], knowledge["root_cause"], knowledge["fix_procedure"]]):
                knowledge["symptom_pattern"] = str(response)[:500]

            return knowledge

        except Exception as e:
            logger.error("knowledge_extraction_failed", fault_id=str(fault.get("id")), error=str(e))
            return None

    async def _store_knowledge(self, extracted: dict, fault: dict):
        """存储提取的知识 - ChromaDB + PostgreSQL"""
        from app.knowledge.chromadb import ChromaDBClient
        from app.db.repositories.memory import MemoryRepository

        fault_id = str(fault.get("id", ""))

        # 索引到 ChromaDB internal_fault_knowledge 集合
        try:
            chroma = ChromaDBClient.get_instance()
            await chroma.add_to_collection(
                collection_name="internal_fault_knowledge",
                documents=[
                    extracted.get("symptom_pattern", ""),
                    extracted.get("root_cause", ""),
                    extracted.get("fix_procedure", ""),
                ],
                metadata=[
                    {"source": "internal_fault", "fault_id": fault_id,
                     "fault_type": fault.get("fault_type", ""), "field": "symptom_pattern"},
                    {"source": "internal_fault", "fault_id": fault_id,
                     "fault_type": fault.get("fault_type", ""), "field": "root_cause"},
                    {"source": "internal_fault", "fault_id": fault_id,
                     "fault_type": fault.get("fault_type", ""), "field": "fix_procedure"},
                ],
            )
        except Exception as e:
            logger.error("chroma_indexing_failed", error=str(e))

        # PostgreSQL 记录提取记录（用于去重）
        try:
            await MemoryRepository.remember(
                room="memory_learning_patterns",
                entity_id=f"extracted_fault:{fault_id}",
                data={
                    "fault_id": fault_id,
                    "fault_type": fault.get("fault_type", ""),
                    "symptom_pattern": extracted.get("symptom_pattern", ""),
                    "root_cause": extracted.get("root_cause", ""),
                    "fix_procedure": extracted.get("fix_procedure", ""),
                    "related_fault_types": extracted.get("related_fault_types", []),
                    "confidence": extracted.get("confidence", 0.5),
                    "source": "knowledge_extraction",
                },
            )
        except Exception as e:
            logger.error("extraction_record_failed", fault_id=fault_id, error=str(e))

    async def verify_existing_knowledge(self, limit: int = 20):
        """验证现有知识 - ChromaDB 不支持直接更新，简化实现"""
        # ChromaDB 中的知识是只读的，验证逻辑需要重建索引
        logger.info("knowledge_verification_skipped", reason="ChromaDB is immutable")
        return {"verified": 0, "note": "ChromaDB knowledge verification not supported"}

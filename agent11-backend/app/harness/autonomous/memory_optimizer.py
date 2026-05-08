"""记忆优化器 - Memory Optimizer"""
import structlog
from datetime import datetime, timedelta

logger = structlog.get_logger()


class MemoryOptimizer:
    """
    记忆优化循环 - 维护记忆系统健康
    """

    async def run_weekly_optimization(self):
        """
        每周记忆优化
        """
        logger.info("running_weekly_memory_optimization")

        results = {
            "episodes_cleaned": 0,
            "patterns_merged": 0,
            "entities_verified": 0
        }

        try:
            from app.config import get_settings
            settings = get_settings()

            results["episodes_cleaned"] = await self.cleanup_old_episodes(settings.memory_max_episode_age_days)
            results["patterns_merged"] = await self.merge_similar_patterns(settings.memory_pattern_merge_similarity)
            results["entities_verified"] = await self.verify_entity_memories()

            logger.info("memory_optimization_complete", results=results)

        except Exception as e:
            logger.error("memory_optimization_failed", error=str(e))
            results["error"] = str(e)

        return results

    async def cleanup_old_episodes(self, max_age_days: int = 365) -> int:
        """清理过期的事件记忆 - 使用 PostgreSQL"""
        from app.db.repositories.memory import MemoryRepository

        try:
            count = await MemoryRepository.cleanup_old_memories(
                room="memory_convers_episodes",
                max_age_days=max_age_days
            )
            logger.info("episodes_cleaned", count=count)
            return count
        except Exception as e:
            logger.error("episodes_cleanup_failed", error=str(e))
            return 0

    async def merge_similar_patterns(self, similarity_threshold: float = 0.85) -> int:
        """合并相似的模式记忆 - 基于 PostgreSQL 的模式去重"""
        from app.db.repositories.memory import MemoryRepository

        try:
            # 获取所有未归档的模式
            patterns = await MemoryRepository.search(
                room="memory_learning_patterns",
                query="",
                limit=1000,
            )

            if len(patterns) < 2:
                return 0

            merged_count = 0
            processed = set()

            for i in range(len(patterns)):
                if i in processed:
                    continue
                for j in range(i + 1, len(patterns)):
                    if j in processed:
                        continue

                    p1 = patterns[i].get("data", {})
                    p2 = patterns[j].get("data", {})

                    if self._patterns_similar(p1, p2, similarity_threshold):
                        merged = self._merge_patterns(p1, p2)

                        # 归档两个旧模式
                        await MemoryRepository.archive(
                            room="memory_learning_patterns",
                            entity_id=patterns[i].get("entity_id", ""),
                        )
                        await MemoryRepository.archive(
                            room="memory_learning_patterns",
                            entity_id=patterns[j].get("entity_id", ""),
                        )

                        # 存储合并后的新模式
                        merged_entity_id = f"merged_pattern:{patterns[i].get('entity_id', '')}_{patterns[j].get('entity_id', '')}"
                        await MemoryRepository.remember(
                            room="memory_learning_patterns",
                            entity_id=merged_entity_id,
                            data=merged,
                            source="pattern_merge",
                            confidence=merged.get("confidence", 0.5),
                        )

                        processed.add(i)
                        processed.add(j)
                        merged_count += 1
                        break  # 每个模式只合并一次

            logger.info("patterns_merged", count=merged_count)
            return merged_count

        except Exception as e:
            logger.error("patterns_merge_failed", error=str(e))
            return 0

    async def verify_entity_memories(self) -> int:
        """验证实体记忆的准确性 - 使用 PostgreSQL"""
        from app.db.repositories.memory import MemoryRepository
        from app.db.repositories.device import DeviceRepository

        verified_count = 0

        try:
            # 获取所有设备记忆
            device_memories = await MemoryRepository.search(
                room="memory_infra_devices",
                query="",  # 获取所有
                limit=100
            )

            for memory in device_memories:
                entity_id = memory.get("entity_id", "")
                if not entity_id:
                    continue

                # 检查设备是否仍然存在
                device = await DeviceRepository.find_by_id(entity_id)
                if not device:
                    logger.info("stale_device_memory_found", entity_id=entity_id)
                else:
                    verified_count += 1

            logger.info("entities_verified", count=verified_count)
            return verified_count

        except Exception as e:
            logger.error("entity_verification_failed", error=str(e))
            return 0

    def _patterns_similar(
        self,
        p1: dict,
        p2: dict,
        threshold: float
    ) -> bool:
        """判断两个模式是否相似"""
        # 简化实现：检查类型和触发条件
        if p1.get("pattern_type") != p2.get("pattern_type"):
            return False

        # 检查触发条件重叠
        triggers1 = set(p1.get("trigger_conditions", []))
        triggers2 = set(p2.get("trigger_conditions", []))

        if not triggers1 or not triggers2:
            return False

        overlap = len(triggers1 & triggers2)
        union = len(triggers1 | triggers2)

        jaccard = overlap / union if union > 0 else 0

        return jaccard >= threshold

    def _merge_patterns(self, p1: dict, p2: dict) -> dict:
        """合并两个模式"""
        merged = p1.copy()

        # 合并触发条件
        triggers1 = set(p1.get("trigger_conditions", []))
        triggers2 = set(p2.get("trigger_conditions", []))
        merged["trigger_conditions"] = list(triggers1 | triggers2)

        # 保留更高置信度
        if p2.get("confidence", 0) > p1.get("confidence", 0):
            merged["confidence"] = p2["confidence"]

        # 合并典型解决方案
        resolutions = []
        if p1.get("typical_resolution"):
            resolutions.append(p1["typical_resolution"])
        if p2.get("typical_resolution"):
            resolutions.append(p2["typical_resolution"])
        merged["resolutions"] = resolutions

        return merged

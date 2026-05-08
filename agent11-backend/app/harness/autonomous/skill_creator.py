"""Skill Creator - 自动检测缺失技能并生成"""
import structlog
from datetime import datetime, timedelta
from typing import Optional

from app.config import get_settings
from app.agent.skills.skill_generator import SkillCodeGenerator, SkillAutoInstaller
from app.db.repositories.eval import EvalRepository

logger = structlog.get_logger()


class SkillCreator:
    """
    技能自动创建器

    检测场景：
    1. 评估失败时，发现缺少对应技能
    2. 用户频繁提问但没有对应技能处理
    3. 从对话历史中学习并创建新技能
    """

    def __init__(self):
        self.settings = get_settings()
        self.generator = SkillCodeGenerator()
        self.installer = SkillAutoInstaller()
        self._created_skills: list[str] = []  # 记录已创建的技能

    async def run_daily_analysis(self) -> dict:
        """
        每日分析：检查是否需要创建新技能
        """
        logger.info("running_skill_creation_analysis")

        results = {
            "skills_created": 0,
            "skill_requests_identified": 0,
            "errors": []
        }

        try:
            # 1. 分析评估失败，找缺失技能
            failed_skills = await self._analyze_failed_evals()
            results["skill_requests_identified"] += len(failed_skills)

            for skill_request in failed_skills:
                success = await self._create_skill_from_request(skill_request)
                if success:
                    results["skills_created"] += 1

            # 2. 分析对话历史，找常见需求模式
            common_patterns = await self._analyze_conversation_patterns()
            results["skill_requests_identified"] += len(common_patterns)

            for pattern in common_patterns:
                success = await self._create_skill_from_request(pattern)
                if success:
                    results["skills_created"] += 1

            logger.info("skill_creation_analysis_complete", results=results)

        except Exception as e:
            logger.error("skill_creation_analysis_failed", error=str(e))
            results["errors"].append(str(e))

        return results

    async def _analyze_failed_evals(self) -> list[dict]:
        """
        分析评估失败，找出缺失技能
        """
        skill_needs = []

        try:
            # 获取最近的评估结果
            from app.agent.skills import SkillRegistry
            registry = SkillRegistry.get_instance()

            # 检查每个技能的失败率
            from app.agent.generator import AgentGenerator
            agent = AgentGenerator.get_instance()
            metrics = agent.get_skill_metrics()

            for skill_name, metric in metrics.items():
                if metric.failure_count > metric.total_calls * 0.3:  # 失败率 > 30%
                    skill_needs.append({
                        "type": "low_quality_skill",
                        "skill": skill_name,
                        "reason": f"技能 {skill_name} 失败率 {metric.failure_count / metric.total_calls * 100:.1f}%",
                        "suggestion": f"需要改进或创建替代技能处理此类问题"
                    })

        except Exception as e:
            logger.error("failed_evals_analysis_error", error=str(e))

        return skill_needs

    async def _analyze_conversation_patterns(self) -> list[dict]:
        """
        分析对话历史，找出常见但未覆盖的需求模式
        """
        patterns = []

        try:
            # 获取最近的对话
            from app.db.repositories.chat import ChatRepository
            chats = await ChatRepository.find_by_user(limit=50)

            # 简单的关键词模式检测
            topic_keywords = {
                "water_pipe": ["水管", "水压", "漏水", "管道", "water"],
                "energy_forecast": ["能耗预测", "用电预测", "energy forecast"],
                "traffic": ["交通", "车流量", "traffic"],
                "bridge": ["桥梁", "结构", "bridge"],
                "weather": ["天气", "气象", "weather", "温度", "湿度"],
            }

            # 统计话题出现次数
            topic_counts = {k: 0 for k in topic_keywords}

            for chat in chats:
                messages = chat.get("messages", [])
                for msg in messages:
                    content = str(msg).lower()
                    for topic, keywords in topic_keywords.items():
                        if any(kw.lower() in content for kw in keywords):
                            topic_counts[topic] += 1

            # 找出高频但可能没有覆盖的话题
            registry = SkillRegistry.get_instance()
            existing_skills = registry.list()

            for topic, count in topic_counts.items():
                if count >= 3 and topic not in existing_skills:
                    patterns.append({
                        "type": "uncovered_topic",
                        "topic": topic,
                        "frequency": count,
                        "reason": f"话题 '{topic}' 在对话中出现 {count} 次但没有对应技能",
                        "suggestion": f"创建一个处理 {topic} 的技能"
                    })

        except Exception as e:
            logger.error("conversation_pattern_analysis_error", error=str(e))

        return patterns

    async def _create_skill_from_request(self, request: dict) -> bool:
        """
        根据需求创建技能

        Args:
            request: 包含 type, reason, suggestion 等字段

        Returns:
            是否成功创建
        """
        request_type = request.get("type")

        if request_type == "low_quality_skill":
            # 改进现有技能（目前只是记录）
            logger.info("skill_improvement_needed", skill=request.get("skill"))
            return False

        elif request_type == "uncovered_topic":
            # 创建新技能
            topic = request.get("topic")
            reason = request.get("reason", "")

            try:
                # 生成技能代码
                skill_def = await self.generator.generate(
                    requirement=f"处理 {topic} 相关问题。{reason}",
                    category="auto_generated"
                )

                # 安装技能
                result = await self.installer.install_generated_skill(skill_def)

                if result["status"] == "installed":
                    logger.info("new_skill_auto_created", skill=skill_def["name"])
                    self._created_skills.append(skill_def["name"])
                    return True

            except Exception as e:
                logger.error("skill_auto_creation_failed", topic=topic, error=str(e))

        return False

    async def create_skill_on_demand(
        self,
        requirement: str,
        category: str = "custom"
    ) -> dict:
        """
        按需创建技能（手动触发）

        Args:
            requirement: 技能需求描述
            category: 技能分类

        Returns:
            创建结果
        """
        logger.info("creating_skill_on_demand", requirement=requirement[:100])

        try:
            # 生成并安装
            result = await SkillCodeGenerator.generate(
                requirement=requirement,
                category=category
            )

            installer = SkillAutoInstaller()
            install_result = await installer.install_generated_skill(result)

            if install_result["status"] == "installed":
                self._created_skills.append(result["name"])

            return install_result

        except Exception as e:
            logger.error("on_demand_skill_creation_failed", error=str(e))
            return {
                "status": "failed",
                "error": str(e)
            }

    def get_created_skills(self) -> list[str]:
        """获取本次会话创建的技能列表"""
        return self._created_skills.copy()

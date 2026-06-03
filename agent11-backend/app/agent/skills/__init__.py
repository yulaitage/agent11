"""技能注册表"""
from typing import Callable, Awaitable, Any, Optional
import structlog
import ast
import asyncio

from app.agent.skills.base import BaseSkill
from app.agent.skills.query_skill import QuerySkill
from app.agent.skills.fault_query_skill import FaultQuerySkill
from app.agent.skills.troubleshoot_skill import TroubleshootSkill
from app.agent.skills.prediction_skill import PredictionSkill
from app.agent.skills.report_skill import ReportSkill
from app.agent.skills.flexible_skill import FlexibleSkill
from app.agent.skills.general_chat_skill import GeneralChatSkill
from app.db.repositories.skill import SkillRepository

logger = structlog.get_logger()

SkillFunc = Callable[..., Awaitable[dict[str, Any]]]


class SkillRegistry:
    """技能注册表 - 支持动态安装/卸载"""

    _instance: Optional["SkillRegistry"] = None

    def __init__(self):
        self._skills: dict[str, SkillFunc] = {}
        self._skill_metadata: dict[str, dict] = {}
        self._lazy_skills: dict[str, str] = {}  # Feature 3: 延迟加载的技能代码
        self._register_default_skills()
        # Set as singleton instance
        SkillRegistry._instance = self

    @classmethod
    def get_instance(cls) -> "SkillRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls):
        """重置注册表（主要用于测试）"""
        cls._instance = None

    def _register_default_skills(self):
        """注册默认内置技能"""
        default_skills = [
            ("query", QuerySkill()),
            ("fault_query", FaultQuerySkill()),
            ("troubleshoot", TroubleshootSkill()),
            ("prediction", PredictionSkill()),
            ("maintenance_report", ReportSkill()),
            ("flexible_report", FlexibleSkill()),
            ("general_chat", GeneralChatSkill()),
        ]

        for name, skill_instance in default_skills:
            self._skills[name] = skill_instance.execute
            self._skill_metadata[name] = {
                "name": name,
                "description": skill_instance.__doc__ or f"{name} skill",
                "is_builtin": True,
                "is_active": True,
            }

    def register(self, name: str, func: SkillFunc, metadata: Optional[dict] = None):
        """注册技能"""
        if name in self._skills:
            logger.warning("skill_already_registered", skill=name)
            return False

        self._skills[name] = func
        self._skill_metadata[name] = metadata or {
            "name": name,
            "description": "Custom skill",
            "is_builtin": False,
            "is_active": True,
        }
        logger.info("skill_registered", skill=name)
        return True

    def unregister(self, name: str) -> bool:
        """注销技能"""
        if name not in self._skills:
            return False

        # 检查是否是内置技能
        metadata = self._skill_metadata.get(name, {})
        if metadata.get("is_builtin"):
            logger.warning("cannot_unregister_builtin_skill", skill=name)
            return False

        del self._skills[name]
        del self._skill_metadata[name]
        logger.info("skill_unregistered", skill=name)
        return True

    def get(self, name: str) -> SkillFunc | None:
        """获取技能函数（支持延迟编译）"""
        # 先检查是否已编译
        func = self._skills.get(name)
        if func:
            return func

        # Feature 3: 延迟编译 — 如果 metadata 存在但未编译，此时编译
        code = self._lazy_skills.get(name)
        if code:
            func = self._compile_skill_code(code, name)
            if func:
                self._skills[name] = func
                del self._lazy_skills[name]
                return func

        return None

    def get_metadata(self, name: str) -> dict | None:
        """获取技能元数据"""
        return self._skill_metadata.get(name)

    def list_skills(self) -> list[str]:
        """列出所有技能名称"""
        return list(self._skills.keys())

    def list_with_metadata(self) -> list[dict]:
        """列出所有技能及其元数据"""
        return [
            {**meta, "name": name}
            for name, meta in self._skill_metadata.items()
        ]

    async def load_from_database(self):
        """从数据库加载自定义技能"""
        try:
            custom_skills = await SkillRepository.list_all(include_inactive=True)
            loaded_count = 0

            for skill_def in custom_skills:
                if not skill_def.get("is_active"):
                    continue

                success = await self.load_skill(skill_def)
                if success:
                    loaded_count += 1

            logger.info("skills_loaded_from_database", count=loaded_count)
            return loaded_count

        except Exception as e:
            logger.error("failed_to_load_skills_from_database", error=str(e))
            return 0

    async def load_skill(self, skill_def: dict) -> bool:
        """动态加载技能代码（延迟编译，首次使用时才编译）"""
        name = skill_def["name"]
        code = skill_def["code"]

        try:
            metadata = {
                "name": name,
                "description": skill_def.get("description", ""),
                "version": skill_def.get("version", "1.0.0"),
                "category": skill_def.get("category"),
                "is_builtin": False,
                "is_active": True,
            }

            # 仅编译验证语法，不保留编译结果
            try:
                compile(code, f"<skill_{name}>", "exec")
            except SyntaxError as se:
                logger.error("skill_syntax_error", skill=name, error=str(se))
                return False

            # 存储元数据和原始代码，延迟到首次 get() 时编译
            self._skill_metadata[name] = metadata
            self._lazy_skills[name] = code
            logger.info("skill_registered_lazy", skill=name)
            return True

        except Exception as e:
            logger.error("failed_to_load_skill", skill=name, error=str(e))
            return False

    def _compile_skill_code(self, code: str, skill_name: str) -> Optional[SkillFunc]:
        """编译技能代码为可执行函数"""
        try:
            # 使用 exec 动态执行代码，获取 execute 函数
            local_ns = {}

            # 添加必要的 imports
            exec_code = f"""
import asyncio
from typing import Any, Dict

async def execute_skill(llm, query, context) -> Dict[str, Any]:
{chr(10).join('    ' + line for line in code.split(chr(10)))}
"""

            exec(exec_code, local_ns)

            return local_ns.get("execute_skill")

        except Exception as e:
            logger.error("skill_compilation_failed", skill=skill_name, error=str(e))
            return None

    async def install_skill(
        self,
        name: str,
        description: str,
        code: str,
        category: str = "custom",
        parameters: dict = None,
        output_schema: dict = None,
    ) -> dict:
        """安装新技能（保存到数据库并注册）"""
        # 检查是否已存在
        if await SkillRepository.exists(name):
            raise ValueError(f"Skill '{name}' already exists")

        # 保存到数据库
        skill_def = await SkillRepository.create({
            "name": name,
            "description": description,
            "code": code,
            "category": category,
            "parameters": parameters,
            "output_schema": output_schema,
            "is_builtin": False,
            "is_active": True,
        })

        # 加载到内存
        success = await self.load_skill(skill_def)
        if not success:
            # 回滚数据库记录
            await SkillRepository.delete(name)
            raise ValueError(f"Failed to compile skill '{name}'")

        return skill_def

    async def uninstall_skill(self, name: str) -> bool:
        """卸载技能（从数据库删除并注销）"""
        # 检查是否是内置技能
        metadata = self._skill_metadata.get(name, {})
        if metadata.get("is_builtin"):
            raise ValueError(f"Cannot uninstall built-in skill '{name}'")

        # 从数据库删除
        deleted = await SkillRepository.hard_delete(name)
        if not deleted:
            return False

        # 从内存注销
        return self.unregister(name)

    async def reload_skill(self, name: str) -> bool:
        """重新加载技能"""
        skill_def = await SkillRepository.get_active(name)
        if not skill_def:
            return False

        # 如果已注册，先注销
        if name in self._skills:
            self.unregister(name)

        return await self.load_skill(skill_def)

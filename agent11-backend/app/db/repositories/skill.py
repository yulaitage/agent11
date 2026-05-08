"""Skill Repository"""
from typing import Optional
from datetime import datetime

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.skill import SkillDefinition
from app.db.session import get_session


class SkillRepository:
    """Repository for SkillDefinition model"""

    @classmethod
    async def get(cls, name: str) -> Optional[dict]:
        """获取技能定义"""
        async for session in get_session():
            result = await session.execute(
                select(SkillDefinition).where(SkillDefinition.name == name)
            )
            skill = result.scalar_one_or_none()
            if skill:
                return cls._to_dict(skill)
            return None

    @classmethod
    async def get_active(cls, name: str) -> Optional[dict]:
        """获取活跃的技能定义"""
        async for session in get_session():
            result = await session.execute(
                select(SkillDefinition).where(
                    and_(
                        SkillDefinition.name == name,
                        SkillDefinition.is_active == True
                    )
                )
            )
            skill = result.scalar_one_or_none()
            if skill:
                return cls._to_dict(skill)
            return None

    @classmethod
    async def list_all(cls, include_inactive: bool = False) -> list[dict]:
        """列出所有技能定义"""
        async for session in get_session():
            query = select(SkillDefinition)

            if not include_inactive:
                query = query.where(SkillDefinition.is_active == True)

            query = query.order_by(SkillDefinition.name)

            result = await session.execute(query)
            skills = result.scalars().all()
            return [cls._to_dict(s) for s in skills]

    @classmethod
    async def list_builtin(cls) -> list[dict]:
        """列出内置技能"""
        async for session in get_session():
            result = await session.execute(
                select(SkillDefinition).where(SkillDefinition.is_builtin == True)
            )
            skills = result.scalars().all()
            return [cls._to_dict(s) for s in skills]

    @classmethod
    async def list_custom(cls) -> list[dict]:
        """列出自定义技能"""
        async for session in get_session():
            result = await session.execute(
                select(SkillDefinition).where(SkillDefinition.is_builtin == False)
            )
            skills = result.scalars().all()
            return [cls._to_dict(s) for s in skills]

    @classmethod
    async def create(cls, skill_data: dict) -> dict:
        """创建技能定义"""
        async for session in get_session():
            skill = SkillDefinition(**skill_data)
            session.add(skill)
            await session.commit()
            await session.refresh(skill)
            return cls._to_dict(skill)

    @classmethod
    async def update(cls, name: str, updates: dict) -> Optional[dict]:
        """更新技能定义"""
        async for session in get_session():
            result = await session.execute(
                select(SkillDefinition).where(SkillDefinition.name == name)
            )
            skill = result.scalar_one_or_none()
            if not skill:
                return None

            for key, value in updates.items():
                if hasattr(skill, key):
                    setattr(skill, key, value)

            skill.updated_at = datetime.utcnow()
            await session.commit()
            await session.refresh(skill)
            return cls._to_dict(skill)

    @classmethod
    async def delete(cls, name: str) -> bool:
        """删除技能定义（软删除，设置为非活跃）"""
        async for session in get_session():
            result = await session.execute(
                select(SkillDefinition).where(SkillDefinition.name == name)
            )
            skill = result.scalar_one_or_none()
            if not skill:
                return False

            if skill.is_builtin:
                # 内置技能不能删除，只能禁用
                skill.is_active = False
            else:
                skill.is_active = False

            skill.updated_at = datetime.utcnow()
            await session.commit()
            return True

    @classmethod
    async def hard_delete(cls, name: str) -> bool:
        """硬删除技能定义（仅限非内置技能）"""
        async for session in get_session():
            result = await session.execute(
                select(SkillDefinition).where(SkillDefinition.name == name)
            )
            skill = result.scalar_one_or_none()
            if not skill:
                return False

            if skill.is_builtin:
                return False  # 内置技能不能删除

            await session.delete(skill)
            await session.commit()
            return True

    @classmethod
    async def exists(cls, name: str) -> bool:
        """检查技能是否存在"""
        async for session in get_session():
            result = await session.execute(
                select(SkillDefinition.name).where(
                    and_(
                        SkillDefinition.name == name,
                        SkillDefinition.is_active == True
                    )
                )
            )
            return result.scalar_one_or_none() is not None

    @classmethod
    def _to_dict(cls, skill: SkillDefinition) -> dict:
        """Convert skill to dict"""
        return {
            "name": skill.name,
            "description": skill.description,
            "code": skill.code,
            "version": skill.version,
            "category": skill.category,
            "parameters": skill.parameters,
            "output_schema": skill.output_schema,
            "is_builtin": skill.is_builtin,
            "is_active": skill.is_active,
            "created_at": skill.created_at,
            "updated_at": skill.updated_at,
        }

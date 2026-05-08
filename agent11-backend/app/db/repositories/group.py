"""Group Repository"""
from typing import Optional
from sqlalchemy import select
from app.db.models.group import GroupInfo
from app.db.session import get_session


class GroupRepository:
    """Repository for GroupInfo model"""

    @classmethod
    async def find_by_id(cls, group_id: int) -> Optional[dict]:
        async for session in get_session():
            result = await session.execute(
                select(GroupInfo).where(GroupInfo.id == group_id)
            )
            group = result.scalar_one_or_none()
            return cls._to_dict(group) if group else None

    @classmethod
    async def find_by_business_group_id(cls, business_group_id: str) -> Optional[dict]:
        async for session in get_session():
            result = await session.execute(
                select(GroupInfo).where(GroupInfo.businessGroupId == business_group_id)
            )
            group = result.scalar_one_or_none()
            return cls._to_dict(group) if group else None

    @classmethod
    async def find_all(cls, limit: int = 100) -> list[dict]:
        async for session in get_session():
            result = await session.execute(select(GroupInfo).limit(limit))
            groups = result.scalars().all()
            return [cls._to_dict(g) for g in groups]

    @classmethod
    def _to_dict(cls, group: GroupInfo) -> dict:
        return {
            "id": group.id,
            "businessGroupId": group.businessGroupId,
            "businessGroupName": group.businessGroupName,
            "businessGroupIdPath": group.businessGroupIdPath,
            "businessGroupNamePath": group.businessGroupNamePath,
            "parentGroupId": group.parentGroupId,
            "created_at": group.created_at,
            "updated_at": group.updated_at,
            "deleted_at": group.deleted_at,
        }

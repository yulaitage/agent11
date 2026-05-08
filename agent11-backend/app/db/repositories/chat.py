"""Chat Repository"""
from typing import Optional
from datetime import datetime

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.chat import Chat
from app.db.session import get_session


class ChatRepository:
    """Repository for Chat model"""

    @classmethod
    async def find_by_id(cls, chat_id: str) -> Optional[dict]:
        """Find chat by ID"""
        async for session in get_session():
            result = await session.execute(
                select(Chat).where(Chat.id == chat_id)
            )
            chat = result.scalar_one_or_none()
            if chat:
                return cls._to_dict(chat)
            return None

    @classmethod
    async def find_by_user(
        cls,
        user_id: str = "default",
        include_archived: bool = False,
        limit: int = 50
    ) -> list[dict]:
        """Find chats by user ID"""
        async for session in get_session():
            query = select(Chat).where(Chat.user_id == user_id)

            if not include_archived:
                query = query.where(Chat.archived == False)

            query = query.order_by(Chat.updated_at.desc()).limit(limit)

            result = await session.execute(query)
            chats = result.scalars().all()
            return [cls._to_dict(c) for c in chats]

    @classmethod
    async def create(cls, chat_data: dict) -> dict:
        """Create a new chat"""
        async for session in get_session():
            chat = Chat(**chat_data)
            session.add(chat)
            await session.commit()
            await session.refresh(chat)
            return cls._to_dict(chat)

    @classmethod
    async def update(cls, chat_id: str, updates: dict) -> Optional[dict]:
        """Update a chat"""
        async for session in get_session():
            result = await session.execute(
                select(Chat).where(Chat.id == chat_id)
            )
            chat = result.scalar_one_or_none()
            if not chat:
                return None

            for key, value in updates.items():
                if hasattr(chat, key):
                    setattr(chat, key, value)

            chat.updated_at = datetime.utcnow()
            await session.commit()
            await session.refresh(chat)
            return cls._to_dict(chat)

    @classmethod
    async def archive(cls, chat_id: str) -> bool:
        """Archive a chat"""
        async for session in get_session():
            result = await session.execute(
                select(Chat).where(Chat.id == chat_id)
            )
            chat = result.scalar_one_or_none()
            if not chat:
                return False

            chat.archived = True
            chat.updated_at = datetime.utcnow()
            await session.commit()
            return True

    @classmethod
    async def add_message(cls, chat_id: str, message: dict) -> Optional[dict]:
        """Add a message to a chat"""
        async for session in get_session():
            result = await session.execute(
                select(Chat).where(Chat.id == chat_id)
            )
            chat = result.scalar_one_or_none()
            if not chat:
                return None

            # Append message to messages array
            messages = chat.messages or []
            messages.append(message)
            chat.messages = messages
            chat.updated_at = datetime.utcnow()

            await session.commit()
            await session.refresh(chat)
            return cls._to_dict(chat)

    @classmethod
    def _to_dict(cls, chat: Chat) -> dict:
        return {
            "id": chat.id,
            "user_id": chat.user_id,
            "chat_title": chat.chat_title,
            "messages": chat.messages,
            "archived": chat.archived,
            "created_at": chat.created_at,
            "updated_at": chat.updated_at,
        }

"""Pytest configuration"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_llm():
    """Mock LLM service"""
    llm = MagicMock()
    llm.invoke = AsyncMock(return_value="Mocked LLM response")
    return llm


@pytest.fixture
def mock_context():
    """Mock conversation context"""
    from app.agent.context import ConversationContext
    return ConversationContext(
        user_id="test_user",
        chat_id="test_chat",
        skill="test",
        query="test query",
        history=[],
        context={}
    )

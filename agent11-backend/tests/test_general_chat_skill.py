"""Tests for GeneralChatSkill"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.agent.skills.general_chat_skill import GeneralChatSkill
from app.agent.context import ConversationContext


@pytest.fixture
def skill():
    return GeneralChatSkill()


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.invoke = AsyncMock(return_value="Mocked flexible response")
    return llm


@pytest.fixture
def ctx():
    return ConversationContext(
        user_id="test_user",
        chat_id="test_chat",
        skill="general_chat",
        query="test",
        history=[],
        context={}
    )


class TestOutOfScopeTopics:
    """Test that out-of-scope topics are politely rejected"""

    @pytest.mark.asyncio
    async def test_stock_topic_rejected(self, skill, mock_llm, ctx):
        result = await skill.execute(mock_llm, "帮我推荐几只股票", ctx)
        assert "超出" in result["answer"] or "范围" in result["answer"]
        assert result["confidence"] > 0.9

    @pytest.mark.asyncio
    async def test_political_topic_rejected(self, skill, mock_llm, ctx):
        result = await skill.execute(mock_llm, "你对选举怎么看", ctx)
        assert "超出" in result["answer"] or "范围" in result["answer"]

    @pytest.mark.asyncio
    async def test_gambling_topic_rejected(self, skill, mock_llm, ctx):
        result = await skill.execute(mock_llm, "赌博技巧", ctx)
        assert "超出" in result["answer"] or "范围" in result["answer"]


class TestEdgeTopics:
    """Test edge topics are briefly answered then guided back"""

    @pytest.mark.asyncio
    async def test_weather_topic_guided(self, skill, mock_llm, ctx):
        result = await skill.execute(mock_llm, "今天天气怎么样", ctx)
        # Should call LLM for a brief response + guidance
        mock_llm.invoke.assert_called()


class TestInfraRelatedQueries:
    """Test infrastructure-related queries get data-enriched or LLM responses"""

    @pytest.mark.asyncio
    @patch("app.agent.skills.general_chat_skill.DeviceRepository.count", new_callable=AsyncMock)
    async def test_device_count_query(self, mock_count, skill, mock_llm, ctx):
        mock_count.return_value = 150
        result = await skill.execute(mock_llm, "系统有多少设备", ctx)
        assert "150" in result["answer"]
        assert result["confidence"] >= 0.9

    @pytest.mark.asyncio
    @patch("app.agent.skills.general_chat_skill.DeviceRepository.count", new_callable=AsyncMock)
    async def test_introduction_query(self, mock_count, skill, mock_llm, ctx):
        mock_count.return_value = 0
        result = await skill.execute(mock_llm, "介绍一下你的功能", ctx)
        assert "AGENT 11" in result["answer"]


class TestNonInfraQueries:
    """Test non-infrastructure queries get guided back"""

    @pytest.mark.asyncio
    async def test_random_topic_guided(self, skill, mock_llm, ctx):
        result = await skill.execute(mock_llm, "讲个笑话吧", ctx)
        mock_llm.invoke.assert_called()
        assert result["confidence"] >= 0.8

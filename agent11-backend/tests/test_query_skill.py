"""Tests for QuerySkill"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.agent.skills.query_skill import QuerySkill
from app.agent.context import ConversationContext

PROTO_SPEC = '{"protocol_id": "streetlight_v1", "fields": [{"name": "voltage_v", "offset": 0, "length": 1, "type": "uint", "endian": "big", "scale": 1.0, "unit": "V"}, {"name": "current_a", "offset": 1, "length": 1, "type": "uint", "endian": "big", "scale": 0.1, "unit": "A"}]}'

PROTO_SPEC_WITH_POWER = '{"protocol_id": "streetlight_v1", "fields": [{"name": "voltage_v", "offset": 0, "length": 1, "type": "uint", "endian": "big", "scale": 1.0, "unit": "V"}, {"name": "current_a", "offset": 1, "length": 1, "type": "uint", "endian": "big", "scale": 0.1, "unit": "A"}, {"name": "power_w", "offset": 2, "length": 1, "type": "uint", "endian": "big", "scale": 1.0, "unit": "W"}, {"name": "energy_var", "offset": 3, "length": 1, "type": "uint", "endian": "big", "scale": 0.01, "unit": "kWh"}]}'


@pytest.fixture
def skill():
    return QuerySkill()


@pytest.fixture
def ctx():
    return ConversationContext(
        user_id="test_user",
        chat_id="test_chat",
        skill="query",
        query="test",
        history=[],
        context={}
    )


class TestRawPayloadDecoding:
    """Test intelligent raw payload decoding"""

    @pytest.mark.asyncio
    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.glob")
    @patch("pathlib.Path.exists")
    async def test_explicit_format_parsing(self, mock_exists, mock_glob, mock_read_text, skill, ctx):
        mock_exists.return_value = True
        mock_glob.return_value = []
        mock_read_text.return_value = PROTO_SPEC
        reasoning_chain = []
        result = await skill._try_decode_raw_payload(
            "解析原始数据 protocol_id=streetlight_v1 raw=0x0ABC",
            reasoning_chain
        )
        assert result is not None
        assert "streetlight_v1" in result["answer"]

    @pytest.mark.asyncio
    async def test_natural_language_hex_detection(self, skill, ctx):
        reasoning_chain = []
        result = await skill._try_decode_raw_payload(
            "帮我解析这段数据 0x0A1B2C3D4E5F6789",
            reasoning_chain
        )
        # Should prompt user for protocol since no protocol_id specified
        assert result is not None
        assert "协议" in result["answer"] or "未指定" in result["answer"]

    @pytest.mark.asyncio
    async def test_incomplete_raw_data_request(self, skill, ctx):
        reasoning_chain = []
        result = await skill._try_decode_raw_payload(
            "我想解析原始数据",
            reasoning_chain
        )
        assert result is not None
        assert "方式1" in result["answer"] or "提供" in result["answer"]

    @pytest.mark.asyncio
    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.glob")
    @patch("pathlib.Path.exists")
    async def test_auto_protocol_match(self, mock_exists, mock_glob, mock_read_text, skill, ctx):
        mock_exists.return_value = True
        mock_glob.return_value = []
        mock_read_text.return_value = PROTO_SPEC_WITH_POWER
        reasoning_chain = []
        result = await skill._try_decode_raw_payload(
            "解析 0x0ABC1234 使用 streetlight_v1 协议",
            reasoning_chain
        )
        assert result is not None
        assert "已按协议" in result["answer"]


class TestDomainConstraint:
    """Test domain gating in query skill"""

    @pytest.mark.asyncio
    async def test_off_topic_rejected(self, skill, ctx):
        mock_llm = MagicMock()
        result = await skill.execute(mock_llm, "今天股市行情如何", ctx)
        assert "智慧设备" in result["answer"] or "设施管理" in result["answer"]
        assert result["confidence"] >= 0.8

    @pytest.mark.asyncio
    @patch("app.agent.skills.query_skill.DeviceRepository.find_all", new_callable=AsyncMock)
    async def test_infra_query_accepted(self, mock_find, skill, ctx):
        mock_find.return_value = [
            {"deviceId": "LIGHT-01-A001", "deviceType": "streetlight", "status": "normal", "geozone": "55"}
        ]
        mock_llm = MagicMock()
        result = await skill.execute(mock_llm, "55区有多少路灯", ctx)
        assert result is not None
        assert result["confidence"] >= 0.9

"""Tests for PredictionSkill"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from app.agent.skills.prediction_skill import PredictionSkill
from app.agent.context import ConversationContext


@pytest.fixture
def skill():
    return PredictionSkill()


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.invoke = AsyncMock(return_value="Mocked LLM response")
    return llm


@pytest.fixture
def ctx():
    return ConversationContext(
        user_id="test_user",
        chat_id="test_chat",
        skill="prediction",
        query="test",
        history=[],
        context={},
    )


class TestParseTimeHorizon:
    def test_24h(self, skill):
        assert skill._parse_time_horizon("未来24小时") == "24h"
        assert skill._parse_time_horizon("明天") == "24h"
        assert skill._parse_time_horizon("1天") == "24h"

    def test_7d(self, skill):
        assert skill._parse_time_horizon("未来7天") == "7d"
        assert skill._parse_time_horizon("下周") == "7d"
        assert skill._parse_time_horizon("一周") == "7d"

    def test_30d(self, skill):
        assert skill._parse_time_horizon("未来30天") == "30d"
        assert skill._parse_time_horizon("下月") == "30d"
        assert skill._parse_time_horizon("一个月") == "30d"

    def test_default(self, skill):
        assert skill._parse_time_horizon("预测能耗") == "24h"


class TestFailureRecommendation:
    def test_fault_status_emergency(self, skill):
        result = skill._generate_failure_recommendation(0.9, "fault", 5, 10, [])
        assert "紧急" in result

    def test_high_risk(self, skill):
        result = skill._generate_failure_recommendation(0.9, "normal", 1, 1, [])
        assert "48小时" in result

    def test_comm_loss(self, skill):
        result = skill._generate_failure_recommendation(0.6, "normal", 0, 5, [])
        assert "通信" in result

    def test_many_faults(self, skill):
        result = skill._generate_failure_recommendation(0.4, "normal", 5, 0, [])
        assert "硬件" in result

    def test_low_risk(self, skill):
        result = skill._generate_failure_recommendation(0.2, "normal", 0, 0, [])
        assert "常规巡检" in result


class TestRiskChart:
    def test_build_risk_chart(self, skill):
        predictions = [
            {"device_id": "LIGHT-01", "risk_level": "极高", "risk_score": 0.9},
            {"device_id": "LIGHT-02", "risk_level": "高", "risk_score": 0.7},
            {"device_id": "LIGHT-03", "risk_level": "中", "risk_score": 0.5},
            {"device_id": "LIGHT-04", "risk_level": "低", "risk_score": 0.2},
        ]
        chart = skill._build_risk_chart(predictions)
        assert chart is not None
        assert chart["type"] == "bar"
        assert len(chart["labels"]) == 4

    def test_risk_chart_empty(self, skill):
        assert skill._build_risk_chart([]) is None


class TestFailurePredictionAnswer:
    def test_no_predictions(self, skill):
        answer = skill._generate_failure_prediction_answer([], "24h")
        assert "未发现" in answer

    def test_with_predictions(self, skill):
        predictions = [
            {"device_id": "LIGHT-01", "risk_level": "极高", "risk_score": 0.9, "factors": ["近90天故障5次"]},
            {"device_id": "LIGHT-02", "risk_level": "高", "risk_score": 0.7, "factors": ["通信丢失"]},
        ]
        answer = skill._generate_failure_prediction_answer(predictions, "7d")
        assert "7天" in answer
        assert "LIGHT-01" in answer


class TestExecuteRouting:
    @pytest.mark.asyncio
    @patch.object(PredictionSkill, "_predict_energy")
    async def test_energy_routing(self, mock_energy, skill, mock_llm, ctx):
        mock_energy.return_value = {"answer": "energy result"}
        result = await skill.execute(mock_llm, "预测未来7天能耗", ctx)
        mock_energy.assert_called_once()
        assert result["answer"] == "energy result"

    @pytest.mark.asyncio
    @patch.object(PredictionSkill, "_predict_failure")
    async def test_fault_routing(self, mock_fault, skill, mock_llm, ctx):
        mock_fault.return_value = {"answer": "fault result"}
        result = await skill.execute(mock_llm, "预测未来24小时故障", ctx)
        mock_fault.assert_called_once()
        assert result["answer"] == "fault result"

    @pytest.mark.asyncio
    @patch.object(PredictionSkill, "_predict_failure")
    async def test_default_routing(self, mock_fault, skill, mock_llm, ctx):
        mock_fault.return_value = {"answer": "default fault"}
        result = await skill.execute(mock_llm, "帮我预测一下", ctx)
        mock_fault.assert_called_once()


class TestFallbackForecast:
    def test_empty_history(self, skill):
        result = skill._fallback_energy_forecast([], "7d")
        assert result["predicted_total"] == 700.0
        assert result["method"] == "fallback"

    def test_with_history(self, skill):
        now = datetime.utcnow()
        history = []
        for i in range(10):
            day = now - timedelta(days=10 - i)
            history.append({
                "timestamp": day,
                "energy_kwh": 100.0,
            })
        result = skill._fallback_energy_forecast(history, "7d")
        assert result["predicted_total"] > 0
        assert result["method"] == "fallback"


class TestProphetFallback:
    @pytest.mark.asyncio
    async def test_prophet_insufficient_data(self, skill):
        """Less than 7 data points should return None"""
        now = datetime.utcnow()
        history = []
        for i in range(3):
            day = now - timedelta(days=3 - i)
            history.append({
                "timestamp": day,
                "energy_kwh": 100.0 + i * 10,
            })
        result = await skill._prophet_energy_forecast(history, "24h")
        assert result is None


class TestHighRiskDevices:
    @pytest.mark.asyncio
    @patch("app.agent.skills.prediction_skill.DeviceRepository.find_all")
    @patch("app.agent.skills.prediction_skill.FaultRepository.find_by_device")
    @patch("app.agent.skills.prediction_skill.CommRepository.find_by_device")
    @patch("app.agent.skills.prediction_skill.ReadingRepository.get_energy_readings")
    async def test_devices_with_risk_signals(
        self, mock_energy, mock_comm, mock_fault, mock_find_all, skill
    ):
        mock_find_all.return_value = [
            {"device_id": "LIGHT-01", "status": "normal", "geozone": "55"},
            {"device_id": "LIGHT-02", "status": "fault", "geozone": "55"},
        ]
        mock_fault.return_value = [
            {"detected_at": datetime.utcnow() - timedelta(hours=1)}
            for _ in range(5)
        ]
        mock_comm.return_value = []
        mock_energy.return_value = []

        devices = await skill._get_high_risk_devices(zone=None, limit=20)
        assert len(devices) > 0
        # LIGHT-02 has fault status → higher risk
        fault_device = [d for d in devices if d["device_id"] == "LIGHT-02"]
        if fault_device:
            assert fault_device[0]["risk_level"] in ("高", "极高")

    @pytest.mark.asyncio
    @patch("app.agent.skills.prediction_skill.DeviceRepository.find_all")
    @patch("app.agent.skills.prediction_skill.FaultRepository.find_by_device")
    @patch("app.agent.skills.prediction_skill.CommRepository.find_by_device")
    @patch("app.agent.skills.prediction_skill.ReadingRepository.get_energy_readings")
    async def test_no_devices(
        self, mock_energy, mock_comm, mock_fault, mock_find_all, skill
    ):
        mock_find_all.return_value = []
        devices = await skill._get_high_risk_devices(zone=None, limit=20)
        assert devices == []

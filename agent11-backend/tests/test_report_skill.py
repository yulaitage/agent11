"""Tests for ReportSkill"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from app.agent.skills.report_skill import ReportSkill
from app.agent.context import ConversationContext


@pytest.fixture
def skill():
    return ReportSkill()


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
        skill="maintenance_report",
        query="test",
        history=[],
        context={},
    )


class TestDetermineReportType:
    def test_weekly(self, skill):
        assert skill._determine_report_type("周报") == "weekly"
        assert skill._determine_report_type("每周报告") == "weekly"

    def test_monthly(self, skill):
        assert skill._determine_report_type("月报") == "monthly"
        assert skill._determine_report_type("月度报告") == "monthly"

    def test_annual(self, skill):
        assert skill._determine_report_type("年报") == "annual"
        assert skill._determine_report_type("年度报告") == "annual"

    def test_default(self, skill):
        assert skill._determine_report_type("报告") == "monthly"


class TestExtractZone:
    def test_zone_found(self, skill):
        zone = skill._extract_zone("55区")
        assert zone == "55"

    def test_zone_not_found(self, skill):
        zone = skill._extract_zone("所有区域")
        assert zone is None


class TestReportContent:
    def test_weekly_template(self, skill):
        data = {
            "report_type": "weekly",
            "period": "2025-01-01 至 2025-01-07",
            "total_energy_kwh": 1500.5,
            "fault_count": 3,
            "avg_response_time_hours": 2.5,
            "availability_percent": 99.5,
            "device_count": 100,
            "fault_types": {"灯具故障": 2, "通信故障": 1},
            "period_days": 7,
        }
        content = skill._generate_report_content("weekly", data, None)
        assert "Weekly" in content or "weekly" in content
        assert "1500.5" in content
        assert "3 次" in content
        assert "99.5%" in content

    def test_monthly_with_zone(self, skill):
        data = {
            "report_type": "monthly",
            "period": "2025-01-01 至 2025-01-31",
            "total_energy_kwh": 5000.0,
            "fault_count": 10,
            "avg_response_time_hours": 3.0,
            "availability_percent": 97.0,
            "device_count": 50,
            "fault_types": {"灯具故障": 5, "通信故障": 3, "电源故障": 2},
            "period_days": 31,
        }
        content = skill._generate_report_content("monthly", data, "55")
        assert "55" in content
        assert "5000.0" in content

    def test_trend_analysis(self, skill):
        data = {
            "report_type": "monthly",
            "period": "test",
            "total_energy_kwh": 1000,
            "fault_count": 15,
            "avg_response_time_hours": 2,
            "availability_percent": 85.0,
            "device_count": 100,
            "fault_types": {},
            "period_days": 30,
        }
        content = skill._generate_report_content("monthly", data, None)
        assert "可用率偏低" in content
        assert "故障次数较多" in content


class TestCollectReportData:
    @pytest.mark.asyncio
    @patch("app.agent.skills.report_skill.ReadingRepository.get_energy_readings")
    @patch("app.agent.skills.report_skill.FaultRepository.find_active")
    @patch("app.agent.skills.report_skill.DeviceRepository.count")
    async def test_monthly_data(self, mock_count, mock_faults, mock_energy, skill):
        mock_energy.return_value = [{"energy_kwh": 100.0} for _ in range(30)]
        mock_faults.return_value = [
            {
                "fault_type": "灯具故障",
                "detected_at": datetime.utcnow() - timedelta(hours=12),
                "resolved_at": datetime.utcnow() - timedelta(hours=6),
                "response_time_hours": 6,
            }
        ]
        mock_count.return_value = 100

        data = await skill._collect_report_data("monthly", zone=None)
        assert data["total_energy_kwh"] > 0
        assert data["fault_count"] > 0
        assert data["device_count"] == 100
        assert data["availability_percent"] > 0


class TestExecute:
    @pytest.mark.asyncio
    @patch.object(ReportSkill, "_collect_report_data")
    async def test_execute_weekly(self, mock_collect, skill, mock_llm, ctx):
        mock_collect.return_value = {
            "report_type": "weekly",
            "period": "test",
            "total_energy_kwh": 1000,
            "fault_count": 2,
            "avg_response_time_hours": 1.5,
            "availability_percent": 99.0,
            "device_count": 100,
            "fault_types": {"灯具故障": 2},
            "period_days": 7,
        }
        result = await skill.execute(mock_llm, "生成本周周报", ctx)
        assert result["data"]["total_energy_kwh"] == 1000
        assert result["confidence"] == 0.9

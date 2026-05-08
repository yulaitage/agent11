"""Tests for TroubleshootSkill"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from app.agent.skills.troubleshoot_skill import TroubleshootSkill
from app.agent.context import ConversationContext


@pytest.fixture
def skill():
    return TroubleshootSkill()


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
        skill="troubleshoot",
        query="test",
        history=[],
        context={},
    )


class TestRecommendation:
    def test_power_outage(self, skill):
        rec = skill._get_recommendation("电源中断")
        assert "跳闸" in rec
        assert "配电箱" in rec

    def test_controller_hw_fault(self, skill):
        rec = skill._get_recommendation("控制器硬件故障")
        assert "重启" in rec
        assert "更换控制器" in rec

    def test_network_issue(self, skill):
        rec = skill._get_recommendation("通信网络问题")
        assert "网线" in rec or "网络" in rec

    def test_lamp_fault(self, skill):
        rec = skill._get_recommendation("灯具故障或驱动损坏")
        assert "驱动" in rec or "LED" in rec

    def test_unknown(self, skill):
        rec = skill._get_recommendation("未知原因")
        assert "现场检查" in rec


class TestDiagnosisAnswer:
    def test_no_root_causes(self, skill):
        answer = skill._generate_diagnosis_answer([])
        assert "未发现" in answer

    def test_with_root_causes(self, skill):
        root_causes = [
            {
                "rank": 1,
                "cause": "电源中断",
                "zone": "55",
                "device_count": 10,
                "confidence": 0.85,
                "recommendation": "检查配电箱",
            }
        ]
        answer = skill._generate_diagnosis_answer(root_causes)
        assert "电源中断" in answer
        assert "55" in answer
        assert "检查配电箱" in answer


class TestGetCommLostDevices:
    @pytest.mark.asyncio
    @patch("app.agent.skills.troubleshoot_skill.CommRepository.find_by_event_type")
    @patch("app.agent.skills.troubleshoot_skill.DeviceRepository.find_by_id")
    async def test_comm_lost_devices_found(self, mock_find_by_id, mock_comm, skill):
        now = datetime.utcnow()
        mock_comm.return_value = [
            {"device_id": "LIGHT-01", "timestamp": now - timedelta(hours=2)},
            {"device_id": "LIGHT-02", "timestamp": now - timedelta(hours=5)},
        ]
        mock_find_by_id.side_effect = lambda did: {
            "LIGHT-01": {"device_id": "LIGHT-01", "geozone": "55", "status": "normal"},
            "LIGHT-02": {"device_id": "LIGHT-02", "geozone": "55", "status": "offline"},
        }.get(did)

        devices = await skill._get_comm_lost_devices(max_devices=500)
        assert len(devices) == 2
        assert "last_comm_loss_at" in devices[0]

    @pytest.mark.asyncio
    @patch("app.agent.skills.troubleshoot_skill.CommRepository.find_by_event_type")
    @patch("app.agent.skills.troubleshoot_skill.DeviceRepository.find_by_id")
    async def test_comm_lost_devices_empty(self, mock_find_by_id, mock_comm, skill):
        mock_comm.return_value = []
        devices = await skill._get_comm_lost_devices(max_devices=500)
        assert devices == []


class TestAnalyzeRootCauses:
    async def _make_skill_with_energy_return(self, energy_value: float):
        skill = TroubleshootSkill()
        return skill

    @pytest.mark.asyncio
    @patch("app.agent.skills.troubleshoot_skill.ReadingRepository.get_energy_readings")
    async def test_controller_hw_fault_diagnosis(self, mock_energy, skill):
        now = datetime.utcnow()
        mock_energy.return_value = [{"energy_kwh": 50.0}]

        devices = [
            {
                "device_id": "LIGHT-01",
                "geozone": "55",
                "status": "normal",
                "last_comm_loss_at": now - timedelta(hours=2),
            }
        ]
        root_causes = await skill._analyze_root_causes(devices)
        assert len(root_causes) > 0
        # Devices with energy + lights_on → controller_hw
        assert any("控制器硬件" in rc["cause"] for rc in root_causes)

    @pytest.mark.asyncio
    @patch("app.agent.skills.troubleshoot_skill.ReadingRepository.get_energy_readings")
    async def test_power_outage_diagnosis(self, mock_energy, skill):
        now = datetime.utcnow()
        mock_energy.return_value = [{"energy_kwh": 0.0}]

        devices = [
            {
                "device_id": "LIGHT-01",
                "geozone": "56",
                "status": "fault",
                "last_comm_loss_at": now - timedelta(hours=2),
            }
        ]
        root_causes = await skill._analyze_root_causes(devices)
        assert len(root_causes) > 0
        assert any("电源" in rc["cause"] for rc in root_causes)


class TestExecute:
    @pytest.mark.asyncio
    @patch("app.agent.skills.troubleshoot_skill.DeviceFaultRepository.find_recent", new_callable=AsyncMock)
    @patch("app.agent.skills.troubleshoot_skill.DeviceInfoRepository.find_by_id", new_callable=AsyncMock)
    @patch("app.agent.skills.troubleshoot_skill.DeviceRepository.find_all", new_callable=AsyncMock)
    @patch.object(TroubleshootSkill, "_get_comm_lost_devices")
    async def test_no_issues(self, mock_comm, mock_find_all, mock_info, mock_fault, skill, mock_llm, ctx):
        mock_comm.return_value = []
        mock_find_all.return_value = []
        mock_fault.return_value = []
        mock_info.return_value = None
        result = await skill.execute(mock_llm, "排查故障", ctx)
        assert "未发现" in result["answer"]

    @pytest.mark.asyncio
    @patch("app.agent.skills.troubleshoot_skill.DeviceFaultRepository.find_recent", new_callable=AsyncMock)
    @patch("app.agent.skills.troubleshoot_skill.DeviceInfoRepository.find_by_id", new_callable=AsyncMock)
    @patch("app.agent.skills.troubleshoot_skill.DeviceRepository.find_all", new_callable=AsyncMock)
    @patch.object(TroubleshootSkill, "_get_comm_lost_devices")
    @patch.object(TroubleshootSkill, "_analyze_root_causes")
    async def test_with_issues(self, mock_analyze, mock_comm, mock_find_all, mock_info, mock_fault, skill, mock_llm, ctx):
        mock_comm.return_value = [{"device_id": "LIGHT-01", "geozone": "55"}]
        mock_analyze.return_value = [
            {
                "rank": 1,
                "cause": "通信网络问题",
                "zone": "55",
                "device_count": 1,
                "confidence": 0.8,
                "recommendation": "检查网络",
            }
        ]
        mock_find_all.return_value = []
        mock_fault.return_value = []
        mock_info.return_value = None
        result = await skill.execute(mock_llm, "排查通信故障", ctx)
        assert result["confidence"] == 0.8
        assert "通信网络问题" in result["answer"]

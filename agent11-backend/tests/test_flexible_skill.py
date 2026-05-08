"""Tests for FlexibleSkill"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from app.agent.skills.flexible_skill import FlexibleSkill
from app.agent.context import ConversationContext


@pytest.fixture
def skill():
    return FlexibleSkill()


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
        skill="flexible_report",
        query="test",
        history=[],
        context={},
    )


class TestPlanQuery:
    @pytest.mark.asyncio
    async def test_energy_by_geozone(self, skill, mock_llm):
        plan = await skill._plan_query("按区域统计各区域能耗对比", mock_llm)
        assert plan["data_source"] == "energy"
        assert plan["aggregation"] == "energy_by_geozone"

    @pytest.mark.asyncio
    async def test_faults_by_geozone(self, skill, mock_llm):
        plan = await skill._plan_query("按区域统计故障数量", mock_llm)
        assert plan["data_source"] == "faults"
        assert plan["aggregation"] == "faults_by_geozone"

    @pytest.mark.asyncio
    async def test_count_by_status(self, skill, mock_llm):
        plan = await skill._plan_query("设备状态分布", mock_llm)
        assert plan["aggregation"] == "count_by_status"

    @pytest.mark.asyncio
    async def test_count_by_type(self, skill, mock_llm):
        plan = await skill._plan_query("设备类型分布", mock_llm)
        assert plan["aggregation"] == "count_by_type"

    @pytest.mark.asyncio
    async def test_trend(self, skill, mock_llm):
        plan = await skill._plan_query("能耗趋势分析", mock_llm)
        assert plan["data_source"] == "energy"
        assert plan["aggregation"] == "trend"

    @pytest.mark.asyncio
    async def test_compare(self, skill, mock_llm):
        plan = await skill._plan_query("各区域对比排名", mock_llm)
        assert plan["aggregation"] == "compare"

    @pytest.mark.asyncio
    async def test_zone_filter(self, skill, mock_llm):
        plan = await skill._plan_query("55区设备数量", mock_llm)
        assert plan["filters"].get("geozone") == "55"

    @pytest.mark.asyncio
    async def test_status_filter(self, skill, mock_llm):
        plan = await skill._plan_query("故障设备统计", mock_llm)
        assert plan["filters"].get("status") == "fault"

    @pytest.mark.asyncio
    async def test_time_range_month(self, skill, mock_llm):
        plan = await skill._plan_query("本月能耗统计", mock_llm)
        assert plan["time_range"] == "30d"

    @pytest.mark.asyncio
    async def test_health_score_aggregation(self, skill, mock_llm):
        plan = await skill._plan_query("设备健康度分布", mock_llm)
        assert plan["aggregation"] == "health_score"

    @pytest.mark.asyncio
    async def test_age_distribution(self, skill, mock_llm):
        plan = await skill._plan_query("设备年龄分布", mock_llm)
        assert plan["aggregation"] == "age_distribution"

    @pytest.mark.asyncio
    async def test_time_of_day(self, skill, mock_llm):
        plan = await skill._plan_query("24小时能耗分布", mock_llm)
        assert plan["aggregation"] == "time_of_day"
        assert plan["data_source"] == "energy"

    @pytest.mark.asyncio
    async def test_donut_chart_style(self, skill, mock_llm):
        plan = await skill._plan_query("环形图按区域统计能耗", mock_llm)
        assert plan["chart"]["type"] == "donut"

    @pytest.mark.asyncio
    async def test_horizontal_bar(self, skill, mock_llm):
        plan = await skill._plan_query("水平柱状图对比", mock_llm)
        assert plan["chart"]["type"] == "horizontal_bar"


class TestBuildChart:
    def test_bar_default(self, skill):
        base = {"labels": ["A", "B"], "values": [1, 2]}
        result = skill._build_chart(base, {"chart": {"type": "bar"}})
        assert result["type"] == "bar"
        assert "orientation" not in result

    def test_donut(self, skill):
        base = {"labels": ["A", "B"], "values": [1, 2]}
        result = skill._build_chart(base, {"chart": {"type": "donut"}})
        assert result["type"] == "donut"

    def test_horizontal_bar(self, skill):
        base = {"labels": ["A", "B"], "values": [1, 2]}
        result = skill._build_chart(base, {"chart": {"type": "horizontal_bar"}})
        assert result["type"] == "bar"
        assert result["orientation"] == "horizontal"


class TestDataOutput:
    def test_empty(self, skill):
        result = skill._generate_data_output([], {"aggregation": None})
        assert result["table"]["headers"] == []
        assert result["table"]["rows"] == []

    def test_count_by_geozone(self, skill):
        results = [
            {"device_id": "L1", "geozone": "55"},
            {"device_id": "L2", "geozone": "55"},
            {"device_id": "L3", "geozone": "56"},
        ]
        plan = {"aggregation": "count_by_geozone", "chart": {"type": "bar"}}
        output = skill._generate_data_output(results, plan)
        assert output["table"]["headers"] == ["区域", "设备数量"]
        assert len(output["table"]["rows"]) == 2

    def test_count_by_status(self, skill):
        results = [
            {"device_id": "L1", "status": "normal"},
            {"device_id": "L2", "status": "normal"},
            {"device_id": "L3", "status": "fault"},
        ]
        plan = {"aggregation": "count_by_status", "chart": {"type": "pie"}}
        output = skill._generate_data_output(results, plan)
        assert output["table"]["headers"] == ["状态", "数量"]
        rows = dict(output["table"]["rows"])
        assert rows["normal"] == "2"
        assert rows["fault"] == "1"

    def test_health_score(self, skill):
        results = [
            {"device_id": "L1", "status": "normal", "fault_count": 0},
            {"device_id": "L2", "status": "fault", "fault_count": 5},
        ]
        plan = {"aggregation": "health_score", "chart": {"type": "bar"}}
        output = skill._generate_data_output(results, plan)
        assert "健康" in output["table"]["headers"][0]

    def test_age_distribution(self, skill):
        now = datetime.utcnow()
        results = [
            {"device_id": "L1", "install_date": now.isoformat()},
            {"device_id": "L2", "install_date": (now - timedelta(days=400)).isoformat()},
            {"device_id": "L3", "install_date": (now - timedelta(days=400 * 3)).isoformat()},
        ]
        plan = {"aggregation": "age_distribution", "chart": {"type": "bar"}}
        output = skill._generate_data_output(results, plan)
        assert "使用年限" in output["table"]["headers"][0]

    def test_time_of_day(self, skill):
        now = datetime.utcnow()
        results = [
            {"timestamp": now.replace(hour=8), "energy_kwh": 10},
            {"timestamp": now.replace(hour=12), "energy_kwh": 15},
            {"timestamp": now.replace(hour=20), "energy_kwh": 25},
        ]
        plan = {"aggregation": "time_of_day", "data_source": "energy", "chart": {"type": "line"}}
        output = skill._generate_data_output(results, plan)
        assert "时段" in output["table"]["headers"][0]

    def test_default_table(self, skill):
        results = [
            {"device_id": "L1", "device_type": "streetlight", "status": "normal", "geozone": "55"},
        ]
        plan = {"aggregation": None, "includes_location": False}
        output = skill._generate_data_output(results, plan)
        assert len(output["table"]["rows"]) == 1


class TestExecute:
    @pytest.mark.asyncio
    @patch.object(FlexibleSkill, "_execute_flexible_query")
    async def test_execute_empty_results(self, mock_query, skill, mock_llm, ctx):
        mock_query.return_value = []
        result = await skill.execute(mock_llm, "55区设备", ctx)
        assert "未找到" in result["answer"]

    @pytest.mark.asyncio
    @patch.object(FlexibleSkill, "_execute_flexible_query")
    async def test_execute_with_results(self, mock_query, skill, mock_llm, ctx):
        mock_query.return_value = [
            {"device_id": "L1", "geozone": "55", "status": "normal"}
        ]
        result = await skill.execute(mock_llm, "55区设备", ctx)
        assert result["confidence"] > 0.8
        assert result["reasoning_chain"] is not None

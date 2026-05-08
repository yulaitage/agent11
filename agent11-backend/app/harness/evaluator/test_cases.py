"""测试用例管理 - 使用 PostgreSQL EvalRepository"""
from dataclasses import dataclass, field, asdict
from typing import Literal
from datetime import datetime
from app.db.repositories.eval import EvalRepository


@dataclass
class TestCase:
    """评估测试用例"""
    id: str
    skill: str
    query: str
    context: dict = field(default_factory=dict)

    # 期望输出
    expected: dict = field(default_factory=dict)
    acceptable_responses: list[str] = field(default_factory=list)

    # 元数据
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    category: str = ""
    is_regression: bool = False
    created_by: str = "system"
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class GoldenCase(TestCase):
    """专家标注的标准用例"""
    expert_annotations: dict = field(default_factory=dict)
    evaluation_notes: str = ""


class TestCaseRepository:
    """测试用例仓库 - 使用 PostgreSQL"""

    def __init__(self):
        self.repo = EvalRepository()

    async def initialize(self):
        """初始化测试用例数据"""
        # 插入默认回归测试用例
        await self._seed_regression_cases()

    async def _seed_regression_cases(self):
        """播种默认回归测试用例"""
        existing = await self.repo.find_test_cases(is_regression=True, limit=1)

        if len(existing) > 0:
            return

        # 基础回归测试用例
        default_cases = [
            TestCase(
                id="regression_query_001",
                skill="query",
                query="显示55区域所有故障路灯",
                difficulty="easy",
                category="故障查询",
                is_regression=True,
                expected={
                    "skill": "query",
                    "requires_map": True,
                    "data_fields": ["device_id", "status", "location"]
                }
            ),
            TestCase(
                id="regression_query_002",
                skill="query",
                query="55区域本月的总能耗是多少？",
                difficulty="easy",
                category="能耗查询",
                is_regression=True,
                expected={
                    "skill": "query",
                    "requires_summary": True,
                    "data_fields": ["energy_kwh"]
                }
            ),
            TestCase(
                id="regression_troubleshoot_001",
                skill="troubleshoot",
                query="分析100个设备通信中断的根本原因",
                context={"device_count": 100, "issue": "comm_loss"},
                difficulty="medium",
                category="故障诊断",
                is_regression=True,
                expected={
                    "skill": "troubleshoot",
                    "requires_reasoning": True,
                    "requires_confidence": True,
                    "requires_recommendation": True
                }
            ),
            TestCase(
                id="regression_prediction_001",
                skill="prediction",
                query="预测55区域未来7天的故障",
                context={"geozone": "55", "horizon": "7d"},
                difficulty="medium",
                category="故障预测",
                is_regression=True,
                expected={
                    "skill": "prediction",
                    "requires_risk_scores": True,
                    "requires_confidence_interval": True,
                    "requires_factors": True
                }
            ),
            TestCase(
                id="regression_report_001",
                skill="maintenance_report",
                query="生成55区域3月份月度报告",
                context={"report_type": "monthly", "month": "3", "geozone": "55"},
                difficulty="medium",
                category="报告生成",
                is_regression=True,
                expected={
                    "skill": "maintenance_report",
                    "requires_metrics": ["total_energy", "fault_count", "response_time"]
                }
            ),
            TestCase(
                id="regression_flexible_001",
                skill="flexible_report",
                query="比较55区和56区的故障率",
                difficulty="medium",
                category="对比报告",
                is_regression=True,
                expected={
                    "skill": "flexible_report",
                    "requires_comparison": True,
                    "requires_chart": True
                }
            ),
        ]

        for case in default_cases:
            await self.add(case)

    async def add(self, test_case: TestCase):
        """添加测试用例"""
        case_data = asdict(test_case)
        case_data["created_at"] = test_case.created_at
        await self.repo.create_test_case(case_data)

    async def get(self, case_id: str) -> TestCase | None:
        """获取单个测试用例"""
        case = await self.repo.get_test_case(case_id)
        if case:
            return TestCase(**case)
        return None

    async def get_test_suite(
        self,
        skill: str | None = None,
        difficulty: str | None = None
    ) -> list[TestCase]:
        """获取测试套件"""
        cases = await self.repo.find_test_cases(skill=skill, difficulty=difficulty)

        return [
            TestCase(
                id=c["id"],
                skill=c["skill"],
                query=c["query"],
                context=c.get("context", {}),
                expected=c.get("expected", {}),
                acceptable_responses=c.get("acceptable_responses", []),
                difficulty=c.get("difficulty", "medium"),
                category=c.get("category", ""),
                is_regression=c.get("is_regression", False),
                created_by=c.get("created_by", "system"),
                created_at=c.get("created_at", datetime.now())
            )
            for c in cases
        ]

    async def get_regression_suite(self) -> list[TestCase]:
        """获取回归测试套件"""
        return await self.get_test_suite(is_regression=True)

    async def get_skill_cases(self, skill: str) -> list[TestCase]:
        """获取某个技能的所有测试用例"""
        return await self.get_test_suite(skill=skill)

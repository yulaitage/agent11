"""评分标准定义 - Eval Rubric"""
from dataclasses import dataclass, field
from typing import Literal
from enum import Enum


class ScoreDimension(str, Enum):
    CORRECTNESS = "correctness"
    COMPLETENESS = "completeness"
    TIMELINESS = "timeliness"
    REASONING_QUALITY = "reasoning_quality"


@dataclass
class DimensionRubric:
    weight: float
    criteria: list[str]
    scoring_method: Literal["exact_match", "similarity", "threshold", "custom"] = "similarity"


@dataclass
class SkillRubric:
    skill: str
    dimensions: dict[str, DimensionRubric] = field(default_factory=dict)

    def get_weight(self, dimension: str) -> float:
        return self.dimensions.get(dimension, DimensionRubric(weight=0, criteria=[])).weight


# 技能评分标准
SKILL_RUBRICS: dict[str, SkillRubric] = {
    "query": SkillRubric(
        skill="query",
        dimensions={
            ScoreDimension.CORRECTNESS: DimensionRubric(
                weight=0.4,
                criteria=[
                    "返回的数据与查询条件匹配",
                    "数值计算准确",
                    "设备状态正确",
                ],
                scoring_method="similarity"
            ),
            ScoreDimension.COMPLETENESS: DimensionRubric(
                weight=0.3,
                criteria=[
                    "包含所有请求的数据字段",
                    "提供数据摘要",
                    "包含地图数据（当涉及位置时）",
                ],
                scoring_method="threshold"
            ),
            ScoreDimension.TIMELINESS: DimensionRubric(
                weight=0.1,
                criteria=["响应时间 < 10秒"],
                scoring_method="threshold"
            ),
            ScoreDimension.REASONING_QUALITY: DimensionRubric(
                weight=0.2,
                criteria=[
                    "推理链清晰可见",
                    "结论有数据支撑",
                ],
                scoring_method="similarity"
            ),
        }
    ),

    "troubleshoot": SkillRubric(
        skill="troubleshoot",
        dimensions={
            ScoreDimension.CORRECTNESS: DimensionRubric(
                weight=0.35,
                criteria=[
                    "正确识别根本原因",
                    "证据与诊断一致",
                    "不漏报",
                    "不误报",
                ],
                scoring_method="similarity"
            ),
            ScoreDimension.COMPLETENESS: DimensionRubric(
                weight=0.25,
                criteria=[
                    "提供所有可能的原因",
                    "每个原因有证据支持",
                    "包含修复建议",
                    "包含置信度",
                ],
                scoring_method="threshold"
            ),
            ScoreDimension.REASONING_QUALITY: DimensionRubric(
                weight=0.4,
                criteria=[
                    "时间关联推理正确",
                    "排除逻辑严密",
                    "推理链完整",
                ],
                scoring_method="similarity"
            ),
        }
    ),

    "prediction": SkillRubric(
        skill="prediction",
        dimensions={
            ScoreDimension.CORRECTNESS: DimensionRubric(
                weight=0.3,
                criteria=[
                    "风险评分在合理范围 (0-1)",
                    "置信区间准确",
                    "与历史模式一致",
                ],
                scoring_method="threshold"
            ),
            ScoreDimension.COMPLETENESS: DimensionRubric(
                weight=0.3,
                criteria=[
                    "列出所有高风险设备",
                    "提供风险因素",
                    "包含时间预测",
                ],
                scoring_method="threshold"
            ),
            ScoreDimension.REASONING_QUALITY: DimensionRubric(
                weight=0.4,
                criteria=[
                    "预测依据充分",
                    "因素分析合理",
                    "不确定性正确量化",
                ],
                scoring_method="similarity"
            ),
        }
    ),

    "maintenance_report": SkillRubric(
        skill="maintenance_report",
        dimensions={
            ScoreDimension.CORRECTNESS: DimensionRubric(
                weight=0.3,
                criteria=[
                    "报告类型正确",
                    "日期范围准确",
                    "指标计算正确",
                ],
                scoring_method="similarity"
            ),
            ScoreDimension.COMPLETENESS: DimensionRubric(
                weight=0.4,
                criteria=[
                    "包含所有必需指标",
                    "格式符合模板",
                    "图表完整",
                ],
                scoring_method="threshold"
            ),
            ScoreDimension.TIMELINESS: DimensionRubric(
                weight=0.1,
                criteria=["生成时间 < 30秒"],
                scoring_method="threshold"
            ),
            ScoreDimension.REASONING_QUALITY: DimensionRubric(
                weight=0.2,
                criteria=[
                    "数据解读合理",
                    "趋势分析到位",
                ],
                scoring_method="similarity"
            ),
        }
    ),

    "flexible_report": SkillRubric(
        skill="flexible_report",
        dimensions={
            ScoreDimension.CORRECTNESS: DimensionRubric(
                weight=0.35,
                criteria=[
                    "理解用户意图",
                    "返回正确的数据",
                    "格式符合要求",
                ],
                scoring_method="similarity"
            ),
            ScoreDimension.COMPLETENESS: DimensionRubric(
                weight=0.35,
                criteria=[
                    "数据完整",
                    "图表适当",
                    "包含说明",
                ],
                scoring_method="threshold"
            ),
            ScoreDimension.REASONING_QUALITY: DimensionRubric(
                weight=0.3,
                criteria=[
                    "数据展示清晰",
                    "分析有洞察",
                ],
                scoring_method="similarity"
            ),
        }
    ),
}


class RubricScorer:
    """
    评分器 - 根据 rubric 对响应进行评分
    """

    def score_response(
        self,
        skill: str,
        response: dict,
        expected: dict | None = None
    ) -> dict[str, float]:
        """
        对响应进行评分

        Returns:
            dict: {dimension: score, overall: float}
        """
        rubric = SKILL_RUBRICS.get(skill)
        if not rubric:
            return {"overall": 0.5, "error": f"Unknown skill: {skill}"}

        scores = {}

        # 按维度评分
        for dim_name, dim_rubric in rubric.dimensions.items():
            scores[dim_name] = self._score_dimension(
                dim_rubric,
                response,
                expected
            )

        # 计算加权总分
        overall = sum(
            scores[dim] * rubric.get_weight(dim)
            for dim in scores
        )

        scores["overall"] = overall

        return scores

    def _score_dimension(
        self,
        rubric: DimensionRubric,
        response: dict,
        expected: dict | None
    ) -> float:
        """对单个维度评分"""
        if rubric.scoring_method == "threshold":
            return self._score_threshold(rubric, response)
        elif rubric.scoring_method == "similarity":
            return self._score_similarity(rubric, response, expected)
        elif rubric.scoring_method == "exact_match":
            return self._score_exact(rubric, response, expected)
        return 0.5

    def _score_threshold(self, rubric: DimensionRubric, response: dict) -> float:
        """阈值评分"""
        # 简化实现：检查响应是否满足条件
        passed = len(rubric.criteria)  # 假设都通过
        total = len(rubric.criteria)
        return passed / total if total > 0 else 0.5

    def _score_similarity(
        self,
        rubric: DimensionRubric,
        response: dict,
        expected: dict | None
    ) -> float:
        """相似度评分"""
        if expected:
            # 与期望对比的相似度
            return self._calculate_similarity(response, expected)
        return 0.7  # 默认分数

    def _score_exact(
        self,
        rubric: DimensionRubric,
        response: dict,
        expected: dict | None
    ) -> float:
        """精确匹配评分"""
        if not expected:
            return 0.5
        return 1.0 if response == expected else 0.0

    def _calculate_similarity(self, a: dict, b: dict) -> float:
        """计算两个 dict 的相似度"""
        if not a or not b:
            return 0.5

        common_keys = set(a.keys()) & set(b.keys())
        if not common_keys:
            return 0.5

        matches = 0
        for key in common_keys:
            if a[key] == b[key]:
                matches += 1
            elif isinstance(a[key], (int, float)) and isinstance(b[key], (int, float)):
                # 数值型：检查是否在 10% 范围内
                if abs(a[key] - b[key]) / max(abs(b[key]), 1) < 0.1:
                    matches += 0.5

        return matches / len(common_keys)

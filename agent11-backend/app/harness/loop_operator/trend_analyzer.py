"""趋势分析器 - Trend Analyzer"""
from app.harness.loop_operator.metrics import MetricsCollector, AgentMetrics, Trend


class TrendAnalyzer:
    """
    趋势分析器 - 检测性能趋势
    """

    # 阈值配置
    SUCCESS_RATE_THRESHOLD = 0.8
    LATENCY_THRESHOLD_MS = 15000
    ERROR_RATE_THRESHOLD = 0.1

    async def analyze(
        self,
        history: list[AgentMetrics],
        window_hours: int = 24
    ) -> list[Trend]:
        """
        分析历史指标，检测趋势
        """
        if len(history) < 3:
            return []

        trends = []

        # 分析每个技能的趋势
        skills = set()
        for m in history:
            skills.update(m.skill_metrics.keys())

        for skill_name in skills:
            # 获取该技能的历史指标
            skill_history = [
                m.skill_metrics.get(skill_name)
                for m in history
                if m.skill_metrics.get(skill_name)
            ]

            if len(skill_history) < 3:
                continue

            # 检测成功率趋势
            success_trend = self._detect_trend(
                [m.success_rate for m in skill_history]
            )

            if success_trend == "declining":
                latest_rate = skill_history[-1].success_rate
                trends.append(Trend(
                    type="success_rate_decline",
                    skill=skill_name,
                    severity="warning" if latest_rate > 0.6 else "critical",
                    recommendation=f"检查 {skill_name} 技能最近的失败案例",
                    current_value=latest_rate,
                    threshold=self.SUCCESS_RATE_THRESHOLD
                ))

            # 检测延迟趋势
            latency_trend = self._detect_trend(
                [m.avg_latency_ms for m in skill_history]
            )

            if latency_trend == "increasing":
                latest_latency = skill_history[-1].avg_latency_ms
                if latest_latency > self.LATENCY_THRESHOLD_MS:
                    trends.append(Trend(
                        type="latency_increase",
                        skill=skill_name,
                        severity="critical",
                        recommendation=f"{skill_name} 延迟持续上升，考虑扩容或优化",
                        current_value=latest_latency,
                        threshold=self.LATENCY_THRESHOLD_MS
                    ))

            # 检测错误率趋势
            error_rates = [
                m.failure_count / max(m.total_calls, 1)
                for m in skill_history
            ]
            error_trend = self._detect_trend(error_rates)

            if error_trend == "increasing":
                latest_error = error_rates[-1]
                if latest_error > self.ERROR_RATE_THRESHOLD:
                    trends.append(Trend(
                        type="error_rate_increase",
                        skill=skill_name,
                        severity="critical",
                        recommendation=f"{skill_name} 错误率上升，检查错误类型分布",
                        current_value=latest_error,
                        threshold=self.ERROR_RATE_THRESHOLD
                    ))

        return trends

    def _detect_trend(self, values: list[float]) -> str:
        """
        检测趋势方向

        Returns:
            "increasing", "declining", or "stable"
        """
        if len(values) < 3:
            return "stable"

        # 简单线性回归斜率
        n = len(values)
        x = list(range(n))
        y = values

        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(x[i] * y[i] for i in range(n))
        sum_x2 = sum(xi ** 2 for xi in x)

        denominator = n * sum_x2 - sum_x * sum_x
        if denominator == 0:
            return "stable"

        slope = (n * sum_xy - sum_x * sum_y) / denominator

        # 归一化斜率
        mean_val = sum_y / n
        normalized_slope = slope / mean_val if mean_val > 0 else 0

        # 阈值
        if normalized_slope > 0.05:
            return "increasing"
        elif normalized_slope < -0.05:
            return "declining"
        return "stable"

    def detect_anomaly(self, current: float, history: list[float]) -> bool:
        """检测异常值"""
        if len(history) < 5:
            return False

        mean = sum(history) / len(history)
        variance = sum((x - mean) ** 2 for x in history) / len(history)
        std = variance ** 0.5

        # 超过 3 个标准差视为异常
        return abs(current - mean) > 3 * std

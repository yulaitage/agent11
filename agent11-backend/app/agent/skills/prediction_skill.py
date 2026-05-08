"""Prediction 技能 - 预测（Prophet 时序预测引擎）"""
from typing import Any
from datetime import datetime, timedelta
import logging

from app.agent.skills.base import BaseSkill
from app.agent.context import ConversationContext
from app.db.repositories.device import DeviceRepository
from app.db.repositories.fault import FaultRepository
from app.db.repositories.reading import ReadingRepository
from app.db.repositories.comm import CommRepository

logger = logging.getLogger(__name__)


class PredictionSkill(BaseSkill):
    """Prediction 技能 - 故障和能耗预测（Prophet 时序预测引擎）"""

    name = "prediction"

    def __init__(self):
        super().__init__()
        self._prediction_cache: dict[str, dict] = {}

    async def clear_prediction_cache(self) -> int:
        """清除预测缓存，返回清除的条目数"""
        count = len(self._prediction_cache)
        self._prediction_cache.clear()
        return count

    async def execute(
        self,
        llm: Any,
        query: str,
        context: ConversationContext
    ) -> dict[str, Any]:
        """执行预测"""
        reasoning_chain = []

        is_energy = "能耗" in query or "用电" in query
        is_fault = "故障" in query or "不亮" in query or "风险" in query

        if not is_energy and not is_fault:
            is_fault = True

        time_horizon = self._parse_time_horizon(query)

        # 检测用户是否指定了具体故障类型
        specific_fault = self._detect_fault_type_in_query(query)

        reasoning_chain.extend(await self._build_reasoning_chain([
            ("确定预测类型", f"{'能耗预测' if is_energy else '故障预测'}", "类型确定"),
            ("解析时间范围", f"预测周期: {time_horizon}", "范围确定"),
            ("故障类型检测", f"具体故障类型: {specific_fault.name_cn if specific_fault else '未指定（通用预测）'}", "检测完成")
        ]))

        if is_energy:
            return await self._predict_energy(query, time_horizon, reasoning_chain)
        elif specific_fault:
            return await self._predict_specific_fault_type(specific_fault, query, time_horizon, reasoning_chain)
        else:
            return await self._predict_failure(query, time_horizon, reasoning_chain)

    def _parse_time_horizon(self, query: str) -> str:
        if "24小时" in query or "明天" in query or "1天" in query:
            return "24h"
        elif "7天" in query or "下周" in query or "一周" in query:
            return "7d"
        elif "30天" in query or "下月" in query or "一个月" in query:
            return "30d"
        return "24h"

    # ------------------------------------------------------------------
    # 故障预测
    # ------------------------------------------------------------------
    async def _predict_failure(
        self,
        query: str,
        time_horizon: str,
        reasoning_chain: list
    ) -> dict[str, Any]:
        """预测故障（多特征模型 + Prophet 故障趋势）"""
        import re

        zone_match = re.search(r'(\d+)区', query)
        zone = zone_match.group(1) if zone_match else None

        reasoning_chain.extend(await self._build_reasoning_chain([
            ("查询设备历史", "获取设备故障、通信、能耗、维护历史", "历史数据获取完成"),
            ("多特征风险建模", "综合历史故障、通信稳定性、能耗异常、设备年龄等维度评分", "模型计算完成")
        ]))

        high_risk_devices = await self._get_high_risk_devices(zone, limit=20)
        fault_trend = await self._predict_fault_trend(zone, time_horizon)

        reasoning_chain.extend(await self._build_reasoning_chain([
            ("生成预测", f"识别 {len(high_risk_devices)} 个高风险设备", "预测完成")
        ]))

        answer = self._generate_failure_prediction_answer(
            high_risk_devices, time_horizon, fault_trend
        )
        avg_confidence = sum(d["risk_score"] for d in high_risk_devices) / len(high_risk_devices) if high_risk_devices else 0.5

        table = {
            "headers": ["设备ID", "区域", "风险评分", "风险等级", "主要因素", "建议措施"],
            "rows": [
                [
                    d["device_id"],
                    str(d.get("zone") or ""),
                    f"{d['risk_score']:.0%}",
                    d["risk_level"],
                    "；".join(d.get("factors") or []),
                    d.get("recommendation", "建议关注"),
                ]
                for d in high_risk_devices
            ],
            "total": len(high_risk_devices),
        }

        chart_data = self._build_risk_chart(high_risk_devices)

        return {
            "answer": answer,
            "reasoning_chain": reasoning_chain,
            "confidence": avg_confidence,
            "map_data": None,
            "data": {
                "predictions": high_risk_devices,
                "time_horizon": time_horizon,
                "table": table,
                "chart": chart_data,
                "fault_trend": fault_trend,
            },
            "sources": []
        }

    async def _predict_fault_trend(self, zone: str | None, time_horizon: str) -> dict | None:
        """使用 Prophet 预测故障数量趋势"""
        horizon_days = {"24h": 1, "7d": 7, "30d": 30}.get(time_horizon, 7)
        now = datetime.utcnow()
        start = now - timedelta(days=90)

        faults = await FaultRepository.find_active(geozone=zone, limit=5000)
        if not faults or len(faults) < 3:
            return None

        daily_counts: dict[str, int] = {}
        for f in faults:
            ts = f.get("detected_at")
            if ts:
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except Exception:
                        continue
                if isinstance(ts, datetime) and ts >= start:
                    day_key = ts.strftime("%Y-%m-%d")
                    daily_counts[day_key] = daily_counts.get(day_key, 0) + 1

        if len(daily_counts) < 3:
            return None

        try:
            import pandas as pd
            from prophet import Prophet

            df = pd.DataFrame([
                {"ds": k, "y": v} for k, v in sorted(daily_counts.items())
            ])
            df["ds"] = pd.to_datetime(df["ds"])

            model = Prophet(
                daily_seasonality=False,
                weekly_seasonality=True,
                yearly_seasonality=False,
                changepoint_prior_scale=0.05,
                interval_width=0.80,
            )
            model.fit(df)

            future = model.make_future_dataframe(periods=horizon_days)
            forecast = model.predict(future)

            forecast_period = forecast.tail(horizon_days)
            daily_predicted = forecast_period["yhat"].clip(lower=0).round(0).tolist()
            daily_lower = forecast_period["yhat_lower"].clip(lower=0).round(0).tolist()
            daily_upper = forecast_period["yhat_upper"].clip(lower=0).round(0).tolist()

            total_predicted = sum(daily_predicted)
            recent_avg = sum(list(daily_counts.values())[-7:]) / max(len(daily_counts), 1)

            return {
                "total_predicted": int(total_predicted),
                "daily_predictions": daily_predicted,
                "daily_lower": daily_lower,
                "daily_upper": daily_upper,
                "recent_daily_avg": round(recent_avg, 1),
            }
        except Exception as e:
            logger.warning("prophet_fault_trend_failed", exc_info=e)
            return None

    async def _get_high_risk_devices(self, zone: str | None, limit: int = 20) -> list[dict]:
        """获取高风险设备（多特征风险评分模型）"""
        devices = await DeviceRepository.find_all(geozone=zone, limit=500)
        now = datetime.utcnow()

        high_risk = []
        for device in devices:
            device_id = device.get("device_id")
            if not device_id:
                continue

            factors = []
            risk_score = 0.0

            since_90d = now - timedelta(days=90)
            recent_faults = await FaultRepository.find_by_device(device_id, limit=50)
            fault_count_90d = sum(
                1 for f in recent_faults
                if f.get("detected_at") and f["detected_at"] >= since_90d
            )
            if fault_count_90d > 0:
                risk_score += min(fault_count_90d * 0.12, 0.35)
                factors.append(f"近90天故障 {fault_count_90d} 次")

            total_faults = len(recent_faults)
            if total_faults > 3:
                risk_score += min((total_faults - 3) * 0.03, 0.15)
                if total_faults > 3:
                    factors.append(f"累计故障 {total_faults} 次")

            since_24h = now - timedelta(hours=24)
            comm_logs = await CommRepository.find_by_device(
                device_id=device_id, event_type="comm_loss", limit=200
            )
            recent_comm_loss = [
                l for l in comm_logs
                if l.get("timestamp") and l["timestamp"] >= since_24h
            ]
            comm_loss_24h = len(recent_comm_loss)
            if comm_loss_24h > 0:
                risk_score += min(comm_loss_24h * 0.08, 0.25)
                factors.append(f"近24小时通信丢失 {comm_loss_24h} 次")

            since_7d = now - timedelta(days=7)
            week_comm_loss = [
                l for l in comm_logs
                if l.get("timestamp") and l["timestamp"] >= since_7d
            ]
            if len(week_comm_loss) >= 3:
                risk_score += 0.1
                factors.append(f"近7天通信不稳定（{len(week_comm_loss)} 次丢失）")

            install_date = device.get("install_date")
            if install_date:
                if isinstance(install_date, str):
                    try:
                        install_date = datetime.fromisoformat(install_date.replace("Z", "+00:00"))
                    except Exception:
                        install_date = None
                if isinstance(install_date, datetime):
                    age_days = (now - install_date.replace(tzinfo=None)).days
                    if age_days > 365 * 3:
                        risk_score += 0.08
                        factors.append(f"设备已运行 {age_days // 365} 年，老化风险")

            last_maintenance = device.get("last_maintenance")
            if last_maintenance:
                if isinstance(last_maintenance, str):
                    try:
                        last_maintenance = datetime.fromisoformat(last_maintenance.replace("Z", "+00:00"))
                    except Exception:
                        last_maintenance = None
                if isinstance(last_maintenance, datetime):
                    days_since_maint = (now - last_maintenance.replace(tzinfo=None)).days
                    if days_since_maint > 180:
                        risk_score += 0.06
                        factors.append(f"已 {days_since_maint} 天未维护")

            status = device.get("status")
            if status == "warning":
                risk_score += 0.1
                factors.append("当前状态为警告")
            elif status == "fault":
                risk_score += 0.2
                factors.append("当前已处于故障状态")
            elif status == "offline":
                risk_score += 0.15
                factors.append("当前设备离线")

            try:
                recent_energy = await ReadingRepository.get_energy_readings(
                    device_id=device_id,
                    start_time=now - timedelta(days=7),
                    end_time=now,
                    limit=100
                )
                prev_energy = await ReadingRepository.get_energy_readings(
                    device_id=device_id,
                    start_time=now - timedelta(days=14),
                    end_time=now - timedelta(days=7),
                    limit=100
                )
                recent_sum = sum(r.get("energy_kwh", 0) for r in recent_energy)
                prev_sum = sum(r.get("energy_kwh", 0) for r in prev_energy)
                if prev_sum > 0 and recent_sum < prev_sum * 0.5:
                    risk_score += 0.12
                    factors.append("近7天能耗骤降50%以上，可能存在灯具衰减")
            except Exception:
                pass

            risk_score = min(risk_score, 0.98)

            if risk_score > 0.001:
                risk_level = "极高" if risk_score > 0.8 else "高" if risk_score > 0.6 else "中" if risk_score > 0.35 else "低"

                recommendation = self._generate_failure_recommendation(
                    risk_score, status, fault_count_90d, comm_loss_24h, factors
                )

                high_risk.append({
                    "device_id": device_id,
                    "device_type": device.get("device_type"),
                    "zone": device.get("geozone"),
                    "risk_score": risk_score,
                    "risk_level": risk_level,
                    "confidence_lower": max(risk_score - 0.1, 0.0),
                    "confidence_upper": min(risk_score + 0.1, 1.0),
                    "factors": factors,
                    "recommendation": recommendation,
                    "status": status,
                })

        high_risk.sort(key=lambda x: x["risk_score"], reverse=True)
        return high_risk[:limit]

    def _generate_failure_recommendation(
        self, risk_score: float, status: str | None,
        fault_count: int, comm_loss: int, factors: list[str]
    ) -> str:
        if status == "fault":
            return "【紧急】设备已故障，建议立即安排现场检修"
        if risk_score > 0.8:
            return "【高优先级】建议48小时内安排预防性维护，重点检查通信模块和电源"
        if comm_loss >= 3:
            return "建议检查通信链路（天线/网线/信号覆盖），必要时更换通信模组"
        if fault_count >= 2:
            return "建议全面检查设备硬件，关注电源模块和LED驱动状态"
        if risk_score > 0.5:
            return "【中优先级】建议1周内安排巡检，关注能耗和通信稳定性"
        return "建议纳入常规巡检计划，持续监控运行状态"

    def _build_risk_chart(self, predictions: list[dict]) -> dict | None:
        if not predictions:
            return None
        levels = {"极高": 0, "高": 0, "中": 0, "低": 0}
        for p in predictions:
            levels[p["risk_level"]] = levels.get(p["risk_level"], 0) + 1
        labels = [k for k, v in levels.items() if v > 0]
        values = [levels[k] for k in labels]
        colors = {"极高": "#dc2626", "高": "#f97316", "中": "#facc15", "低": "#22c55e"}
        return {
            "type": "bar",
            "title": "风险等级分布",
            "labels": labels,
            "values": values,
            "colors": [colors.get(l, "#3b82f6") for l in labels],
            "unit": "台",
        }

    def _generate_failure_prediction_answer(
        self, predictions: list[dict], time_horizon: str, fault_trend: dict | None = None
    ) -> str:
        if not predictions and not fault_trend:
            horizon_text = {"24h": "24小时", "7d": "7天", "30d": "30天"}.get(time_horizon, time_horizon)
            return f"在预测期间（未来{horizon_text}）未发现高风险设备。当前系统运行平稳。"

        horizon_text = {"24h": "24小时", "7d": "7天", "30d": "30天"}.get(time_horizon, time_horizon)

        lines = [f"未来 {horizon_text} 故障风险预测结果：\n"]

        if fault_trend:
            total = fault_trend.get("total_predicted", 0)
            daily_avg = fault_trend.get("recent_daily_avg", 0)
            lines.append(f"系统级预测：预计未来{horizon_text}将发生约 {total} 次故障")
            if daily_avg > 0:
                delta = total / max(len(predictions), 1) if predictions else 0
                lines.append(f"（近期日均 {daily_avg:.1f} 次故障）")
            lines.append("")

        if predictions:
            extreme = [p for p in predictions if p["risk_level"] == "极高"]
            high = [p for p in predictions if p["risk_level"] == "高"]
            medium = [p for p in predictions if p["risk_level"] == "中"]
            low = [p for p in predictions if p["risk_level"] == "低"]

            lines.append(f"共评估 {len(predictions)} 台设备，风险分布如下：")
            if extreme:
                lines.append(f"- 极高风险: {len(extreme)} 台")
            if high:
                lines.append(f"- 高风险: {len(high)} 台")
            if medium:
                lines.append(f"- 中风险: {len(medium)} 台")
            if low:
                lines.append(f"- 低风险: {len(low)} 台")
            lines.append("")

            if extreme:
                lines.append("极高风险设备（需立即关注）：")
                for p in extreme[:3]:
                    lines.append(f"  - {p['device_id']} | 评分 {p['risk_score']:.0%}")
                lines.append("")

            if high:
                lines.append("高风险设备（建议48小时内处理）：")
                for p in high[:5]:
                    lines.append(f"  - {p['device_id']} | 评分 {p['risk_score']:.0%}")
                lines.append("")

            lines.append("所有风险设备的详细信息和针对性建议请见下方表格。")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 能耗预测（Prophet 时序引擎）
    # ------------------------------------------------------------------
    async def _predict_energy(
        self,
        query: str,
        time_horizon: str,
        reasoning_chain: list
    ) -> dict[str, Any]:
        """预测能耗（Prophet 时序预测 + 平稳性检查与回退）"""
        import re

        zone_match = re.search(r'(\d+)区', query)
        zone = zone_match.group(1) if zone_match else None
        cache_key = f"energy:{zone}:{time_horizon}"

        # 检查缓存
        if cache_key in self._prediction_cache:
            cached = self._prediction_cache[cache_key]
            reasoning_chain.extend(await self._build_reasoning_chain([
                ("预测缓存命中", f"使用缓存的 {zone or '全局'} 能耗预测结果", "缓存命中"),
            ]))
            return cached

        reasoning_chain.extend(await self._build_reasoning_chain([
            ("查询历史能耗", "获取过去90天能耗数据用于 Prophet 时序建模", "数据获取完成"),
            ("Prophet 预测", "使用 Prophet 模型进行时序预测（含周季节性和不确定性区间）", "模型计算完成"),
        ]))

        history = await self._get_energy_history(zone, days=90)

        # 尝试 Prophet，失败时回退到确定性预测
        prophet_result = await self._prophet_energy_forecast(history, time_horizon)

        if prophet_result:
            result = prophet_result
            reasoning_chain.extend(await self._build_reasoning_chain([
                ("模型选择", "使用 Prophet 时序预测模型", "Prophet 模型完成")
            ]))
        else:
            result = self._fallback_energy_forecast(history, time_horizon)
            reasoning_chain.extend(await self._build_reasoning_chain([
                ("模型选择", "数据不足，回退到确定性趋势预测", "回退预测完成")
            ]))

        response = self._build_energy_response(result, zone, time_horizon, history, reasoning_chain)
        self._prediction_cache[cache_key] = response
        return response

    async def _prophet_energy_forecast(self, history: list[dict], time_horizon: str) -> dict | None:
        """使用 Prophet 进行能耗时序预测"""
        horizon_days = {"24h": 1, "7d": 7, "30d": 30}.get(time_horizon, 7)

        if not history or len(history) < 7:
            return None  # 数据太少，无法建模

        daily: dict[str, float] = {}
        for h in history:
            ts = h.get("timestamp") or h.get("recorded_at")
            energy = h.get("energy_kwh", 0)
            if ts:
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except Exception:
                        continue
                if isinstance(ts, datetime):
                    day_key = ts.strftime("%Y-%m-%d")
                    daily[day_key] = daily.get(day_key, 0) + energy

        if len(daily) < 7:
            return None

        try:
            import pandas as pd
            from prophet import Prophet

            df = pd.DataFrame([
                {"ds": k, "y": v} for k, v in sorted(daily.items())
            ])
            df["ds"] = pd.to_datetime(df["ds"])

            n = len(df)

            model = Prophet(
                daily_seasonality=False,
                weekly_seasonality=n >= 14,
                yearly_seasonality=False,
                changepoint_prior_scale=0.05,
                interval_width=0.80,
            )
            # 如果数据跨度为多个月，添加月度季节性的傅里叶近似
            if (df["ds"].max() - df["ds"].min()).days > 60:
                model.add_seasonality(name="monthly", period=30.5, fourier_order=3)

            model.fit(df)

            future = model.make_future_dataframe(periods=horizon_days)
            forecast = model.predict(future)

            forecast_period = forecast.tail(horizon_days)
            predicted_total = forecast_period["yhat"].clip(lower=0).sum()
            lower_total = forecast_period["yhat_lower"].clip(lower=0).sum()
            upper_total = forecast_period["yhat_upper"].clip(lower=0).sum()

            recent = df.tail(7)
            recent_avg = recent["y"].mean()

            # 趋势方向
            trend_slope = forecast["trend"].iloc[-1] - forecast["trend"].iloc[-(horizon_days + 7)]
            if trend_slope > recent_avg * 0.05:
                trend_direction = "rising"
                trend_pct = (trend_slope / max(recent_avg, 0.01)) * 100
            elif trend_slope < -recent_avg * 0.05:
                trend_direction = "falling"
                trend_pct = (trend_slope / max(recent_avg, 0.01)) * 100
            else:
                trend_direction = "stable"
                trend_pct = 0.0

            # 工作日 vs 周末
            weekday_mask = df["ds"].dt.weekday < 5
            weekday_avg = df.loc[weekday_mask, "y"].mean() if weekday_mask.any() else None
            weekend_avg = df.loc[~weekday_mask, "y"].mean() if (~weekday_mask).any() else None

            # 用于图表的历史+预测拼接
            hist_dates = df["ds"].dt.strftime("%m-%d").tolist()
            hist_values = df["y"].round(2).tolist()
            fcst_dates = forecast_period["ds"].dt.strftime("%m-%d").tolist()
            fcst_values = forecast_period["yhat"].clip(lower=0).round(2).tolist()
            fcst_lower = forecast_period["yhat_lower"].clip(lower=0).round(2).tolist()
            fcst_upper = forecast_period["yhat_upper"].clip(lower=0).round(2).tolist()

            return {
                "predicted_total": round(predicted_total, 2),
                "avg_daily": round(recent_avg, 2),
                "lower_bound": round(lower_total, 2),
                "upper_bound": round(upper_total, 2),
                "trend_direction": trend_direction,
                "trend_percent": round(trend_pct, 1),
                "weekday_avg": round(weekday_avg, 2) if weekday_avg else None,
                "weekend_avg": round(weekend_avg, 2) if weekend_avg else None,
                "method": "prophet",
                "chart_historical_dates": hist_dates[-30:],
                "chart_historical_values": hist_values[-30:],
                "chart_forecast_dates": fcst_dates,
                "chart_forecast_values": fcst_values,
                "chart_forecast_lower": fcst_lower,
                "chart_forecast_upper": fcst_upper,
            }
        except Exception as e:
            logger.warning("prophet_forecast_failed, falling back", exc_info=e)
            return None

    def _fallback_energy_forecast(self, history: list[dict], time_horizon: str) -> dict:
        """回退方案：确定性趋势预测（当 Prophet 无法使用时）"""
        from datetime import datetime

        horizon_days = {"24h": 1, "7d": 7, "30d": 30}.get(time_horizon, 7)

        daily: dict[str, float] = {}
        for h in history:
            ts = h.get("timestamp") or h.get("recorded_at")
            energy = h.get("energy_kwh", 0)
            if ts:
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except Exception:
                        continue
                if isinstance(ts, datetime):
                    day_key = ts.strftime("%Y-%m-%d")
                    daily[day_key] = daily.get(day_key, 0) + energy

        if not daily:
            return {
                "predicted_total": round(100.0 * horizon_days, 2),
                "avg_daily": 100.0,
                "lower_bound": round(100.0 * horizon_days * 0.85, 2),
                "upper_bound": round(100.0 * horizon_days * 1.15, 2),
                "trend_direction": "stable",
                "trend_percent": 0.0,
                "weekday_avg": None,
                "weekend_avg": None,
                "method": "fallback",
            }

        sorted_days = sorted(daily.keys())
        values = [daily[d] for d in sorted_days]

        recent_values = values[-30:] if len(values) >= 30 else values
        avg_daily = sum(recent_values) / len(recent_values) if recent_values else 100.0

        trend_direction = "stable"
        trend_percent = 0.0
        if len(values) >= 28:
            recent_14 = sum(values[-14:]) / 14
            prev_14 = sum(values[-28:-14]) / 14
            if prev_14 > 0:
                trend_percent = ((recent_14 - prev_14) / prev_14) * 100
                if trend_percent > 5:
                    trend_direction = "rising"
                elif trend_percent < -5:
                    trend_direction = "falling"

        trend_factor = 1.0
        if trend_direction != "stable":
            trend_factor = 1.0 + (trend_percent / 100) * 0.5

        predicted_total = avg_daily * horizon_days * trend_factor

        weekday_avg = None
        weekend_avg = None
        if len(sorted_days) >= 14:
            weekday_sum = weekday_count = 0
            weekend_sum = weekend_count = 0
            for day_key in sorted_days[-30:]:
                dt = datetime.strptime(day_key, "%Y-%m-%d")
                v = daily[day_key]
                if dt.weekday() < 5:
                    weekday_sum += v
                    weekday_count += 1
                else:
                    weekend_sum += v
                    weekend_count += 1
            weekday_avg = weekday_sum / weekday_count if weekday_count > 0 else None
            weekend_avg = weekend_sum / weekend_count if weekend_count > 0 else None

        return {
            "predicted_total": round(predicted_total, 2),
            "avg_daily": round(avg_daily, 2),
            "lower_bound": round(predicted_total * 0.85, 2),
            "upper_bound": round(predicted_total * 1.15, 2),
            "trend_direction": trend_direction,
            "trend_percent": round(trend_percent, 1),
            "weekday_avg": round(weekday_avg, 2) if weekday_avg else None,
            "weekend_avg": round(weekend_avg, 2) if weekend_avg else None,
            "method": "fallback",
        }

    def _build_energy_response(
        self,
        result: dict,
        zone: str | None,
        time_horizon: str,
        history: list[dict],
        reasoning_chain: list
    ) -> dict[str, Any]:
        """构建能耗预测响应"""
        horizon_days = {"24h": 1, "7d": 7, "30d": 30}.get(time_horizon, 7)
        horizon_text = {"24h": "24小时", "7d": "7天", "30d": "30天"}.get(time_horizon, time_horizon)

        zone_text = f"{zone}区域 " if zone else ""

        method_label = "Prophet 时序模型" if result.get("method") == "prophet" else "趋势分析模型"

        lines = [
            f"{zone_text}能耗预测（未来 {horizon_text}）：\n",
            f"模型：{method_label}",
            f"预测总能耗：{result['predicted_total']:.2f} kWh",
            f"日均能耗基准：{result['avg_daily']:.2f} kWh/天",
        ]

        td = result.get("trend_direction")
        tp = result.get("trend_percent", 0)
        if td == "rising":
            lines.append(f"趋势：近14天能耗呈上升趋势（+{tp:.1f}%），可能因季节变化或新装设备导致")
        elif td == "falling":
            lines.append(f"趋势：近14天能耗呈下降趋势（{tp:.1f}%），可能因部分设备故障或节能措施生效")
        else:
            lines.append(f"趋势：近14天能耗相对平稳（变化 {tp:+.1f}%）")

        wa = result.get("weekday_avg")
        we = result.get("weekend_avg")
        if wa and we:
            lines.append(f"工作日日均：{wa:.2f} kWh | 周末日均：{we:.2f} kWh")

        lb = result.get("lower_bound", result["predicted_total"] * 0.85)
        ub = result.get("upper_bound", result["predicted_total"] * 1.15)
        lines.append(f"80% 置信区间：[{lb:.2f}, {ub:.2f}] kWh")
        lines.append("")
        lines.append("提示：实际能耗可能受天气、季节、设备启停计划等因素影响。")

        chart_data = self._build_prophet_energy_chart(result, history)

        return {
            "answer": "\n".join(lines),
            "reasoning_chain": reasoning_chain,
            "confidence": 0.85 if result.get("method") == "prophet" else 0.7,
            "map_data": None,
            "data": {
                "predicted_energy_kwh": result["predicted_total"],
                "avg_daily_kwh": result["avg_daily"],
                "time_horizon": time_horizon,
                "confidence_interval": [lb, ub],
                "trend_direction": result.get("trend_direction"),
                "trend_percent": result.get("trend_percent"),
                "forecast_method": result.get("method", "fallback"),
                "chart": chart_data,
            },
            "sources": []
        }

    def _build_prophet_energy_chart(self, result: dict, history: list[dict]) -> dict | None:
        """构建包含预测的能耗图表"""
        if result.get("method") == "prophet" and result.get("chart_forecast_dates"):
            return {
                "type": "line",
                "title": "能耗趋势与预测",
                "labels": (result["chart_historical_dates"] + result["chart_forecast_dates"])[-34:],
                "values": (result["chart_historical_values"] + result["chart_forecast_values"])[-34:],
                "forecast_upper": (result["chart_historical_values"][-1:] + result["chart_forecast_upper"])[-horizon:] if (horizon := len(result["chart_forecast_dates"])) else None,
                "forecast_lower": (result["chart_historical_values"][-1:] + result["chart_forecast_lower"])[-horizon:] if (horizon := len(result["chart_forecast_dates"])) else None,
                "unit": "kWh",
                "has_forecast": True,
            }

        from datetime import datetime
        if not history:
            return None

        daily: dict[str, float] = {}
        for h in history:
            ts = h.get("timestamp") or h.get("recorded_at")
            energy = h.get("energy_kwh", 0)
            if ts:
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except Exception:
                        continue
                if isinstance(ts, datetime):
                    day_key = ts.strftime("%m-%d")
                    daily[day_key] = daily.get(day_key, 0) + energy

        if len(daily) < 3:
            return None

        sorted_days = sorted(daily.keys())[-14:]
        return {
            "type": "line",
            "title": "近14天能耗趋势",
            "labels": sorted_days,
            "values": [daily[d] for d in sorted_days],
            "unit": "kWh",
            "has_forecast": False,
        }

    async def _get_energy_history(self, zone: str | None, days: int = 90) -> list[dict]:
        start_time = datetime.utcnow() - timedelta(days=days)
        history = await ReadingRepository.get_energy_readings(
            geozone=zone,
            start_time=start_time,
            limit=days * 24
        )
        return history

    # ------------------------------------------------------------------
    # 具体故障类型预测
    # ------------------------------------------------------------------

    def _detect_fault_type_in_query(self, query: str) -> "FaultTypeDef | None":
        """从用户查询中检测是否指定了具体故障类型"""
        from app.core.fault_types import FAULT_TYPE_REGISTRY
        query_lower = query.lower()

        for code, ft in FAULT_TYPE_REGISTRY.items():
            # 匹配故障编码
            if code in query_lower:
                return ft
            # 匹配中文名称
            if ft.name_cn in query:
                return ft
            # 匹配关键词（部分匹配）
            keywords = ft.name_cn.split("、")
            for kw in keywords:
                if len(kw) >= 2 and kw in query:
                    return ft

        return None

    async def _predict_specific_fault_type(
        self,
        fault_type: "FaultTypeDef",
        query: str,
        time_horizon: str,
        reasoning_chain: list,
    ) -> dict[str, Any]:
        """
        针对具体故障类型的预测

        例如用户问："预测未来24小时哪些设备会AC主电压过高"
        """
        import re
        from app.core.fault_logic import FaultLogicEngine
        from app.db.repositories.device_threshold import DeviceThresholdRepository

        zone_match = re.search(r'(\d+)区', query)
        zone = zone_match.group(1) if zone_match else None

        reasoning_chain.extend(await self._build_reasoning_chain([
            ("加载故障定义", f"故障编码: {fault_type.code}, 名称: {fault_type.name_cn}", "定义加载完成"),
            ("查询相关设备", f"区域: {zone or '全部'}, 数据源: {', '.join(fault_type.data_sources)}", "设备查询完成")
        ]))

        # 获取设备列表
        devices = await DeviceRepository.find_all(geozone=zone, limit=200)

        # 获取阈值配置
        # 注：DeviceThresholdRepository 需要 device_id (BigInteger) 查询
        # 简化：使用通用阈值或设备级阈值

        predictions = []
        now = datetime.utcnow()
        start_time = now - timedelta(hours=24)

        for device in devices:
            device_id = device.get("device_id")
            if not device_id:
                continue

            # 获取最近读数
            readings = await ReadingRepository.get_device_readings(
                device_id=device_id,
                start_time=start_time,
                end_time=now,
                limit=100,
            )

            # 获取阈值（简化：从 device_info 或通用阈值）
            threshold = await self._get_device_threshold(device)

            # 调用对应检查方法
            check_method = getattr(FaultLogicEngine, f"check_{fault_type.code}", None)
            if check_method and readings:
                result = check_method(readings, threshold)
            elif readings:
                # 通用检查：基于阈值越界
                result = self._generic_fault_check(fault_type, readings, threshold)
            else:
                continue

            if result.risk_score > 0.2 or result.triggered:
                predictions.append({
                    "device_id": device_id,
                    "device_type": device.get("device_type"),
                    "zone": device.get("geozone"),
                    "fault_code": fault_type.code,
                    "fault_name": fault_type.name_cn,
                    "risk_score": result.risk_score,
                    "risk_level": result.risk_level,
                    "triggered": result.triggered,
                    "evidence": result.evidence,
                    "recommendation": result.recommendation,
                    "severity": fault_type.severity.value,
                })

        # 按风险评分排序
        predictions.sort(key=lambda x: x["risk_score"], reverse=True)
        predictions = predictions[:20]

        reasoning_chain.extend(await self._build_reasoning_chain([
            ("生成预测", f"识别 {len(predictions)} 个{fault_type.name_cn}风险设备", "预测完成")
        ]))

        # 生成回答
        horizon_text = {"24h": "24小时", "7d": "7天", "30d": "30天"}.get(time_horizon, time_horizon)

        lines = [
            f"🔮 **{fault_type.name_cn}** 风险预测（未来 **{horizon_text}**）：\n",
            f"判断逻辑：{fault_type.logic_description}\n",
        ]

        if not predictions:
            lines.append(f"🎉 未发现 **{fault_type.name_cn}** 风险设备。当前系统运行正常。")
        else:
            triggered_count = sum(1 for p in predictions if p["triggered"])
            high_risk_count = sum(1 for p in predictions if p["risk_level"] in ["极高", "高"])

            lines.append(f"共评估 **{len(devices)}** 台设备，发现：")
            if triggered_count > 0:
                lines.append(f"• ⚠️ 已触发: **{triggered_count}** 台")
            if high_risk_count > 0:
                lines.append(f"• 🔶 高风险: **{high_risk_count}** 台")
            lines.append(f"• 📊 总风险设备: **{len(predictions)}** 台")
            lines.append("")
            lines.append("**TOP 5 风险设备：**")
            for p in predictions[:5]:
                status = "🔴 已触发" if p["triggered"] else f"🟡 风险 {p['risk_score']:.0%}"
                lines.append(f"  - `{p['device_id']}` | {status} | {p['evidence'][0] if p['evidence'] else '无'}")
            lines.append("")
            lines.append("💡 建议措施请见下方详细表格。")

        # 构建表格
        table = {
            "headers": ["设备ID", "区域", "风险评分", "风险等级", "是否触发", "证据", "建议"],
            "rows": [
                [
                    p["device_id"],
                    str(p.get("zone") or ""),
                    f"{p['risk_score']:.0%}",
                    p["risk_level"],
                    "是" if p["triggered"] else "否",
                    "；".join(p["evidence"][:2]),
                    p["recommendation"],
                ]
                for p in predictions
            ],
            "total": len(predictions),
        }

        # 风险分布图表
        chart = self._build_specific_fault_chart(predictions)

        return {
            "answer": "\n".join(lines),
            "reasoning_chain": reasoning_chain,
            "confidence": 0.82,
            "map_data": None,
            "data": {
                "predictions": predictions,
                "fault_type": fault_type.code,
                "fault_name": fault_type.name_cn,
                "time_horizon": time_horizon,
                "table": table,
                "chart": chart,
            },
            "sources": []
        }

    async def _get_device_threshold(self, device: dict) -> dict | None:
        """获取设备阈值配置（简化实现）"""
        # 从 device_info 中提取常用阈值
        # 实际场景应从 DeviceThresholdRepository 查询
        threshold = {}
        if device.get("rated_power"):
            rp = float(device["rated_power"])
            threshold["max_power"] = rp * 1.1
            threshold["min_power"] = rp * 0.3
        if device.get("wattage"):
            threshold["max_power"] = float(device["wattage"]) * 1.1
        # 通用默认值
        threshold.setdefault("max_voltage", 260.0)
        threshold.setdefault("min_voltage", 180.0)
        threshold.setdefault("max_current", 10.0)
        threshold.setdefault("min_current", 0.1)
        threshold.setdefault("min_power_factor", 0.85)
        threshold.setdefault("max_temperature", 85.0)
        threshold.setdefault("daylight_threshold", 50.0)
        threshold.setdefault("max_leakage_current", 30.0)
        return threshold

    def _generic_fault_check(
        self,
        fault_type: "FaultTypeDef",
        readings: list[dict],
        threshold: dict | None,
    ) -> "FaultCheckResult":
        """通用故障检查（基于阈值参数的简化检查）"""
        from app.core.fault_logic import FaultCheckResult

        # 对于没有专门检查方法的故障类型，使用通用阈值比对
        risk_score = 0.0
        evidence = []
        triggered = False

        for param in fault_type.threshold_params:
            param_key = param.replace("max_", "").replace("min_", "")
            values = [r.get(param_key, 0) for r in readings if r.get(param_key) is not None]
            if not values:
                continue

            limit = threshold.get(param) if threshold else None
            if limit is None:
                continue

            if param.startswith("max_"):
                max_val = max(values)
                if max_val > limit:
                    triggered = True
                    risk_score = max(risk_score, min((max_val / limit - 1) * 2, 0.98))
                    evidence.append(f"{param_key}={max_val:.2f} 超过上限 {limit}")
                elif max_val > limit * 0.9:
                    risk_score = max(risk_score, (max_val / limit - 0.9) * 5)
                    evidence.append(f"{param_key}={max_val:.2f} 接近上限 {limit}")
            elif param.startswith("min_"):
                min_val = min(values)
                if min_val < limit:
                    triggered = True
                    risk_score = max(risk_score, min((1 - min_val / limit) * 2, 0.98))
                    evidence.append(f"{param_key}={min_val:.2f} 低于下限 {limit}")
                elif min_val < limit * 1.1:
                    risk_score = max(risk_score, (1.1 - min_val / limit) * 5)
                    evidence.append(f"{param_key}={min_val:.2f} 接近下限 {limit}")

        risk_level = "极高" if risk_score > 0.8 else "高" if risk_score > 0.6 else "中" if risk_score > 0.35 else "低"

        return FaultCheckResult(
            fault_type.code,
            triggered,
            risk_score,
            risk_level,
            evidence or ["暂无异常数据"],
            recommendation=fault_type.logic_description[:80] + "..." if len(fault_type.logic_description) > 80 else fault_type.logic_description,
        )

    def _build_specific_fault_chart(self, predictions: list[dict]) -> dict | None:
        """构建具体故障类型的风险分布图表"""
        if not predictions:
            return None
        levels = {"极高": 0, "高": 0, "中": 0, "低": 0}
        for p in predictions:
            levels[p["risk_level"]] = levels.get(p["risk_level"], 0) + 1
        labels = [k for k, v in levels.items() if v > 0]
        values = [levels[k] for k in labels]
        colors = {"极高": "#dc2626", "高": "#f97316", "中": "#facc15", "低": "#22c55e"}
        return {
            "type": "bar",
            "title": "风险等级分布",
            "labels": labels,
            "values": values,
            "colors": [colors.get(l, "#3b82f6") for l in labels],
            "unit": "台",
        }

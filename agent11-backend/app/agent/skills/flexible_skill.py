"""Flexible 技能 - 灵活报告（增强版）"""
from typing import Any
from datetime import datetime, timedelta
import logging

from app.agent.skills.base import BaseSkill
from app.agent.context import ConversationContext
from app.db.repositories.device import DeviceRepository
from app.db.repositories.fault import FaultRepository
from app.db.repositories.reading import ReadingRepository

logger = logging.getLogger(__name__)


class FlexibleSkill(BaseSkill):
    """
    Flexible 技能 - 灵活查询和报告（增强版）。

    支持维度：
    - 设备维度：按区域、类型、状态、年龄、健康度统计
    - 能耗维度：按时间、区域聚合，支持趋势分析、时段分析
    - 故障维度：按类型、时间、区域统计
    - 图表类型：bar、pie、line、donut、horizontal_bar
    """

    name = "flexible_report"

    async def execute(
        self,
        llm: Any,
        query: str,
        context: ConversationContext
    ) -> dict[str, Any]:
        """执行灵活查询"""
        reasoning_chain = []

        reasoning_chain.extend(await self._build_reasoning_chain([
            ("解析查询意图", f"用户查询: {query}", "意图解析完成")
        ]))

        query_plan = await self._plan_query(query, llm)

        reasoning_chain.extend(await self._build_reasoning_chain([
            ("构建查询", f"查询计划: {query_plan}", "查询构建完成")
        ]))

        results = await self._execute_flexible_query(query_plan)

        reasoning_chain.extend(await self._build_reasoning_chain([
            ("执行查询", f"获取 {len(results)} 条结果", "查询完成")
        ]))

        answer = await self._generate_flexible_answer(query, results, query_plan, llm)
        data = self._generate_data_output(results, query_plan)

        return {
            "answer": answer,
            "reasoning_chain": reasoning_chain,
            "confidence": 0.88,
            "map_data": self._generate_map_data(results) if query_plan.get("includes_location") else None,
            "data": data,
            "sources": []
        }

    async def _plan_query(self, query: str, llm: Any) -> dict:
        """规划查询（增强版关键词解析，支持环形图、水平柱状图、健康度、时段分析）"""
        import re

        q = query.lower()
        plan: dict[str, Any] = {
            "collection": "devices",
            "filters": {},
            "includes_location": False,
            "aggregation": None,
            "chart": None,
            "time_range": None,
            "data_source": "devices",  # devices | energy | faults
        }

        # --- 数据域检测 ---
        if any(k in q for k in ["能耗", "用电", "电量", "kwh", "功率", "电压", "电流"]):
            plan["data_source"] = "energy"
        elif any(k in q for k in ["故障", "fault", "损坏", "维修", "修复", "事件", "告警", "告警事件", "fault_event", "alert"]):
            plan["data_source"] = "faults"

        # --- 区域 ---
        zone_match = re.search(r'(\d+)区', query)
        if zone_match:
            plan["filters"]["geozone"] = zone_match.group(1)
            plan["includes_location"] = True

        # --- 状态 ---
        for status, code in [("故障", "fault"), ("正常", "normal"), ("警告", "warning"), ("离线", "offline")]:
            if status in query:
                plan["filters"]["status"] = code
                break

        # --- 设备类型 ---
        for dtype, code in [("路灯", "streetlight"), ("控制器", "controller"), ("传感器", "sensor")]:
            if dtype in query:
                plan["filters"]["device_type"] = code
                break

        # --- 自然语言筛选：街道/路段 ---
        street_match = re.search(r'在\s*([一-鿿]+路)', query)
        if not street_match:
            street_match = re.search(r'([一-鿿]+路)\s*上的', query)
        if not street_match:
            street_match = re.search(r'([一-鿿]+路)\s*的', query)
        if street_match:
            plan["filters"]["street_name"] = street_match.group(1)

        # --- 自然语言筛选：状态（如 状态1、状态为1、状态是1） ---
        status_match = re.search(r'状态[为是]?\s*(\d+)', query)
        if status_match:
            plan["filters"]["status"] = status_match.group(1)

        # --- "有多少" → 触发计数（去掉聚合，用默认输出直接显示筛选后的条数） ---
        # 已有筛选条件（街道/状态）时，数量会自然体现在结果中

        # --- 时间范围 ---
        if any(k in q for k in ["今天", "今日", "24小时", "24h"]):
            plan["time_range"] = "1d"
        elif any(k in q for k in ["本周", "这周", "7天", "7d"]):
            plan["time_range"] = "7d"
        elif any(k in q for k in ["本月", "这个月", "30天", "30d"]):
            plan["time_range"] = "30d"
        elif any(k in q for k in ["本年", "今年", "年度", "一年", "365天"]):
            plan["time_range"] = "1y"

        # --- 图表样式偏好 ---
        chart_style = "bar"  # default
        if any(k in q for k in ["饼图", "环形图", "占比", "比例", "proportion"]):
            chart_style = "donut" if any(k in q for k in ["环形"]) else "pie"
        elif any(k in q for k in ["水平", "横向"]):
            chart_style = "horizontal_bar"
        # 英文图表类型检测
        elif any(k in q for k in ["bar chart", "histogram", "柱状图", "柱形图"]):
            chart_style = "bar"

        # --- 图表 + 故障 = 需要聚合图表数据 ---
        if chart_style == "bar" and plan["data_source"] == "faults":
            plan["aggregation"] = "faults_by_type"
            plan["chart"] = {"type": "bar", "title": "故障类型分布（柱状图）"}

        # --- 聚合类型检测 ---
        # 健康度
        if any(k in q for k in ["健康度", "健康评分", "健康状态", "健康状况"]):
            plan["aggregation"] = "health_score"
            plan["chart"] = {"type": chart_style, "title": "设备健康度分布"}

        # 设备年龄
        elif any(k in q for k in ["设备年龄", "老化", "使用年限", "安装时间", "服役"]):
            plan["aggregation"] = "age_distribution"
            plan["chart"] = {"type": "bar", "title": "设备年龄分布"}

        # 按时段/小时分析
        elif any(k in q for k in ["时段", "小时", "每时", "24小时分布", "峰谷"]):
            plan["aggregation"] = "time_of_day"
            plan["data_source"] = "energy"
            plan["chart"] = {"type": "line", "title": "24小时能耗分布"}

        # 按区域（注意 "各区域" 含 "各区" 子串，需要排除）
        elif "按区域" in q or "按区" in q or ("各区" in q and "各区域" not in q):
            if plan["data_source"] == "energy":
                plan["aggregation"] = "energy_by_geozone"
                plan["chart"] = {"type": chart_style, "title": "各区域能耗对比"}
            elif plan["data_source"] == "faults":
                plan["aggregation"] = "faults_by_geozone"
                plan["chart"] = {"type": chart_style, "title": "各区域故障数量对比"}
            else:
                plan["aggregation"] = "count_by_geozone"
                plan["chart"] = {"type": chart_style, "title": "按区域设备数量分布"}

        elif any(k in q for k in ["按状态", "状态分布", "状态统计"]):
            plan["aggregation"] = "count_by_status"
            plan["chart"] = {"type": chart_style if chart_style in ("pie", "donut") else "pie", "title": "设备状态分布"}

        elif any(k in q for k in ["按类型", "类型分布", "类型统计"]):
            plan["aggregation"] = "count_by_type"
            plan["chart"] = {"type": chart_style if chart_style in ("pie", "donut") else "pie", "title": "设备类型分布"}

        elif any(k in q for k in ["按故障类型", "故障类型分布", "故障统计"]):
            plan["aggregation"] = "faults_by_type"
            plan["chart"] = {"type": chart_style if chart_style in ("pie", "donut") else "pie", "title": "故障类型分布"}
            plan["data_source"] = "faults"

        elif any(k in q for k in ["趋势", "变化", "走势", "历史"]):
            plan["aggregation"] = "trend"
            plan["chart"] = {"type": "line", "title": "趋势分析"}
            if plan["data_source"] == "devices":
                plan["data_source"] = "energy"

        elif any(k in q for k in ["比较", "对比", "排名", "top", "最多", "最少"]):
            plan["aggregation"] = "compare"
            if plan["data_source"] == "energy":
                plan["compare_field"] = "energy_kwh"
                plan["chart"] = {"type": chart_style if chart_style == "horizontal_bar" else "bar", "title": "能耗对比排名"}
            elif plan["data_source"] == "faults":
                plan["compare_field"] = "fault_count"
                plan["chart"] = {"type": chart_style if chart_style == "horizontal_bar" else "bar", "title": "故障对比排名"}
            else:
                plan["compare_field"] = "device_count"
                plan["chart"] = {"type": chart_style if chart_style == "horizontal_bar" else "bar", "title": "设备数量对比"}

        # --- 定制分组（按 XX 统计）优先于通用汇总 ---
        custom_group_map = {
            "街道": "street_name",
            "路段": "street_name",
            "状态": "status",
            "类型": "device_type",
            "设备类型": "device_type",
            "分组": "businessGroupName",
            "区域": "businessGroupName",
            "功率": "wattage",
            "瓦数": "wattage",
            "安装日期": "install_date",
        }
        group_match = re.search(r'(?:按|根据|以)\s*(\S+)', query)
        if group_match:
            dim = group_match.group(1)
            # 去掉末尾的 统计/汇总/分组/排序/排列
            for sfx in ["统计", "汇总", "分组", "排序", "排列"]:
                if dim.endswith(sfx):
                    dim = dim[:-len(sfx)]
                    break
            col = custom_group_map.get(dim)
            if col:
                plan["aggregation"] = "custom_group"
                plan["group_column"] = col
                plan["group_dim"] = dim

        elif any(k in q for k in ["汇总", "统计", "总数", "分布"]):
            if plan["data_source"] == "energy":
                plan["aggregation"] = "energy_summary"
            elif plan["data_source"] == "faults":
                plan["aggregation"] = "fault_summary"
            else:
                plan["aggregation"] = "count_by_geozone"
                plan["chart"] = {"type": chart_style, "title": "设备分布统计"}

        # --- 排序 ---
        if any(k in q for k in ["排序", "排名", "top", "最多", "最高"]):
            plan["sort"] = True
            plan["sort_desc"] = "最少" not in q and "最低" not in q
            if plan["data_source"] == "energy":
                plan["sort_field"] = "energy_kwh"
            elif plan["data_source"] == "faults":
                plan["sort_field"] = "fault_count"
            else:
                plan["sort_field"] = "device_count"

        return plan

    async def _get_all_faults_for_chart(self, plan: dict) -> list[dict]:
        """从 devices_fault 获取所有故障记录用于图表聚合"""
        from app.db.session import get_session
        from sqlalchemy import text

        async for session in get_session():
            result = await session.execute(
                text('''
                    SELECT fault, COUNT(*) as count
                    FROM devices_fault
                    WHERE fault IS NOT NULL AND fault != ''
                    GROUP BY fault
                    ORDER BY count DESC
                    LIMIT 50
                ''')
            )
            rows = result.fetchall()
            return [{"fault": r[0], "count": r[1]} for r in rows]

    async def _execute_flexible_query(self, plan: dict) -> list[dict]:
        """执行灵活查询（多数据源支持）"""
        data_source = plan.get("data_source", "devices")
        filters = plan.get("filters", {})
        time_range = plan.get("time_range")
        aggregation = plan.get("aggregation")

        now = datetime.utcnow()
        start_time = None
        if time_range:
            if time_range == "1d":
                start_time = now - timedelta(days=1)
            elif time_range == "7d":
                start_time = now - timedelta(days=7)
            elif time_range == "30d":
                start_time = now - timedelta(days=30)
            elif time_range == "1y":
                start_time = now - timedelta(days=365)

        # 如果需要故障类型统计（如 bar chart），直接查 devices_fault
        if data_source == "faults" and aggregation in ("faults_by_type", "fault_summary", "compare", "bar_chart_requested"):
            results = await self._get_all_faults_for_chart(plan)
            return results

        if data_source == "energy":
            results = await ReadingRepository.get_energy_readings(
                geozone=filters.get("geozone"),
                start_time=start_time,
                end_time=now,
                limit=10000
            )
        elif data_source == "faults":
            results = await FaultRepository.find_active(
                geozone=filters.get("geozone"),
                limit=5000
            )
            # 如果时间过滤需要再处理
            if start_time and results:
                results = [r for r in results if r.get("detected_at") and r["detected_at"] >= start_time]
        else:
            results = await DeviceRepository.find_all(
                geozone=filters.get("geozone"),
                status=filters.get("status"),
                device_type=filters.get("device_type"),
                street_name=filters.get("street_name"),
                limit=2000
            )

        return results

    async def _generate_flexible_answer(
        self, query: str, results: list, plan: dict, llm: Any
    ) -> str:
        """根据聚合类型和数据生成描述"""
        if not results:
            return "未找到匹配的数据。请尝试调整查询条件或时间范围。"

        aggregation = plan.get("aggregation")
        data_source = plan.get("data_source", "devices")
        count = len(results)

        if aggregation == "health_score":
            return f"设备健康度分析完成，共评估 {count} 台设备，分布情况请见下方图表。"

        if aggregation == "age_distribution":
            return f"设备年龄分布统计完成，共 {count} 台设备。"

        if aggregation == "time_of_day":
            total = sum(r.get("energy_kwh", 0) for r in results)
            return f"24小时能耗分布分析完成，总能耗 {total:.2f} kWh。"

        if aggregation == "count_by_geozone":
            return f"按区域统计共找到 {count} 台设备，分布情况请见下方图表。"

        if aggregation == "count_by_status":
            return f"设备状态分布统计完成，共 {count} 台设备。"

        if aggregation == "count_by_type":
            return f"设备类型分布统计完成，共 {count} 台设备。"

        if aggregation == "energy_by_geozone":
            total = sum(r.get("energy_kwh", 0) for r in results)
            return f"各区域能耗统计完成，查询范围内总能耗 {total:.2f} kWh。"

        if aggregation == "energy_summary":
            total = sum(r.get("energy_kwh", 0) for r in results)
            avg = total / count if count > 0 else 0
            return f"能耗汇总：共 {count} 条记录，总能耗 {total:.2f} kWh，平均每条 {avg:.2f} kWh。"

        if aggregation == "faults_by_geozone":
            return f"各区域故障统计完成，共 {count} 个故障记录。"

        if aggregation == "faults_by_type":
            return f"故障类型分布统计完成，共 {count} 个故障记录。"

        if aggregation == "fault_summary":
            return f"故障汇总：共 {count} 个故障记录。"

        if aggregation == "trend":
            return f"趋势分析完成，基于 {count} 条历史数据生成趋势图。"

        if aggregation == "compare":
            return f"对比分析完成，共 {count} 条记录参与排名。"

        # 定制分组统计
        if aggregation == "custom_group":
            dim = plan.get("group_dim", plan.get("group_column", ""))
            col = plan.get("group_column", "")
            counts: dict[str, int] = {}
            for r in results:
                val = str(r.get(col) or "其他")
                counts[val] = counts.get(val, 0) + 1
            lines = [f"按{dim}统计（共 {count} 台设备）：\n"]
            for k, v in sorted(counts.items(), key=lambda x: -x[1]):
                lines.append(f"- {k}: {v}台")
            return "\n".join(lines)

        # 少于50台显示详细清单，超过50台则汇总统计
        if count <= 50:
            sample = results[:20]
            # 构建筛选描述
            flt = plan.get("filters", {})
            desc = ""
            if flt.get("street_name"):
                desc += flt["street_name"]
            if flt.get("status"):
                desc += f"状态{flt['status']}"
            lines = [f"{desc}共 {count} 台设备：\n" if desc else f"找到 {count} 台设备：\n"]
            for r in sample:
                did = r.get("device_id") or r.get("deviceId", "N/A")
                name = r.get("device_name") or r.get("deviceName", "")
                status = r.get("status") or ""
                group = r.get("businessGroupName") or ""
                parts = [name, did, group, status]
                parts = [p for p in parts if p]
                lines.append(f"- {' | '.join(parts)}")
            if count > 20:
                lines.append(f"\n... 还有 {count - 20} 台设备")
            # 如果有筛选条件（已按特定维度查询），不显示定制提示
            if not plan.get("filters"):
                lines.append("\n💡 如需定制统计表格，请告诉我统计维度（如按街道统计、按状态统计）")
            return "\n".join(lines)

        # 超过50台：汇总统计（按状态、类型、分组）
        statuses: dict[str, int] = {}
        types: dict[str, int] = {}
        groups: dict[str, int] = {}
        for r in results:
            s = r.get("status") or "unknown"
            statuses[s] = statuses.get(s, 0) + 1
            t = r.get("device_type") or "unknown"
            types[t] = types.get(t, 0) + 1
            g = r.get("businessGroupName") or "其他"
            groups[g] = groups.get(g, 0) + 1

        lines = [f"共找到 {count} 台设备\n"]
        lines.append(f"■ 按状态：{' | '.join([f'{k} {v}台' for k, v in sorted(statuses.items(), key=lambda x: -x[1])])}")
        lines.append(f"■ 按类型：{' | '.join([f'{k} {v}台' for k, v in sorted(types.items(), key=lambda x: -x[1])])}")
        lines.append(f"■ 按分组：{' | '.join([f'{k} {v}台' for k, v in sorted(groups.items(), key=lambda x: -x[1])])}")
        return "\n".join(lines)

    def _build_chart(self, base: dict, plan: dict) -> dict:
        """根据计划中的图表类型包装 chart 数据（支持 donut / horizontal_bar）"""
        chart_type = (plan.get("chart") or {}).get("type", "bar")
        base["type"] = chart_type
        if chart_type == "horizontal_bar":
            base["type"] = "bar"
            base["orientation"] = "horizontal"
        elif chart_type == "donut":
            base["type"] = "donut"
        return base

    def _generate_data_output(self, results: list, plan: dict) -> dict:
        """生成数据输出（支持健康度、年龄分布、时段分析、多种图表类型）"""
        if not results:
            return {"table": {"headers": [], "rows": []}}

        aggregation = plan.get("aggregation")
        data_source = plan.get("data_source", "devices")

        # ---------- 健康度分布 ----------
        if aggregation == "health_score":
            buckets = {"优秀(>80)": 0, "良好(60-80)": 0, "一般(40-60)": 0, "差(<40)": 0}
            for r in results:
                faults = int(r.get("fault_count", 0))
                status = r.get("status", "normal")
                score = 100 - faults * 10
                if status == "fault":
                    score -= 30
                elif status == "warning":
                    score -= 15
                elif status == "offline":
                    score -= 20
                score = max(0, min(100, score))
                if score > 80:
                    buckets["优秀(>80)"] += 1
                elif score > 60:
                    buckets["良好(60-80)"] += 1
                elif score > 40:
                    buckets["一般(40-60)"] += 1
                else:
                    buckets["差(<40)"] += 1
            labels = [k for k, v in buckets.items() if v > 0]
            values = [buckets[k] for k in labels]
            colors = {"优秀(>80)": "#22c55e", "良好(60-80)": "#3b82f6", "一般(40-60)": "#facc15", "差(<40)": "#ef4444"}
            chart = self._build_chart({
                "title": plan.get("chart", {}).get("title") or "设备健康度分布",
                "labels": labels,
                "values": values,
                "colors": [colors.get(l, "#3b82f6") for l in labels],
                "unit": "台",
            }, plan)
            return {
                "table": {"headers": ["健康等级", "设备数量"], "rows": [[k, str(v)] for k, v in zip(labels, values)], "total": len(labels)},
                "chart": chart,
            }

        # ---------- 设备年龄分布 ----------
        if aggregation == "age_distribution":
            now = datetime.utcnow()
            buckets = {"1年以内": 0, "1-3年": 0, "3-5年": 0, "5年以上": 0}
            for r in results:
                install_date = r.get("install_date")
                if not install_date:
                    buckets["1年以内"] += 1
                    continue
                if isinstance(install_date, str):
                    try:
                        install_date = datetime.fromisoformat(install_date.replace("Z", "+00:00"))
                    except Exception:
                        buckets["1年以内"] += 1
                        continue
                age_years = (now - install_date.replace(tzinfo=None)).days / 365.0 if hasattr(install_date, "replace") else 0
                if age_years < 1:
                    buckets["1年以内"] += 1
                elif age_years < 3:
                    buckets["1-3年"] += 1
                elif age_years < 5:
                    buckets["3-5年"] += 1
                else:
                    buckets["5年以上"] += 1
            labels = [k for k, v in buckets.items() if v > 0]
            values = [buckets[k] for k in labels]
            chart = self._build_chart({
                "title": plan.get("chart", {}).get("title") or "设备年龄分布",
                "labels": labels,
                "values": values,
                "unit": "台",
            }, plan)
            return {
                "table": {"headers": ["使用年限", "设备数量"], "rows": [[k, str(v)] for k, v in zip(labels, values)], "total": len(labels)},
                "chart": chart,
            }

        # ---------- 24小时能耗时段分析 ----------
        if aggregation == "time_of_day":
            hourly: dict[int, float] = {}
            for r in results:
                ts = r.get("timestamp") or r.get("recorded_at")
                energy = r.get("energy_kwh", 0)
                if ts:
                    if isinstance(ts, str):
                        try:
                            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        except Exception:
                            continue
                    if isinstance(ts, datetime):
                        h = ts.hour
                        hourly[h] = hourly.get(h, 0.0) + energy
            if hourly:
                labels = [f"{h:02d}:00" for h in range(24)]
                values = [round(hourly.get(h, 0), 2) for h in range(24)]
            else:
                labels, values = [], []
            chart = self._build_chart({
                "title": plan.get("chart", {}).get("title") or "24小时能耗分布",
                "labels": labels,
                "values": values,
                "unit": "kWh",
            }, plan)
            return {
                "table": {"headers": ["时段", "能耗 (kWh)"], "rows": [[l, str(v)] for l, v in zip(labels, values)], "total": len(labels)},
                "chart": chart,
            }

        # ---------- 按区域聚合 ----------
        if aggregation == "count_by_geozone":
            counts: dict[str, int] = {}
            for r in results:
                z = str(r.get("geozone") or r.get("zone") or "unknown")
                counts[z] = counts.get(z, 0) + 1
            labels = sorted(counts.keys(), key=lambda k: (k == "unknown", k))
            values = [counts[k] for k in labels]
            chart = self._build_chart({
                "title": plan.get("chart", {}).get("title") or "按区域设备数量分布",
                "labels": labels,
                "values": values,
                "unit": "台",
            }, plan)
            return {
                "table": {"headers": ["区域", "设备数量"], "rows": [[k, str(counts[k])] for k in labels], "total": len(labels)},
                "chart": chart,
            }

        # ---------- 按状态聚合 ----------
        if aggregation == "count_by_status":
            counts: dict[str, int] = {}
            for r in results:
                s = str(r.get("status") or "unknown")
                counts[s] = counts.get(s, 0) + 1
            labels = sorted(counts.keys(), key=lambda k: counts[k], reverse=True)
            values = [counts[k] for k in labels]
            color_map = {"normal": "#22c55e", "warning": "#facc15", "fault": "#ef4444", "offline": "#6b7280"}
            chart = self._build_chart({
                "title": plan.get("chart", {}).get("title") or "设备状态分布",
                "labels": labels,
                "values": values,
                "colors": [color_map.get(l, "#3b82f6") for l in labels],
                "unit": "台",
            }, plan)
            return {
                "table": {"headers": ["状态", "数量"], "rows": [[k, str(counts[k])] for k in labels], "total": len(labels)},
                "chart": chart,
            }

        # ---------- 按类型聚合 ----------
        if aggregation == "count_by_type":
            counts: dict[str, int] = {}
            for r in results:
                t = str(r.get("device_type") or r.get("type") or "unknown")
                counts[t] = counts.get(t, 0) + 1
            labels = sorted(counts.keys(), key=lambda k: counts[k], reverse=True)
            values = [counts[k] for k in labels]
            chart = self._build_chart({
                "title": plan.get("chart", {}).get("title") or "设备类型分布",
                "labels": labels,
                "values": values,
                "unit": "台",
            }, plan)
            return {
                "table": {"headers": ["设备类型", "数量"], "rows": [[k, str(counts[k])] for k in labels], "total": len(labels)},
                "chart": chart,
            }

        # ---------- 能耗按区域聚合 ----------
        if aggregation == "energy_by_geozone":
            energy_by_zone: dict[str, float] = {}
            for r in results:
                z = str(r.get("geozone") or r.get("zone") or "unknown")
                energy_by_zone[z] = energy_by_zone.get(z, 0.0) + r.get("energy_kwh", 0)
            labels = sorted(energy_by_zone.keys(), key=lambda k: energy_by_zone[k], reverse=True)
            values = [round(energy_by_zone[k], 2) for k in labels]
            chart = self._build_chart({
                "title": plan.get("chart", {}).get("title") or "各区域能耗对比",
                "labels": labels,
                "values": values,
                "unit": "kWh",
            }, plan)
            return {
                "table": {"headers": ["区域", "能耗 (kWh)"], "rows": [[k, str(v)] for k, v in zip(labels, values)], "total": len(labels)},
                "chart": chart,
            }

        # ---------- 能耗汇总 ----------
        if aggregation == "energy_summary":
            daily: dict[str, float] = {}
            for r in results:
                ts = r.get("timestamp") or r.get("recorded_at")
                if ts:
                    if isinstance(ts, str):
                        try:
                            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        except Exception:
                            continue
                    if isinstance(ts, datetime):
                        day = ts.strftime("%m-%d")
                        daily[day] = daily.get(day, 0.0) + r.get("energy_kwh", 0)
            labels = sorted(daily.keys())[-14:]
            values = [round(daily[k], 2) for k in labels]
            chart = self._build_chart({
                "title": "能耗趋势", "labels": labels, "values": values, "unit": "kWh",
            }, plan) if plan.get("chart", {}).get("type") in ("line",) else {
                "type": "line", "title": "能耗趋势", "labels": labels, "values": values, "unit": "kWh",
            }
            return {
                "table": {"headers": ["日期", "能耗 (kWh)"], "rows": [[k, str(daily[k])] for k in labels], "total": len(labels)},
                "chart": chart,
            }

        # ---------- 故障按区域聚合 ----------
        if aggregation == "faults_by_geozone":
            counts: dict[str, int] = {}
            for r in results:
                z = str(r.get("geozone") or r.get("zone") or "unknown")
                counts[z] = counts.get(z, 0) + 1
            labels = sorted(counts.keys(), key=lambda k: counts[k], reverse=True)
            values = [counts[k] for k in labels]
            chart = self._build_chart({
                "title": plan.get("chart", {}).get("title") or "各区域故障数量",
                "labels": labels, "values": values, "unit": "个",
            }, plan)
            return {
                "table": {"headers": ["区域", "故障数量"], "rows": [[k, str(counts[k])] for k in labels], "total": len(labels)},
                "chart": chart,
            }

        # ---------- 故障按类型聚合 ----------
        if aggregation == "faults_by_type":
            # 支持两种数据格式：{"fault": x, "count": n} 聚合结果 或 {"fault_type": x} 原始记录
            if results and "fault" in results[0] and "count" in results[0]:
                # 已经是聚合好的数据（来自 _get_all_faults_for_chart）
                labels = [r["fault"] for r in results]
                values = [r["count"] for r in results]
            else:
                counts: dict[str, int] = {}
                for r in results:
                    t = str(r.get("fault_type") or "unknown")
                    counts[t] = counts.get(t, 0) + 1
                labels = sorted(counts.keys(), key=lambda k: counts[k], reverse=True)
                values = [counts[k] for k in labels]
            chart = self._build_chart({
                "title": plan.get("chart", {}).get("title") or "故障类型分布",
                "labels": labels, "values": values, "unit": "个",
            }, plan)
            return {
                "table": {"headers": ["故障类型", "数量"], "rows": [[k, str(v)] for k, v in zip(labels, values)], "total": len(labels)},
                "chart": chart,
            }

        # ---------- 故障汇总 ----------
        if aggregation == "fault_summary":
            daily: dict[str, int] = {}
            for r in results:
                ts = r.get("detected_at")
                if ts:
                    if isinstance(ts, str):
                        try:
                            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        except Exception:
                            continue
                    if isinstance(ts, datetime):
                        day = ts.strftime("%m-%d")
                        daily[day] = daily.get(day, 0) + 1
            labels = sorted(daily.keys())[-14:]
            values = [daily[k] for k in labels]
            return {
                "table": {"headers": ["日期", "故障数量"], "rows": [[k, str(daily[k])] for k in labels], "total": len(labels)},
                "chart": {"type": "line", "title": "故障趋势", "labels": labels, "values": values, "unit": "个"},
            }

        # ---------- 趋势 ----------
        if aggregation == "trend":
            daily: dict[str, float] = {}
            for r in results:
                ts = r.get("timestamp") or r.get("recorded_at") or r.get("detected_at")
                val = r.get("energy_kwh", 0) if "energy_kwh" in r else 1
                if ts:
                    if isinstance(ts, str):
                        try:
                            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        except Exception:
                            continue
                    if isinstance(ts, datetime):
                        day = ts.strftime("%m-%d")
                        daily[day] = daily.get(day, 0.0) + val
            labels = sorted(daily.keys())[-14:]
            values = [round(daily[k], 2) for k in labels]
            return {
                "table": {"headers": ["日期", "数值"], "rows": [[k, str(daily[k])] for k in labels], "total": len(labels)},
                "chart": {"type": "line", "title": plan.get("chart", {}).get("title") or "趋势分析", "labels": labels, "values": values, "unit": ""},
            }

        # ---------- 对比/排名 ----------
        if aggregation == "compare":
            counts: dict[str, int] = {}
            for r in results:
                z = str(r.get("geozone") or r.get("zone") or "unknown")
                counts[z] = counts.get(z, 0) + 1
            sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
            labels = [k for k, v in sorted_items]
            values = [v for k, v in sorted_items]
            chart = self._build_chart({
                "title": plan.get("chart", {}).get("title") or "对比排名",
                "labels": labels, "values": values, "unit": "",
            }, plan)
            return {
                "table": {"headers": ["区域", "数量"], "rows": [[k, str(v)] for k, v in sorted_items], "total": len(sorted_items)},
                "chart": chart,
            }

        # ---------- 定制分组统计 ----------
        if aggregation == "custom_group":
            dim = plan.get("group_dim", plan.get("group_column", ""))
            col = plan.get("group_column", "")
            counts: dict[str, int] = {}
            for r in results:
                val = str(r.get(col) or "其他")
                counts[val] = counts.get(val, 0) + 1
            labels = sorted(counts.keys(), key=lambda k: counts[k], reverse=True)
            values = [counts[k] for k in labels]
            chart = self._build_chart({
                "title": f"按{dim}统计",
                "labels": labels, "values": values, "unit": "台",
            }, plan)
            return {
                "table": {"headers": [f"按{dim}", "数量"], "rows": [[k, str(v)] for k, v in zip(labels, values)], "total": len(labels)},
                "chart": chart,
            }

        # ---------- 默认输出 ----------
        count = len(results)

        # 少于50台显示详细清单，超过50台则汇总统计
        if count <= 50:
            headers = ["设备ID", "设备名称", "设备类型", "分组", "街道", "状态", "纬度", "经度"]
            rows = []
            for r in results[:100]:
                rows.append([
                    r.get("device_id") or r.get("deviceId", ""),
                    r.get("device_name") or r.get("deviceName", ""),
                    r.get("device_type") or r.get("type", ""),
                    r.get("businessGroupName") or "",
                    r.get("street_name") or "",
                    r.get("status") or "",
                    str(r.get("latitude") or ""),
                    str(r.get("longitude") or ""),
                ])
        else:
            # 汇总统计（按状态、类型、分组）
            statuses: dict[str, int] = {}
            types: dict[str, int] = {}
            groups: dict[str, int] = {}
            for r in results:
                s = r.get("status") or "unknown"
                statuses[s] = statuses.get(s, 0) + 1
                t = r.get("device_type") or "unknown"
                types[t] = types.get(t, 0) + 1
                g = r.get("businessGroupName") or "其他"
                groups[g] = groups.get(g, 0) + 1

            headers = ["统计维度", "分类", "数量"]
            rows = []
            for k, v in sorted(statuses.items(), key=lambda x: -x[1]):
                rows.append(["按状态", k, str(v)])
            for k, v in sorted(types.items(), key=lambda x: -x[1]):
                rows.append(["按类型", k, str(v)])
            for k, v in sorted(groups.items(), key=lambda x: -x[1]):
                rows.append(["按分组", k, str(v)])

        return {
            "table": {"headers": headers, "rows": rows, "total": len(results)}
        }

    def _generate_map_data(self, results: list) -> dict | None:
        """生成地图数据"""
        markers = []
        for r in results:
            lat = r.get("latitude")
            lng = r.get("longitude")
            if lat and lng:
                markers.append({
                    "device_id": r.get("device_id") or r.get("deviceId", ""),
                    "lat": lat,
                    "lng": lng,
                    "status": r.get("status", "normal"),
                    "popup": f"{r.get('device_id') or r.get('deviceId', '')} - {r.get('status', '')}"
                })
        if not markers:
            return None
        lats = [m["lat"] for m in markers]
        lngs = [m["lng"] for m in markers]
        center = [sum(lats) / len(lats), sum(lngs) / len(lngs)]
        return {
            "center": center,
            "zoom": 14,
            "markers": markers
        }

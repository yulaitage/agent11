"""Flexible 技能 - 灵活报告（增强版）"""
import re
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
    """Flexible 技能 - 灵活查询和报告"""

    @staticmethod
    def _is_en(query: str) -> bool:
        """检测查询是否为英文"""
        import re
        return not bool(re.search(r'[一-鿿]', query))

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

        is_en = self._is_en(query)
        query_plan["is_en"] = is_en
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
        """使用 LLM 分析用户自然语言，生成查询计划"""
        import re, json

        prompt = (
            "你是一个数据分析专家。根据用户的自然语言问题，生成结构化的数据查询计划。\n\n"
            "可用数据列（devices_info 表）：\n"
            "- device_id, device_name, device_type, status, street_name\n"
            "- businessGroupName, businessGroupNamePath, wattage, rated_power\n"
            "- latitude, longitude, install_date\n\n"
            "还可用：devices_fault（故障记录）, 能耗数据\n\n"
            '输出 JSON 格式（仅 JSON，不要解释）：\n'
            '{\n'
            '  "data_source": "devices",\n'
            '  "filters": {},\n'
            '  "aggregation": null,\n'
            '  "group_column": null,\n'
            '  "group_dim": null,\n'
            '  "chart": null,\n'
            '  "sort": false,\n'
            '  "sort_desc": true,\n'
            '  "includes_location": false\n'
            '}\n\n'
            "规则：\n"
            '1. 如果用户提到具体值（如街道名、状态值、类型、分组），放到 filters 中。\n'
            '   "在和平路上的设备" -> filters: {"street_name": "和平路"}\n'
            '   "状态1的设备" -> filters: {"status": "1"}\n'
            '   "分组9有几台设备" -> filters: {"businessGroupName": "分组9"}\n'
            '   "分组9" -> filters: {"businessGroupName": "分组9"}\n'
            '   "分组10" -> filters: {"businessGroupName": "分组10"}\n'
            '   "路灯" -> filters: {"device_type": "streetlight"}\n'
            'IMPORTANT: 分组X（X是数字）要作为 businessGroupName 过滤，不要忽略\n'
            '2. "按XX统计"或"XX分布" -> aggregation 为 custom_group, group_column 为列名, group_dim 为中文维度名\n'
            '3. "有多少"、"多少个"、"总共" -> 不清求分组, aggregation 为 null\n'
            '4. "健康度" -> aggregation 为 health_score\n'
            '5. "趋势"、"走势" -> aggregation 为 trend, data_source 为 energy\n'
            '6. 故障类型（灯具功率过高、温度过高、电表故障等）不需要放 filters，不需要切换 data_source\n'
            '7. 能耗查询设 data_source 为 energy\n'
            '8. 涉及街道的 filter key: street_name\n'
            '9. 涉及分组的 filter key: businessGroupName\n'
            '10. 涉及状态的 filter key: status\n'
            '11. 涉及设备类型的 filter key: device_type\n'
            '12. data_source 仅能为 devices 或 energy，不能为 faults\n'
            '13. English queries also work — extract filters the same way:\n'
            '    "how many devices in group 10" -> filters: {"businessGroupName": "分组10"}\n'
            '    "devices on 和平路" -> filters: {"street_name": "和平路"}\n'
            '    "devices with status 1" -> filters: {"status": "1"}\n\n'
            f"用户问题: {query}"
        )

        try:
            import json
            response = await llm.invoke(prompt, system=False, temperature=0.1)
            json_str = response.strip()
            json_str = re.sub(r'<think>.*?</think>', '', json_str, flags=re.DOTALL)
            json_str = re.sub(r'```json|```', '', json_str).strip()
            start = json_str.find("{")
            end = json_str.rfind("}")
            if start != -1 and end != -1 and end > start:
                json_str = json_str[start:end+1]
                plan = json.loads(json_str)
                defaults = {
                    "data_source": "devices", "filters": {},
                    "aggregation": None, "group_column": None,
                    "group_dim": None, "chart": None,
                    "sort": False, "sort_desc": True, "includes_location": False,
                }
                logger.info("llm_plan_generated: %s", str(plan)[:200])
                for k, v in defaults.items():
                    plan.setdefault(k, v)
                return plan
        except Exception as e:
            logger.warning("plan_query_failed: %s", e)

        fallback = {"data_source": "devices", "filters": {},
                   "aggregation": None, "group_column": None,
                   "group_dim": None, "chart": None,
                   "sort": False, "sort_desc": True, "includes_location": False}
        return fallback

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
        # fault_records 表不存在，故障查询走 devices_fault 或 fault_query skill
        if data_source == "faults":
            data_source = "devices"
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
                business_group=filters.get("businessGroupName"),
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
                val = str(r.get(col) or ("other" if self._is_en(query) else "其他"))
                counts[val] = counts.get(val, 0) + 1
            if self._is_en(query):
                lines = [f"By {dim} ({count} devices total):\n"]
                for k, v in sorted(counts.items(), key=lambda x: -x[1]):
                    lines.append(f"- {k}: {v}")
            else:
                lines = [f"按{dim}统计（共 {count} 台设备）：\n"]
                for k, v in sorted(counts.items(), key=lambda x: -x[1]):
                    lines.append(f"- {k}: {v}台")
            return "\n".join(lines)

        # 少于50台显示详细清单，超过50台则汇总统计
        is_en = self._is_en(query)
        if count <= 50:
            sample = results[:20]
            flt = plan.get("filters", {})
            desc = ""
            if flt.get("street_name"):
                desc += flt["street_name"]
            if flt.get("status"):
                desc += f" status {flt['status']}" if is_en else f"状态{flt['status']}"
            if desc:
                lines = [f"{desc}: {count} devices\n" if is_en else f"{desc}共 {count} 台设备：\n"]
            else:
                lines = [f"Found {count} devices:\n" if is_en else f"找到 {count} 台设备：\n"]
            for r in sample:
                did = r.get("device_id") or r.get("deviceId", "N/A")
                name = r.get("device_name") or r.get("deviceName", "")
                status = r.get("status") or ""
                group = r.get("businessGroupName") or ""
                parts = [name, did, group, status]
                parts = [p for p in parts if p]
                lines.append(f"- {' | '.join(parts)}")
            if count > 20:
                lines.append(f"\n... {count - 20} more" if is_en else f"\n... 还有 {count - 20} 台设备")
            if not plan.get("filters"):
                tip = "\n💡 Ask to customize (e.g. 'group by street' or 'by status')" if is_en else "\n💡 如需定制统计表格，请告诉我统计维度（如按街道统计、按状态统计）"
                lines.append(tip)
            return "\n".join(lines)

        # 超过50台：汇总统计（按状态、类型、分组）
        is_en = self._is_en(query)
        statuses: dict[str, int] = {}
        types: dict[str, int] = {}
        groups: dict[str, int] = {}
        for r in results:
            s = r.get("status") or "unknown"
            statuses[s] = statuses.get(s, 0) + 1
            t = r.get("device_type") or "unknown"
            types[t] = types.get(t, 0) + 1
            g = r.get("businessGroupName") or ("other" if is_en else "其他")
            groups[g] = groups.get(g, 0) + 1

        if is_en:
            lines = [f"Total {count} devices\n"]
            lines.append(f"■ By status: {' | '.join([f'{k} {v}' for k, v in sorted(statuses.items(), key=lambda x: -x[1])])}")
            lines.append(f"■ By type: {' | '.join([f'{k} {v}' for k, v in sorted(types.items(), key=lambda x: -x[1])])}")
            lines.append(f"■ By group: {' | '.join([f'{k} {v}' for k, v in sorted(groups.items(), key=lambda x: -x[1])])}")
        else:
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
        is_en_tbl = plan.get("is_en", False)

        # 少于50台显示详细清单，超过50台则汇总统计
        if count <= 50:
            headers = ["Device ID", "Name", "Type", "Group", "Street", "Status", "Lat", "Lng"] if is_en_tbl else ["设备ID", "设备名称", "设备类型", "分组", "街道", "状态", "纬度", "经度"]
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
                g = r.get("businessGroupName") or ("other" if is_en_tbl else "其他")
                groups[g] = groups.get(g, 0) + 1

            if is_en_tbl:
                headers = ["Dimension", "Category", "Count"]
                rows = []
                for k, v in sorted(statuses.items(), key=lambda x: -x[1]):
                    rows.append(["By status", k, str(v)])
                for k, v in sorted(types.items(), key=lambda x: -x[1]):
                    rows.append(["By type", k, str(v)])
                for k, v in sorted(groups.items(), key=lambda x: -x[1]):
                    rows.append(["By group", k, str(v)])
            else:
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

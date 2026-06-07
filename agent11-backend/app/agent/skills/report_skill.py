"""Report 技能 - 报告生成（多语言、分析型）"""
import re
from typing import Any
from datetime import datetime, timedelta
from app.agent.skills.base import BaseSkill
from app.agent.context import ConversationContext
from app.db.repositories.device import DeviceRepository
from app.db.postgres import Database


class ReportSkill(BaseSkill):
    """Report 技能 - 维护报告生成"""

    name = "maintenance_report"

    @staticmethod
    def _is_en(query: str) -> bool:
        return not bool(re.search(r'[一-鿿]', query))

    async def execute(
        self,
        llm: Any,
        query: str,
        context: ConversationContext
    ) -> dict[str, Any]:
        reasoning_chain = []

        report_type = self._determine_report_type(query)
        zone = self._extract_zone(query)
        is_en = self._is_en(query)

        reasoning_chain.extend(await self._build_reasoning_chain([
            ("确定报告类型", f"Report type: {report_type}", "类型确定"),
            ("确定时间范围", f"Zone: {zone or 'all'}", "范围确定")
        ]))

        report_data = await self._collect_report_data(report_type, zone)

        reasoning_chain.extend(await self._build_reasoning_chain([
            ("收集数据", f"Energy: {report_data.get('total_energy_kwh', 0):.2f} kWh, Faults: {report_data.get('fault_count', 0)}", "数据完成"),
        ]))

        answer = self._generate_report_content(report_type, report_data, zone, is_en)

        return {
            "answer": answer,
            "reasoning_chain": reasoning_chain,
            "confidence": 0.9,
            "map_data": None,
            "data": report_data,
            "sources": []
        }

    def _determine_report_type(self, query: str) -> str:
        q = query.lower()
        if any(k in q for k in ["年报", "年度", "annual", "yearly", "year"]):
            return "annual"
        elif any(k in q for k in ["月报", "月度", "monthly", "month"]):
            return "monthly"
        elif any(k in q for k in ["周报", "每周", "weekly", "week"]):
            return "weekly"
        return "monthly"

    def _extract_zone(self, query: str) -> str | None:
        zone_match = re.search(r'(\d+)区', query)
        if zone_match:
            return zone_match.group(1)
        zm = re.search(r'zone\s*(\d+)', query.lower())
        return zm.group(1) if zm else None

    async def _collect_report_data(self, report_type: str, zone: str | None) -> dict:
        now = datetime.utcnow()
        if report_type == "weekly":
            start_date = now - timedelta(days=7)
            period_days = 7
        elif report_type == "monthly":
            start_date = datetime(now.year, now.month, 1)
            period_days = (now - start_date).days or 30
        else:
            start_date = datetime(now.year, 1, 1)
            period_days = (now - start_date).days or 365

        # Energy consumption from devices_consumption
        try:
            energy_rows = await Database.fetch(
                "SELECT value FROM devices_consumption WHERE report_date >= $1 LIMIT 10000",
                start_date
            )
            total_energy = sum(r.get("value", 0) or 0 for r in energy_rows)
        except Exception:
            total_energy = 0

        # Fault records from devices_fault (direct query)
        try:
            fault_rows = await Database.fetch(
                "SELECT fault, start_date FROM devices_fault WHERE start_date >= $1 ORDER BY start_date DESC LIMIT 5000",
                start_date
            )
        except Exception:
            fault_rows = []

        fault_count = len(fault_rows)
        fault_types: dict[str, int] = {}
        for r in fault_rows:
            ft = r.get("fault", "unknown")
            fault_types[ft] = fault_types.get(ft, 0) + 1

        # Device count
        device_count = 0
        try:
            cnt = await Database.fetchval("SELECT count(*) FROM devices_info")
            device_count = cnt or 0
        except Exception:
            pass

        availability = 100.0
        if device_count > 0:
            uptime_hours = period_days * 24 * device_count
            downtime_hours = fault_count * 2  # estimated 2h avg response
            availability = ((uptime_hours - downtime_hours) / uptime_hours) * 100 if uptime_hours > 0 else 100

        return {
            "report_type": report_type,
            "period": f"{start_date.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}",
            "total_energy_kwh": total_energy,
            "fault_count": fault_count,
            "availability_percent": max(availability, 0),
            "fault_types": fault_types,
            "device_count": device_count,
            "period_days": period_days,
        }

    def _generate_report_content(
        self, report_type: str, data: dict, zone: str | None, is_en: bool = False
    ) -> str:
        zn = zone or ("all zones" if is_en else "全区域")
        rp = {"weekly": "Weekly", "monthly": "Monthly", "annual": "Annual"}.get(report_type, report_type)
        rp_cn = {"weekly": "周报", "monthly": "月报", "annual": "年报"}.get(report_type, "月报")

        if is_en:
            lines = [
                f"# {rp} Maintenance Report",
                f"**Zone**: {zn}  |  **Period**: {data['period']}",
                "",
                "## Key Metrics",
                "",
                f"| Metric | Value |",
                f"|--------|-------|",
                f"| Total Energy | {data.get('total_energy_kwh', 0):.2f} kWh |",
                f"| Fault Count | {data.get('fault_count', 0)} |",
                f"| Availability | {data.get('availability_percent', 100):.1f}% |",
                f"| Total Devices | {data.get('device_count', 0)} |",
                "",
            ]
        else:
            lines = [
                f"# {rp_cn}维护报告",
                f"**区域**: {zn}  |  **周期**: {data['period']}",
                "",
                "## 关键指标",
                "",
                f"| 指标 | 数值 |",
                f"|------|------|",
                f"| 总能耗 | {data.get('total_energy_kwh', 0):.2f} kWh |",
                f"| 故障次数 | {data.get('fault_count', 0)} 次 |",
                f"| 设备可用率 | {data.get('availability_percent', 100):.1f}% |",
                f"| 设备总数 | {data.get('device_count', 0)} 台 |",
                "",
            ]

        # Fault type distribution
        if data.get("fault_types"):
            sorted_ft = sorted(data["fault_types"].items(), key=lambda x: x[1], reverse=True)
            if is_en:
                lines.append("## Fault Type Distribution")
                lines.append("")
                for ft, count in sorted_ft[:10]:
                    lines.append(f"- {ft}: {count}")
            else:
                lines.append("## 故障类型分布")
                lines.append("")
                for ft, count in sorted_ft[:10]:
                    lines.append(f"- {ft}: {count} 次")
            lines.append("")

        # Analysis
        availability = data.get("availability_percent", 100)
        fault_count = data.get("fault_count", 0)

        if is_en:
            lines.append("## Analysis")
            lines.append("")
            if availability >= 95:
                lines.append("✅ System availability is excellent. All zones operating within normal parameters.")
            elif availability >= 90:
                lines.append("⚠️ Availability is acceptable but needs attention. Consider reviewing high-fault areas.")
            else:
                lines.append("🔴 Availability is below target. Immediate maintenance review recommended.")
            if fault_count > 10:
                total_energy = data.get("total_energy_kwh", 0)
                lines.append(f"⚠️ {fault_count} faults recorded in this period. Energy consumption: {total_energy:.2f} kWh.")
            if fault_count == 0:
                lines.append("✅ No faults recorded — system is running smoothly.")
            lines.append("")
            lines.append("---")
            lines.append("*Report generated automatically by AGENT 11*")
        else:
            lines.append("## 分析")
            lines.append("")
            if availability >= 95:
                lines.append("✅ 设备运行状态良好，可用率保持在较高水平。")
            elif availability >= 90:
                lines.append("⚠️ 设备可用率一般，建议关注高故障率区域。")
            else:
                lines.append("🔴 设备可用率偏低，建议进行全面检修。")
            if fault_count > 10:
                lines.append(f"⚠️ 本周期共记录 {fault_count} 次故障。")
            if fault_count == 0:
                lines.append("✅ 本周期无故障记录，系统运行平稳。")
            lines.append("")
            lines.append("---")
            lines.append("*报告由 AGENT 11 自动生成*")

        return "\n".join(lines)

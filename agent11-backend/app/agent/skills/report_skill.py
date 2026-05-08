"""Report 技能 - 报告生成"""
from typing import Any
from datetime import datetime, timedelta
from app.agent.skills.base import BaseSkill
from app.agent.context import ConversationContext
from app.db.repositories.device import DeviceRepository
from app.db.repositories.fault import FaultRepository
from app.db.repositories.reading import ReadingRepository


class ReportSkill(BaseSkill):
    """Report 技能 - 维护报告生成"""

    name = "maintenance_report"

    async def execute(
        self,
        llm: Any,
        query: str,
        context: ConversationContext
    ) -> dict[str, Any]:
        """生成维护报告"""
        reasoning_chain = []

        # 确定报告类型
        report_type = self._determine_report_type(query)
        zone = self._extract_zone(query)

        reasoning_chain.extend(await self._build_reasoning_chain([
            ("确定报告类型", f"报告类型: {report_type}", "类型确定"),
            ("确定时间范围", f"区域: {zone or '全部'}", "范围确定")
        ]))

        # 收集数据
        report_data = await self._collect_report_data(report_type, zone)

        reasoning_chain.extend(await self._build_reasoning_chain([
            ("收集指标数据", f"能耗: {report_data.get('total_energy_kwh', 0):.2f} kWh", "数据收集完成"),
            ("生成报告", "格式化报告内容", "报告生成完成")
        ]))

        # 生成报告内容
        answer = self._generate_report_content(report_type, report_data, zone)

        return {
            "answer": answer,
            "reasoning_chain": reasoning_chain,
            "confidence": 0.9,
            "map_data": None,
            "data": report_data,
            "sources": []
        }

    def _determine_report_type(self, query: str) -> str:
        """确定报告类型"""
        if "年报" in query or "年度" in query:
            return "annual"
        elif "月报" in query or "月度" in query:
            return "monthly"
        elif "周报" in query or "每周" in query:
            return "weekly"
        else:
            return "monthly"  # 默认月报

    def _extract_zone(self, query: str) -> str | None:
        """提取区域"""
        import re
        zone_match = re.search(r'(\d+)区', query)
        return zone_match.group(1) if zone_match else None

    async def _collect_report_data(self, report_type: str, zone: str | None) -> dict:
        """收集报告数据"""
        # 计算时间范围
        now = datetime.utcnow()

        if report_type == "weekly":
            start_date = now - timedelta(days=7)
            period_days = 7
        elif report_type == "monthly":
            start_date = datetime(now.year, now.month, 1)
            period_days = (now - start_date).days or 30
        else:  # annual
            start_date = datetime(now.year, 1, 1)
            period_days = (now - start_date).days or 365

        # 查询能耗
        energy_records = await ReadingRepository.get_energy_readings(
            geozone=zone,
            start_time=start_date,
            end_time=now,
            limit=10000
        )
        total_energy = sum(e.get("energy_kwh", 0) for e in energy_records)

        # 查询故障
        faults = await FaultRepository.find_active(geozone=zone, limit=1000)
        fault_count = len(faults)

        # 计算响应时间
        response_times = [
            f.get("response_time_hours", 0)
            for f in faults
            if f.get("resolved_at") and f.get("detected_at")
        ]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0

        # 计算可用率
        device_count = await DeviceRepository.count()
        if device_count > 0:
            uptime_hours = period_days * 24 * device_count
            downtime_hours = fault_count * avg_response_time
            availability = ((uptime_hours - downtime_hours) / uptime_hours) * 100
        else:
            availability = 100

        # 故障类型分布
        fault_types: dict[str, int] = {}
        for f in faults:
            ft = f.get("fault_type", "unknown")
            fault_types[ft] = fault_types.get(ft, 0) + 1

        return {
            "report_type": report_type,
            "period": f"{start_date.strftime('%Y-%m-%d')} 至 {now.strftime('%Y-%m-%d')}",
            "total_energy_kwh": total_energy,
            "fault_count": fault_count,
            "avg_response_time_hours": avg_response_time,
            "availability_percent": availability,
            "fault_types": fault_types,
            "device_count": device_count,
            "period_days": period_days
        }

    def _generate_report_content(
        self,
        report_type: str,
        data: dict,
        zone: str | None
    ) -> str:
        """生成报告内容"""
        zone_text = f"{zone}区域" if zone else "全区域"

        lines = [
            f"# {report_type.title()}维护报告",
            f"## {zone_text}",
            f"**报告周期**: {data['period']}",
            "",
            "## 关键指标",
            "",
            f"| 指标 | 数值 |",
            f"|------|------|",
            f"| 总能耗 | {data.get('total_energy_kwh', 0):.2f} kWh |",
            f"| 故障次数 | {data.get('fault_count', 0)} 次 |",
            f"| 平均响应时间 | {data.get('avg_response_time_hours', 0):.1f} 小时 |",
            f"| 设备可用率 | {data.get('availability_percent', 100):.1f}% |",
            f"| 设备总数 | {data.get('device_count', 0)} 台 |",
            ""
        ]

        if data.get("fault_types"):
            lines.append("## 故障类型分布")
            lines.append("")
            for ft, count in sorted(data["fault_types"].items(), key=lambda x: x[1], reverse=True):
                lines.append(f"- {ft}: {count} 次")
            lines.append("")

        # 添加趋势分析
        lines.append("## 趋势分析")
        lines.append("")
        availability = data.get("availability_percent", 100)
        if availability >= 95:
            lines.append("设备运行状态良好，可用率保持在较高水平。")
        elif availability >= 90:
            lines.append("设备可用率一般，建议关注高故障率设备。")
        else:
            lines.append("设备可用率偏低，建议进行全面检修。")

        fault_count = data.get("fault_count", 0)
        if fault_count > 10:
            lines.append(f"本月故障次数较多({fault_count}次)，建议分析故障原因。")

        return "\n".join(lines)

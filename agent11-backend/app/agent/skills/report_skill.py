"""Report 技能 - 月度路灯维护报告（模板来自 PDF 模版）"""
import re, math
from typing import Any
from datetime import datetime, timedelta
from app.agent.skills.base import BaseSkill
from app.agent.context import ConversationContext
from app.db.postgres import Database


# 故障类型中文映射（数据库英文值 → 模版中文分类）
FAULT_TYPE_CN = {
    "supply_loss": "停电/供电中断",
    "high_temperature": "温度过高",
    "meter_fault": "电表故障",
    "lamp_failure": "灯具故障",
    "lamp_power_too_high": "灯具功率过高",
    "lamp_power_too_low": "灯具功率过低",
    "dimming_failure": "调光故障",
    "lamp_unexpected_on": "灯具意外亮起",
    "current_too_high": "电流过高",
    "current_too_low": "电流过低",
    "power_factor_too_low": "功率因数过低",
    "relay_failure": "继电器故障",
    "control_gear_comm_failure": "通信故障",
    "cycling_failure": "循环故障",
    "supply_voltage_too_high": "供电电压过高",
    "supply_voltage_too_low": "供电电压过低",
    "group_control_fault": "分组控制故障",
    "link_control_fault": "链路控制故障",
    "lux_communication_fault": "光照通信故障",
    "high_load_power": "高负载功率",
    "lux_module_fault": "光照模块故障",
}


class ReportSkill(BaseSkill):
    """Report 技能 - 月度路灯维护报告（PDF 模版格式）"""

    name = "maintenance_report"

    async def execute(
        self,
        llm: Any,
        query: str,
        context: ConversationContext
    ) -> dict[str, Any]:
        reasoning_chain = []
        report_type = self._determine_report_type(query)
        zone = self._extract_zone(query)

        reasoning_chain.extend(await self._build_reasoning_chain([
            ("确定报告类型", f"Report type: {report_type}", "类型确定"),
        ]))

        report_data = await self._collect_report_data(report_type, zone)

        reasoning_chain.extend(await self._build_reasoning_chain([
            ("收集数据", f"故障数: {report_data.get('fault_count', 0)}", "完成"),
        ]))

        answer = self._generate_report_content(report_data, llm, query)

        return {
            "answer": answer,
            "reasoning_chain": reasoning_chain,
            "confidence": 0.9,
            "map_data": None,
            "data": report_data,
            "sources": [],
        }

    def _determine_report_type(self, query: str) -> str:
        q = query.lower()
        if any(k in q for k in ["月报", "月度", "monthly", "month"]):
            return "monthly"
        elif any(k in q for k in ["周报", "每周", "weekly", "week"]):
            return "weekly"
        elif any(k in q for k in ["年报", "年度", "annual", "yearly", "year"]):
            return "annual"
        return "monthly"

    def _extract_zone(self, query: str) -> str | None:
        zm = re.search(r'(\d+)区', query)
        if zm:
            return zm.group(1)
        zm = re.search(r'zone\s*(\d+)', query.lower())
        return zm.group(1) if zm else None

    async def _collect_report_data(self, report_type: str, zone: str | None) -> dict:
        now = datetime.utcnow()
        year, month = now.year, now.month
        month_start = datetime(year, month, 1)
        prev_month = datetime(year - 1, month, 1) if month == 1 else datetime(year, month - 1, 1)

        # 本月故障
        try:
            fault_rows = await Database.fetch(
                "SELECT fault, start_date FROM devices_fault WHERE start_date >= $1 AND start_date < $2 ORDER BY start_date",
                month_start, now
            )
        except Exception:
            fault_rows = []

        # 上月故障
        try:
            prev_faults = await Database.fetch(
                "SELECT fault, start_date FROM devices_fault WHERE start_date >= $1 AND start_date < $2",
                prev_month, month_start
            )
        except Exception:
            prev_faults = []

        # 设备总数
        device_count = 0
        try:
            cnt = await Database.fetchval("SELECT count(*) FROM devices_info")
            device_count = cnt or 0
        except Exception:
            pass

        # 能耗
        try:
            energy_rows = await Database.fetch(
                "SELECT value FROM devices_consumption WHERE report_date >= $1 LIMIT 10000",
                month_start
            )
            total_energy = sum(r.get("value", 0) or 0 for r in energy_rows)
        except Exception:
            total_energy = 0

        # 📊 按故障类型统计
        fault_type_counts: dict[str, int] = {}
        for r in fault_rows:
            ft = r.get("fault", "other")
            fault_type_counts[ft] = fault_type_counts.get(ft, 0) + 1

        # 分类汇总（对应模版五大类）
        categories = {"灯具故障": 0, "线路/通信故障": 0, "配电箱/供电故障": 0, "开关电源故障": 0, "灯杆故障": 0, "其他故障": 0}
        cat_detail = {"灯具故障": [], "线路/通信故障": [], "配电箱/供电故障": [], "开关电源故障": [], "灯杆故障": [], "其他故障": []}
        lamp_keys = {"lamp_failure", "lamp_power_too_high", "lamp_power_too_low", "dimming_failure", "lamp_unexpected_on"}
        line_keys = {"control_gear_comm_failure", "lux_communication_fault", "lux_module_fault", "link_control_fault", "group_control_fault"}
        power_keys = {"supply_loss", "supply_voltage_too_high", "supply_voltage_too_low", "current_too_high", "current_too_low", "power_factor_too_low"}
        switch_keys = {"relay_failure", "cycling_failure", "high_temperature", "high_load_power"}

        for ft, cnt in fault_type_counts.items():
            cn = FAULT_TYPE_CN.get(ft, ft)
            if ft in lamp_keys:
                categories["灯具故障"] += cnt
                cat_detail["灯具故障"].append(f"{cn} {cnt}起")
            elif ft in line_keys:
                categories["线路/通信故障"] += cnt
                cat_detail["线路/通信故障"].append(f"{cn} {cnt}起")
            elif ft in power_keys:
                categories["配电箱/供电故障"] += cnt
                cat_detail["配电箱/供电故障"].append(f"{cn} {cnt}起")
            elif ft in switch_keys:
                categories["开关电源故障"] += cnt
                cat_detail["开关电源故障"].append(f"{cn} {cnt}起")
            else:
                categories["其他故障"] += cnt
                cat_detail["其他故障"].append(f"{cn} {cnt}起")

        total_faults = sum(categories.values())
        prev_total = len(prev_faults)

        # 30天平均高灯率/在线率/故障率估算
        on_rate = round(100 - (total_faults / max(device_count * 30, 1)) * 100, 2) if device_count else 100
        fault_rate = round(100 - on_rate, 2)

        return {
            "report_year": year,
            "report_month": month,
            "device_count": device_count,
            "total_energy_kwh": total_energy,
            "fault_count": total_faults,
            "prev_fault_count": prev_total,
            "on_rate": on_rate,
            "fault_rate": fault_rate,
            "categories": categories,
            "cat_detail": cat_detail,
            "fault_type_counts": fault_type_counts,
            "period": f"{month_start.strftime('%Y-%m-%d')} ~ {now.strftime('%Y-%m-%d')}",
        }

    def _generate_report_content(self, data: dict, llm: Any, query: str) -> str:
        """严格按照 PDF 模版格式生成报告"""
        y, m = data["report_year"], data["report_month"]
        dc = data["device_count"]
        fc = data["fault_count"]
        pfc = data["prev_fault_count"]
        on_r = data["on_rate"]
        f_r = data["fault_rate"]
        cats = data["categories"]
        cat_d = data["cat_detail"]

        def bar(pct):
            n = max(1, round(pct / 5))
            return "█" * min(n, 20)

        lines = [
            "=" * 60,
            f"  月度路灯维护报告",
            f"  {y}年{m}月",
            "=" * 60,
            "",
            "━" * 60,
            "一、报告基础信息",
            "━" * 60,
            f"  月份：{y}年{m}月",
            f"  维护路灯总数：{dc} 台",
            f"  报告周期：{data['period']}",
            "",
            "━" * 60,
            "二、本月核心运维 KPI",
            "━" * 60,
            f"  30天平均在线率：              {on_r:.2f}%   {'✅ 达标' if on_r >= 98 else '⚠️ 不达标'}（目标98%）",
            f"  30天平均故障率：              {f_r:.2f}%   {'✅ 达标' if f_r <= 2 else '⚠️ 不达标'}（目标 < 2%）",
            f"  本月故障总数量：              {fc} 起",
            f"  上月故障数量：                {pfc} 起",
            f"  故障环比变化：                {'📉 下降' if fc <= pfc else '📈 上升'} {abs(fc - pfc)} 起",
            f"  本月能耗：                    {data['total_energy_kwh']:.2f} kWh",
            "",
            "━" * 60,
            "三、本月养护工作完成情况",
            "━" * 60,
            f"  故障维修：{fc} 起",
            f"  灯具维修：{cats['灯具故障']} 起",
            f"  线路排查检修：{cats['线路/通信故障']} 起",
            f"  配电箱维护：{cats['配电箱/供电故障']} 起",
            f"  开关电源维护：{cats['开关电源故障']} 起",
            f"  其他维护：{cats['其他故障']} 起",
            "",
            "━" * 60,
            "四、本月故障明细",
            "━" * 60,
        ]

        if data.get("fault_type_counts"):
            lines.append("  故障类型分布：")
            for ft, cnt in sorted(data["fault_type_counts"].items(), key=lambda x: -x[1]):
                cn = FAULT_TYPE_CN.get(ft, ft)
                pct = cnt * 100 / max(fc, 1)
                lines.append(f"    {cn:16s}  {cnt:3d} 起 ({pct:5.1f}%)  {bar(pct)}")
        else:
            lines.append("  本月无故障记录。")

        lines += [
            "",
            "━" * 60,
            "五、故障分类统计",
            "━" * 60,
        ]

        for cat_name in ["灯具故障", "线路/通信故障", "配电箱/供电故障", "开关电源故障", "灯杆故障", "其他故障"]:
            cnt = cats[cat_name]
            pct = cnt * 100 / max(fc, 1)
            lines.append(f"  {cat_name:14s}  {cnt:3d} 起 ({pct:5.1f}%)")
            if cat_d[cat_name]:
                lines.append(f"    → {'；'.join(cat_d[cat_name][:4])}")

        lines += [
            "",
            "━" * 60,
            "六、故障分析与月度工作总结",
            "━" * 60,
        ]

        if fc == 0:
            lines += [
                "1. 故障类型分布与核心原因分析：",
                "   本月无故障记录，系统运行平稳。",
                "",
                "2. 故障高发区域/路段与时间规律分析：",
                "   无。",
                "",
                "3. 本月工作核心成果与亮点：",
                f"   ① 全系统 {dc} 台设备正常运行。",
                f"   ② 在线率 {on_r:.2f}%，达到运维目标。",
                "",
                "4. 预算执行情况分析：",
                f"   本月能耗 {data['total_energy_kwh']:.2f} kWh。",
            ]
        else:
            top_cat = sorted(cats.items(), key=lambda x: -x[1])[0]
            lines += [
                "1. 故障类型分布与核心原因分析：",
                f"   本月共发生 {fc} 起故障。主要集中在「{top_cat[0]}」（{top_cat[1]} 起，"
                f"占 {top_cat[1]*100//fc}%），为主要故障类型。",
                "",
                "2. 本月工作核心成果与亮点：",
                f"   ① 处理故障 {fc} 起，其中{'灯具故障' if cats['灯具故障'] > 0 else '线路故障'}为重点处理方向。",
                f"   ② 系统在线率 {on_r:.2f}%。",
                "",
                "3. 预算执行情况分析：",
                f"   本月能耗 {data['total_energy_kwh']:.2f} kWh。",
            ]

        lines += [
            "",
            "━" * 60,
            "七、改善措施与整改计划",
            "━" * 60,
            "  基于本月数据分析，建议以下改善措施：",
            "  ① 加强高发区域巡检频次，预防性维护前移。",
            "  ② 针对高发故障类型，储备备品备件。",
            f"  {'③ 关注能耗变化趋势，优化运行策略。' if data['total_energy_kwh'] > 0 else ''}",
            "",
            "━" * 60,
            "八、下月重点工作计划",
            "━" * 60,
            "  ① 继续推进日常巡检与维护工作。",
            "  ② 对本月高发故障区域进行重点复查。",
            "  ③ 做好备品备件采购计划。",
            "",
            "━" * 60,
            "九、审批签字",
            "━" * 60,
            "  养护单位负责人：               监理单位负责人：             业主单位负责人：",
            "",
            "  签字：                         签字：                       签字：",
            f"  日期：{y}年{m}月{datetime.now().day}日           日期：                      日期：",
            "",
            "=" * 60,
            "  报告由 AGENT 11 自动生成",
            "=" * 60,
        ]

        return "\n".join(lines)

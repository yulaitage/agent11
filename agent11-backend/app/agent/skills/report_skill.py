"""Report 技能 - 周度/月度路灯维护报告（Excel 模版格式）"""
import re, math
from typing import Any
from datetime import datetime, timedelta
from app.agent.skills.base import BaseSkill
from app.agent.context import ConversationContext
from app.db.postgres import Database


FAULT_TYPE_CN = {
    "supply_loss": "停电/供电中断", "high_temperature": "温度过高", "meter_fault": "电表故障",
    "lamp_failure": "灯具故障", "lamp_power_too_high": "灯具功率过高", "lamp_power_too_low": "灯具功率过低",
    "dimming_failure": "调光故障", "lamp_unexpected_on": "灯具意外亮起",
    "current_too_high": "电流过高", "current_too_low": "电流过低", "power_factor_too_low": "功率因数过低",
    "relay_failure": "继电器故障", "control_gear_comm_failure": "通信故障", "cycling_failure": "循环故障",
    "supply_voltage_too_high": "供电电压过高", "supply_voltage_too_low": "供电电压过低",
    "group_control_fault": "分组控制故障", "link_control_fault": "链路控制故障",
    "lux_communication_fault": "光照通信故障", "high_load_power": "高负载功率", "lux_module_fault": "光照模块故障",
}

CATEGORY_MAP = {
    "lamp_failure": "灯具故障", "lamp_power_too_high": "灯具故障", "lamp_power_too_low": "灯具故障",
    "dimming_failure": "灯具故障", "lamp_unexpected_on": "灯具故障",
    "control_gear_comm_failure": "线路/通信故障", "lux_communication_fault": "线路/通信故障",
    "lux_module_fault": "线路/通信故障", "link_control_fault": "线路/通信故障", "group_control_fault": "线路/通信故障",
    "supply_loss": "配电箱/供电故障", "supply_voltage_too_high": "配电箱/供电故障",
    "supply_voltage_too_low": "配电箱/供电故障", "current_too_high": "配电箱/供电故障",
    "current_too_low": "配电箱/供电故障", "power_factor_too_low": "配电箱/供电故障",
    "relay_failure": "开关电源故障", "cycling_failure": "开关电源故障",
    "high_temperature": "开关电源故障", "high_load_power": "开关电源故障",
}


class ReportSkill(BaseSkill):
    """Report 技能 - 周度/月度路灯维护报告（Excel 模版格式）"""

    name = "maintenance_report"

    async def execute(self, llm: Any, query: str, context: ConversationContext) -> dict[str, Any]:
        reasoning_chain = []
        report_type = self._determine_report_type(query)
        reasoning_chain.extend(await self._build_reasoning_chain([("确定报告类型", report_type, "完成")]))
        report_data = await self._collect_report_data(report_type)
        reasoning_chain.extend(await self._build_reasoning_chain([("收集数据", f"故障:{report_data.get('fault_count',0)}起", "完成")]))
        answer = self._generate_report(report_type, report_data)
        return {"answer": answer, "reasoning_chain": reasoning_chain, "confidence": 0.9, "map_data": None, "data": report_data, "sources": []}

    def _determine_report_type(self, query: str) -> str:
        q = query.lower()
        if any(k in q for k in ["周报", "每周", "weekly", "week"]):
            return "weekly"
        elif any(k in q for k in ["月报", "月度", "monthly", "month"]):
            return "monthly"
        elif any(k in q for k in ["年报", "年度", "annual", "yearly", "year"]):
            return "annual"
        return "monthly"

    async def _collect_report_data(self, report_type: str) -> dict:
        now = datetime.utcnow()
        year, month, day = now.year, now.month, now.day

        if report_type == "weekly":
            # 本周一 ~ 至今
            week_start = now - timedelta(days=now.weekday())
            period_name = f"第{(day - 1) // 7 + 1}周"
            prev_start = week_start - timedelta(days=7)
        elif report_type == "monthly":
            week_start = datetime(year, month, 1)
            period_name = f"{year}年{month}月"
            prev_start = datetime(year - 1, month, 1) if month == 1 else datetime(year, month - 1, 1)
        else:
            week_start = datetime(year, 1, 1)
            period_name = f"{year}年"
            prev_start = datetime(year - 1, 1, 1)

        try:
            fault_rows = await Database.fetch(
                "SELECT fault, start_date FROM devices_fault WHERE start_date >= $1 AND start_date < $2 ORDER BY start_date",
                week_start, now
            )
            prev_rows = await Database.fetch(
                "SELECT fault FROM devices_fault WHERE start_date >= $1 AND start_date < $2",
                prev_start, week_start
            )
        except Exception:
            fault_rows = []
            prev_rows = []

        device_count = 0
        try:
            cnt = await Database.fetchval("SELECT count(*) FROM devices_info")
            device_count = cnt or 0
        except Exception:
            pass

        fault_type_counts: dict[str, int] = {}
        for r in fault_rows:
            ft = r.get("fault", "other")
            fault_type_counts[ft] = fault_type_counts.get(ft, 0) + 1

        categories = {"灯具故障": 0, "线路/通信故障": 0, "配电箱/供电故障": 0, "开关电源故障": 0, "灯杆故障": 0, "其他故障": 0}
        cat_detail = {k: [] for k in categories}
        for ft, cnt in fault_type_counts.items():
            cat = CATEGORY_MAP.get(ft, "其他故障")
            categories[cat] += cnt
            cat_detail[cat].append(f"{FAULT_TYPE_CN.get(ft, ft)} {cnt}起")

        total_faults = sum(categories.values())
        prev_total = len(prev_rows)
        on_rate = round(100 - (total_faults / max(device_count * 7, 1)) * 100, 2) if device_count else 100
        fault_rate = round(100 - on_rate, 2)

        return {
            "report_type": report_type, "period_name": period_name,
            "year": year, "month": month, "day": day,
            "device_count": device_count, "fault_count": total_faults,
            "prev_fault_count": prev_total, "on_rate": on_rate, "fault_rate": fault_rate,
            "categories": categories, "cat_detail": cat_detail,
            "fault_type_counts": fault_type_counts,
            "period": f"{week_start.strftime('%Y-%m-%d')} ~ {now.strftime('%Y-%m-%d')}",
        }

    def _generate_report(self, report_type: str, data: dict) -> str:
        if report_type == "weekly":
            return self._weekly_report(data)
        return self._monthly_report(data)

    def _weekly_report(self, data: dict) -> str:
        y, m, d = data["year"], data["month"], data["day"]
        dc, fc, pfc = data["device_count"], data["fault_count"], data["prev_fault_count"]
        on_r, f_r = data["on_rate"], data["fault_rate"]
        cats, cat_d = data["categories"], data["cat_detail"]

        lines = [
            "=" * 60,
            f"  周度路灯维护报告",
            f"  {data['period_name']}  |  {data['period']}",
            "=" * 60, "",
            "━" * 60,
            "一、报告基础信息",
            "━" * 60,
            f"  报告周期：{data['period']}",
            f"  维护路灯总灯数：{dc} 台", "",
            "━" * 60,
            "二、本周核心运维 KPI",
            "━" * 60,
            f"  7天平均亮灯率：            {on_r:.2f}%   {'✅ 达标' if on_r >= 98 else '⚠️ 不达标'}（目标≥98%）",
            f"  7天平均在线率：            {on_r:.2f}%   {'✅ 达标' if on_r >= 99 else '⚠️ 不达标'}（目标≥99%）",
            f"  7天平均故障率：            {f_r:.2f}%   {'✅ 达标' if f_r <= 2 else '⚠️ 不达标'}（目标≤2%）",
            f"  本周故障总数量：           {fc} 起",
            f"  上周故障数量：             {pfc} 起",
            f"  故障环比变化：             {'📉 下降' if fc <= pfc else '📈 上升'} {abs(fc - pfc)} 起", "",
            "━" * 60,
            "三、本周养护工作完成情况",
            "━" * 60,
            f"  故障维修：{fc} 起",
            f"  灯具维修：{cats['灯具故障']} 起",
            f"  线路排查检修：{cats['线路/通信故障']} 起",
            f"  配电箱维护：{cats['配电箱/供电故障']} 起",
            f"  开关电源维护：{cats['开关电源故障']} 起", "",
            "━" * 60,
            "四、本周故障明细全链路记录",
            "━" * 60,
        ]
        if data.get("fault_type_counts"):
            lines.append("  故障类型 | 数量 | 占比")
            lines.append("  " + "-" * 40)
            for ft, cnt in sorted(data["fault_type_counts"].items(), key=lambda x: -x[1]):
                cn = FAULT_TYPE_CN.get(ft, ft)
                pct = cnt * 100 / max(fc, 1)
                bar = "█" * max(1, min(round(pct / 5), 20))
                lines.append(f"  {cn:14s}  {cnt:3d}  ({pct:5.1f}%)  {bar}")
        else:
            lines.append("  本周无故障记录。")
        lines += ["", "━" * 60, "五、故障分类统计", "━" * 60]
        for cat_name in ["灯具故障", "线路/通信故障", "配电箱/供电故障", "开关电源故障", "灯杆故障", "其他故障"]:
            cnt = cats[cat_name]
            pct = cnt * 100 / max(fc, 1)
            lines.append(f"  {cat_name:14s}  {cnt:3d} 起 ({pct:5.1f}%)")
            if cat_d[cat_name]:
                lines.append(f"    → {'；'.join(cat_d[cat_name][:3])}")
        lines += ["", "━" * 60, "六、故障分析与本周工作总结", "━" * 60]
        if fc == 0:
            lines += ["1. 故障类型分布分析：本周无故障记录，系统运行平稳。", "", "2. 本周工作核心亮点：", f"   ① 全系统 {dc} 台设备正常运行。", f"   ② 亮灯率 {on_r:.2f}%，达到运维目标。", ""]
        else:
            top_cat = sorted(cats.items(), key=lambda x: -x[1])[0]
            lines += ["1. 故障类型分布分析：", f"   本周共 {fc} 起故障，主要集中在「{top_cat[0]}」（{top_cat[1]} 起，{top_cat[1]*100//max(fc,1)}%）。", "", "2. 本周工作核心亮点：", f"   ① 处理故障 {fc} 起。", f"   ② 亮灯率 {on_r:.2f}%。", ""]
        lines += ["━" * 60, "七、改善措施与整改计划", "━" * 60, "  ① 加强高发区域巡检频次。", "  ② 针对高发故障类型储备备品备件。", "", "━" * 60, "八、下周工作计划", "━" * 60, "  ① 继续推进日常巡检与维护工作。", "  ② 对本周高发故障区域进行重点复查。", "", "━" * 60, "审批签字", "━" * 60, "  养护单位负责人：         监理单位负责人：         业主单位负责人：", "", "  签字：                   签字：                   签字：", f"  日期：{y}年{m}月{d}日   日期：                  日期：", "", "=" * 60, "  报告由 AGENT 11 自动生成", "=" * 60]
        return "\n".join(lines)

    def _monthly_report(self, data: dict) -> str:
        y, m, dc = data["year"], data["month"], data["device_count"]
        fc, pfc = data["fault_count"], data["prev_fault_count"]
        on_r, f_r = data["on_rate"], data["fault_rate"]
        cats, cat_d = data["categories"], data["cat_detail"]

        def bar(pct):
            return "█" * min(max(1, round(pct / 5)), 20)

        lines = [
            "=" * 60, f"  月度路灯维护报告  {y}年{m}月", "=" * 60, "",
            "━" * 60, "一、报告基础信息", "━" * 60,
            f"  月份：{y}年{m}月  |  维护路灯总数：{dc} 台  |  周期：{data['period']}", "",
            "━" * 60, "二、本月核心运维 KPI", "━" * 60,
            f"  30天平均在线率：            {on_r:.2f}%   {'✅ 达标' if on_r >= 98 else '⚠️ 不达标'}（目标98%）",
            f"  30天平均故障率：            {f_r:.2f}%   {'✅ 达标' if f_r <= 2 else '⚠️ 不达标'}（目标 < 2%）",
            f"  本月故障总数量：            {fc} 起",
            f"  上月故障数量：              {pfc} 起",
            f"  故障环比变化：              {'📉 下降' if fc <= pfc else '📈 上升'} {abs(fc - pfc)} 起", "",
            "━" * 60, "三、本月养护工作完成情况", "━" * 60,
            f"  故障维修：{fc} 起  |  灯具维修：{cats['灯具故障']} 起  |  线路排查检修：{cats['线路/通信故障']} 起",
            f"  配电箱维护：{cats['配电箱/供电故障']} 起  |  开关电源维护：{cats['开关电源故障']} 起", "",
            "━" * 60, "四、本月故障明细", "━" * 60,
        ]
        if data.get("fault_type_counts"):
            for ft, cnt in sorted(data["fault_type_counts"].items(), key=lambda x: -x[1]):
                cn = FAULT_TYPE_CN.get(ft, ft)
                pct = cnt * 100 / max(fc, 1)
                lines.append(f"  {cn:16s}  {cnt:3d} 起 ({pct:5.1f}%)  {bar(pct)}")
        else:
            lines.append("  本月无故障记录。")
        lines += ["", "━" * 60, "五、故障分类统计", "━" * 60]
        for cn in ["灯具故障", "线路/通信故障", "配电箱/供电故障", "开关电源故障", "灯杆故障", "其他故障"]:
            cnt = cats[cn]
            pct = cnt * 100 / max(fc, 1)
            lines.append(f"  {cn:14s}  {cnt:3d} 起 ({pct:5.1f}%)")
            if cat_d[cn]:
                lines.append(f"    → {'；'.join(cat_d[cn][:3])}")
        lines += ["", "━" * 60, "六、故障分析与月度工作总结", "━" * 60]
        if fc == 0:
            lines += ["1. 故障类型分布：本月无故障记录，系统运行平稳。", "", "2. 本月工作核心成果：", f"   ① 全系统 {dc} 台设备正常运行。", f"   ② 在线率 {on_r:.2f}%，达到运维目标。", ""]
        else:
            top = sorted(cats.items(), key=lambda x: -x[1])[0]
            lines += ["1. 故障类型分布与核心原因分析：", f"   本月共 {fc} 起故障。主要集中在「{top[0]}」（{top[1]} 起，{top[1]*100//fc}%）。", "", "2. 本月工作核心成果：", f"   ① 处理故障 {fc} 起。", f"   ② 在线率 {on_r:.2f}%。", ""]
        lines += [
            "━" * 60, "七、改善措施与整改计划", "━" * 60,
            "  ① 加强高发区域巡检频次，预防性维护前移。", "  ② 针对高发故障类型储备备品备件。", "",
            "━" * 60, "八、其他管理事项", "━" * 60, "  1. 耗材使用情况：根据维修记录安排备品采购。", "  2. 安全管理情况：按计划执行安全培训。", "",
            "━" * 60, "九、下月重点工作计划", "━" * 60,
            "  ① 继续推进日常巡检与维护工作。", "  ② 对本月高发故障区域进行重点复查。", "  ③ 做好备品备件采购计划。", "",
            "━" * 60, "审批签字", "━" * 60,
            "  养护单位负责人：         监理单位负责人：         业主单位负责人：",
            "  签字：                   签字：                   签字：",
            f"  日期：{y}年{m}月{data['day']}日   日期：                  日期：",
            "", "=" * 60, "  报告由 AGENT 11 自动生成", "=" * 60,
        ]
        return "\n".join(lines)

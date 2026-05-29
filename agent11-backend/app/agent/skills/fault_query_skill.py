"""Fault Query 技能 - 故障查询"""
import re
from typing import Any
from datetime import datetime
import structlog

from app.agent.skills.base import BaseSkill
from app.agent.context import ConversationContext
from app.db.postgres import Database

logger = structlog.get_logger()


class FaultQuerySkill(BaseSkill):
    """Fault Query 技能 - 查询故障记录"""

    name = "fault_query"

    # 故障类型映射：中文 → 数据库 FAULT ENUM 值
    FAULT_TYPE_MAP = {
        # 灯具相关
        "灯具功率过高": "lamp_power_too_high",
        "功率过高": "lamp_power_too_high",
        "灯具功率过低": "lamp_power_too_low",
        "功率过低": "lamp_power_too_low",
        "灯具故障": "lamp_failure",
        "灯故障": "lamp_failure",
        "调光故障": "dimming_failure",
        "灯具意外亮起": "lamp_unexpected_on",
        "灯意外亮": "lamp_unexpected_on",
        # 电流相关
        "电流过高": "current_too_high",
        "电流过低": "current_too_low",
        "功率因数过低": "power_factor_too_low",
        # 温度相关
        "高温": "high_temperature",
        "温度过高": "high_temperature",
        "过热": "high_temperature",
        # 继电器/控制相关
        "继电器故障": "relay_failure",
        "控制设备通信故障": "control_gear_comm_failure",
        "通信故障": "control_gear_comm_failure",
        "通信中断": "control_gear_comm_failure",
        "循环故障": "cycling_failure",
        "周期性故障": "cycling_failure",
        # 供电相关
        "停电": "supply_loss",
        "断电": "supply_loss",
        "供电中断": "supply_loss",
        "供电电压过高": "supply_voltage_too_high",
        "电压过高": "supply_voltage_too_high",
        "供电电压过低": "supply_voltage_too_low",
        "电压过低": "supply_voltage_too_low",
        # 分组/链路控制
        "分组控制故障": "group_control_fault",
        "链路控制故障": "link_control_fault",
        # 其他
        "光照通信故障": "lux_communication_fault",
        "高负载功率": "high_load_power",
        "负载过高": "high_load_power",
        "电表故障": "meter_fault",
        "光照模块故障": "lux_module_fault",
    }

    # 故障类型反向映射：数据库值 → 中文（保留常见映射用于显示）
    FAULT_TYPE_REVERSE_MAP = {
        "lamp_power_too_high": "灯具功率过高",
        "lamp_power_too_low": "灯具功率过低",
        "lamp_failure": "灯具故障",
        "dimming_failure": "调光故障",
        "current_too_high": "电流过高",
        "current_too_low": "电流过低",
        "power_factor_too_low": "功率因数过低",
        "high_temperature": "高温",
        "relay_failure": "继电器故障",
        "control_gear_comm_failure": "控制设备通信故障",
        "cycling_failure": "循环故障",
        "supply_loss": "停电",
        "lamp_unexpected_on": "灯具意外亮起",
        "supply_voltage_too_high": "供电电压过高",
        "supply_voltage_too_low": "供电电压过低",
        "group_control_fault": "分组控制故障",
        "link_control_fault": "链路控制故障",
        "lux_communication_fault": "光照通信故障",
        "high_load_power": "高负载功率",
        "meter_fault": "电表故障",
        "lux_module_fault": "光照模块故障",
    }

    # 分组信息映射：分组号 → businessGroupIdPath 前缀（完整路径）
    # 实际数据只有分组9和10，路径格式为 0000/0001/0009 和 0000/0001/00010
    GROUP_PATH_MAP = {
        "1": "0000/0001/0001",
        "2": "0000/0002/0002",
        "3": "0000/0003/0003",
        "4": "0000/0004/0004",
        "5": "0000/0005/0005",
        "6": "0000/0006/0006",
        "7": "0000/0007/0007",
        "8": "0000/0008/0008",
        "9": "0000/0001/0009",
        "10": "0000/0001/00010",
        "分组1": "0000/0001/0001",
        "分组2": "0000/0002/0002",
        "分组3": "0000/0003/0003",
        "分组4": "0000/0004/0004",
        "分组5": "0000/0005/0005",
        "分组6": "0000/0006/0006",
        "分组7": "0000/0007/0007",
        "分组8": "0000/0008/0008",
        "分组9": "0000/0001/0009",
        "分组10": "0000/0001/00010",
    }

    async def execute(
        self,
        llm: Any,
        query: str,
        context: ConversationContext
    ) -> dict[str, Any]:
        """执行故障查询"""
        reasoning_chain = []

        reasoning_chain.extend(await self._build_reasoning_chain([
            ("解析查询意图", f"用户查询: {query}", "意图识别为故障查询")
        ]))

        # 解析查询条件
        filters = self._parse_fault_query(query)

        reasoning_chain.extend(await self._build_reasoning_chain([
            ("提取查询条件",
             f"分组: {filters.get('group')}, 时间: {filters.get('date_range')}, 故障类型: {filters.get('fault_type')}",
             "条件提取完成")
        ]))

        # 生成 SQL 查询
        sql, params = self._build_sql_query(filters)

        reasoning_chain.extend(await self._build_reasoning_chain([
            ("构建 SQL", f"生成查询语句", "SQL 构建完成")
        ]))

        # 执行查询
        results = await self._execute_fault_query(sql, params)

        reasoning_chain.extend(await self._build_reasoning_chain([
            ("执行查询", f"找到 {len(results)} 条故障记录", "查询完成")
        ]))

        # 当查询为空且有分组筛选时，去掉分组条件重新查询，找出哪些分组有数据
        if not results and filters.get("group"):
            alt_filters = {k: v for k, v in filters.items() if k not in ("group", "group_path")}
            if alt_filters:
                alt_sql, alt_params = self._build_sql_query(alt_filters)
                alt_results = await self._execute_fault_query(alt_sql, alt_params)
            else:
                alt_sql = """
                    SELECT DISTINCT "businessGroupId", "businessGroupName", "businessGroupIdPath"
                    FROM devices_fault
                    ORDER BY "businessGroupId"
                """
                alt_results = await self._execute_fault_query(alt_sql, [])
            # 用 LLM 生成回答
            answer = await self._generate_no_results_llm_answer(query, filters, alt_results, llm)
        else:
            # 生成回答
            answer = self._generate_answer(query, results, filters)

        # 生成表格数据
        data = self._generate_table_data(results)

        return {
            "answer": answer,
            "reasoning_chain": reasoning_chain,
            "confidence": 0.95,
            "map_data": None,
            "data": data,
            "sources": []
        }

    def _parse_fault_query(self, query: str) -> dict:
        """解析故障查询条件"""
        filters = {}

        # 提取分组信息
        group_match = re.search(r'分组(\d+)', query)
        if group_match:
            group_num = group_match.group(1)
            filters["group"] = group_num
            # 直接从 GROUP_PATH_MAP 获取完整路径
            filters["group_path"] = self.GROUP_PATH_MAP.get(f"分组{group_num}", f"0000/0001/{group_num.zfill(4)}")

        # 也支持 "组1" 格式
        if "group" not in filters:
            group_match = re.search(r'组(\d+)', query)
            if group_match:
                group_num = group_match.group(1)
                filters["group"] = group_num
                filters["group_path"] = self.GROUP_PATH_MAP.get(group_num, f"0000/0001/{group_num.zfill(4)}")

        # 提取故障类型
        fault_type = None
        for chinese_name, db_value in self.FAULT_TYPE_MAP.items():
            if chinese_name in query:
                fault_type = db_value
                filters["fault_type_cn"] = chinese_name
                break
        if fault_type:
            filters["fault_type"] = fault_type

        # 提取日期
        date_match = re.search(r'(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日', query)
        if date_match:
            year, month, day = date_match.groups()
            filters["date"] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            filters["start_date"] = filters["date"]
            filters["end_date"] = filters["date"]
        else:
            # 尝试 "2026年4月份" 或 "2026年4月" 格式（只有年月，没有日）
            date_match = re.search(r'(\d{4})年\s*(\d{1,2})月份?', query)
            if date_match:
                year, month = date_match.groups()
                filters["year"] = year
                filters["month"] = month
                filters["start_date"] = f"{year}-{month.zfill(2)}-01"
                # 月底
                month_int = int(month)
                if month_int in (1, 3, 5, 7, 8, 10, 12):
                    filters["end_date"] = f"{year}-{month.zfill(2)}-31"
                elif month_int in (4, 6, 9, 11):
                    filters["end_date"] = f"{year}-{month.zfill(2)}-30"
                else:
                    # 2月，根据年判断闰年
                    year_int = int(year)
                    if (year_int % 4 == 0 and year_int % 100 != 0) or (year_int % 400 == 0):
                        filters["end_date"] = f"{year}-{month.zfill(2)}-29"
                    else:
                        filters["end_date"] = f"{year}-{month.zfill(2)}-28"
            else:
                # 尝试 "2026-04-22" 格式
                date_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', query)
                if date_match:
                    filters["date"] = date_match.group(0)
                    filters["start_date"] = filters["date"]
                    filters["end_date"] = filters["date"]

        # 提取时间范围（如 "本月", "上周", "本周"）
        time_range = None
        if "本月" in query:
            now = datetime.now()
            time_range = "本月"
            filters["start_date"] = f"{now.year}-{now.month:02d}-01"
            filters["end_date"] = filters["date"] if "date" in filters else now.strftime("%Y-%m-%d")
        elif "上周" in query:
            time_range = "上周"
        elif "本周" in query:
            time_range = "本周"
        elif "昨日" in query or "昨天" in query:
            time_range = "昨天"
        elif "今日" in query or "今天" in query:
            time_range = "今天"

        if time_range:
            filters["time_range"] = time_range

        return filters

    def _build_sql_query(self, filters: dict) -> tuple[str, list]:
        """构建 SQL 查询（使用 positional parameters）"""
        conditions = []
        params = []

        # 故障类型条件
        if filters.get("fault_type"):
            conditions.append("fault = $1")
            params.append(filters["fault_type"])

        # 分组条件
        if filters.get("group_path"):
            param_idx = len(params) + 1
            group_path = filters["group_path"]
            # 使用完整路径匹配（不使用 LIKE 前缀匹配，因为路径是固定的）
            if group_path.startswith("%"):
                # 特殊格式（如 %00010%）直接使用
                conditions.append(f'"businessGroupIdPath" LIKE ${param_idx}')
                params.append(group_path)
            else:
                # 完整路径使用等号匹配
                conditions.append(f'"businessGroupIdPath" = ${param_idx}')
                params.append(group_path)

        # 日期条件 - 使用 TO_DATE 函数进行日期比较
        if filters.get("start_date") and filters.get("end_date"):
            param_idx = len(params) + 1
            conditions.append(f"start_date >= TO_DATE(${param_idx}, 'YYYY-MM-DD')")
            params.append(filters["start_date"])
            param_idx = len(params) + 1
            conditions.append(f"start_date < (TO_DATE(${param_idx}, 'YYYY-MM-DD') + interval '1 day')")
            params.append(filters["end_date"])
        elif filters.get("start_date"):
            param_idx = len(params) + 1
            conditions.append(f"start_date >= TO_DATE(${param_idx}, 'YYYY-MM-DD')")
            params.append(filters["start_date"])
        elif filters.get("end_date"):
            param_idx = len(params) + 1
            conditions.append(f"start_date < (TO_DATE(${param_idx}, 'YYYY-MM-DD') + interval '1 day')")
            params.append(filters["end_date"])

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        sql = f"""
            SELECT
                id,
                device_id,
                fault,
                "businessGroupId",
                "businessGroupName",
                "businessGroupIdPath",
                "businessGroupNamePath",
                start_date,
                end_date,
                created_at
            FROM devices_fault
            WHERE {where_clause}
            ORDER BY start_date DESC
            LIMIT 100
        """

        return sql, params

    async def _execute_fault_query(self, sql: str, params: list) -> list[dict]:
        """执行故障查询"""
        try:
            rows = await Database.fetch(sql, *params)
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error("fault_query_execution_failed", sql=sql, error=str(e))
            return []

    def _generate_answer(self, query: str, results: list, filters: dict) -> str:
        """生成自然语言回答"""
        if not results:
            return "未找到匹配的故障记录。"

        count = len(results)
        parts = []

        # 分组信息
        if filters.get("group"):
            parts.append(f"分组{filters['group']}")
        elif filters.get("group_path"):
            parts.append(f"分组路径 {filters['group_path']}")

        # 故障类型
        if filters.get("fault_type_cn"):
            parts.append(f"{filters['fault_type_cn']}")

        # 时间信息
        if filters.get("date"):
            parts.append(f"在 {filters['date']}")

        base = "".join(parts) if parts else "相关"

        # 避免 "电表故障故障记录" 这种重复
        if filters.get("fault_type_cn"):
            if base.endswith("故障"):
                lines = [f"找到 {count} 条{base}记录：\n"]
            else:
                lines = [f"找到 {count} 条{base}故障记录：\n"]
        else:
            lines = [f"找到 {count} 条{base}故障记录：\n"]

        # 显示前几条记录
        for r in results[:5]:
            device_id = r.get("device_id", "N/A")
            fault = r.get("fault", "未知")
            fault_cn = self.FAULT_TYPE_REVERSE_MAP.get(fault, fault)
            group_name = r.get("businessGroupName", "")
            start_date = r.get("start_date", "")
            if isinstance(start_date, datetime):
                start_date = start_date.strftime("%Y-%m-%d %H:%M")
            lines.append(f"- 设备{device_id}: {fault_cn} ({group_name}, {start_date})")

        if count > 5:
            lines.append(f"\n... 还有 {count - 5} 条记录")

        return "\n".join(lines)

    async def _generate_no_results_llm_answer(
        self,
        query: str,
        filters: dict,
        alt_results: list[dict],
        llm: Any
    ) -> str:
        """当无匹配结果时，使用 LLM 生成分析回答"""
        # 收集存在的分组信息
        groups = {}
        for r in alt_results:
            gid = r.get("businessGroupId", "")
            gname = r.get("businessGroupName", "")
            if gid:
                groups[gid] = gname or f"分组{gid}"
            # 也尝试从 businessGroupIdPath 提取
            path = r.get("businessGroupIdPath", "")
            if not gid and path:
                parts = path.split("/")
                gid = parts[-1]
                groups[gid] = f"分组{gid}"

        group_list = ", ".join(groups.values()) if groups else "未知"
        fault_type = filters.get("fault_type_cn", "相关")

        prompt = f"""用户查询: {query}
查询条件: {fault_type}
结果: 在指定分组({filters.get('group', '?')})未找到匹配记录

系统实际包含以下分组的数据: {group_list}

请用中文、自然语言回答用户，说明:
1. 用户查询的{fault_type}在分组{filters.get('group', '?')}没有记录
2. 该{fault_type}仅存在于以下分组: {group_list}
3. 建议用户查询这些分组

回答要简洁、友好。"""

        try:
            response = llm.invoke(prompt, system=False, temperature=0.3)
            # 清理 thinking 标签
            import re
            cleaned = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL).strip()
            return cleaned if cleaned else f"未在分组{filters.get('group', '')}找到{fault_type}记录。该{fault_type}仅存在于{group_list}。"
        except Exception as e:
            logger.warning("llm_no_results_answer_failed", error=str(e))
            return f"未在分组{filters.get('group', '')}找到{fault_type}记录。该{fault_type}仅存在于{group_list}。"

    def _generate_table_data(self, results: list) -> dict:
        """生成表格数据"""
        if not results:
            return {"headers": [], "rows": []}

        headers = ["ID", "设备ID", "故障类型", "分组ID", "分组名称", "分组路径", "开始时间", "结束时间"]

        rows = []
        for r in results[:100]:
            fault = r.get("fault", "")
            fault_cn = self.FAULT_TYPE_REVERSE_MAP.get(fault, fault)

            start_date = r.get("start_date", "")
            if isinstance(start_date, datetime):
                start_date = start_date.strftime("%Y-%m-%d %H:%M")

            end_date = r.get("end_date", "")
            if isinstance(end_date, datetime):
                end_date = end_date.strftime("%Y-%m-%d %H:%M")

            rows.append([
                r.get("id", ""),
                r.get("device_id", ""),
                fault_cn,
                r.get("businessGroupId", ""),
                r.get("businessGroupName", ""),
                r.get("businessGroupIdPath", ""),
                str(start_date),
                str(end_date),
            ])

        return {
            "headers": headers,
            "rows": rows,
            "total": len(results)
        }

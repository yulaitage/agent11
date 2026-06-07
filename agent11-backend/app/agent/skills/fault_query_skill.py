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

    # 缓存动态加载的分组信息（按聊天会话惰性加载）
    _group_info_cache: dict | None = None

    async def _ensure_group_info(self) -> dict:
        """从 groups_info 表动态加载分组层级关系"""
        if self._group_info_cache is not None:
            return self._group_info_cache

        cache = {
            "id_by_num": {},       # "分组1" → "0001", "1" → "0001"
            "name_by_id": {},      # "0001" → "分组1"
            "parent_ids": set(),   # {"0001", "0002"}（有子组的分组）
            "path_by_id": {},      # "0001" → "0000/0001"（用于 LIKE 前缀）
        }

        try:
            rows = await Database.fetch('SELECT * FROM groups_info ORDER BY "businessGroupId"')
            child_ids = set()

            for r in rows:
                gid = r["businessGroupId"]
                gname = r["businessGroupName"]
                path = r["businessGroupIdPath"]
                parent = r["parentGroupId"]

                cache["name_by_id"][gid] = gname
                cache["path_by_id"][gid] = path

                # 从分组名提取数字（如 "分组1" → "1"）
                import re
                m = re.search(r'(\d+)', gname)
                if m:
                    num = m.group(1)
                    cache["id_by_num"][f"分组{num}"] = gid
                    cache["id_by_num"][num] = gid

                # 记录有子组的分组
                if parent:
                    child_ids.add(gid)
                    cache["parent_ids"].add(parent)

            logger.info("group_info_loaded",
                        groups=len(rows),
                        parents=len(cache["parent_ids"]),
                        children=len(child_ids))

            self._group_info_cache = cache

        except Exception as e:
            logger.error("group_info_load_failed", error=str(e))
            # 缓存空数据，避免重复查询失败
            self._group_info_cache = cache

        return self._group_info_cache

    async def execute(
        self,
        llm: Any,
        query: str,
        context: ConversationContext
    ) -> dict[str, Any]:
        """执行故障查询"""
        reasoning_chain = []

        # 动态加载分组层级信息
        group_info = await self._ensure_group_info()

        reasoning_chain.extend(await self._build_reasoning_chain([
            ("解析查询意图", f"用户查询: {query}", "意图识别为故障查询")
        ]))

        # 解析查询条件（使用动态分组信息）
        filters = self._parse_fault_query(query, group_info)

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
        if not results and (filters.get("group") or filters.get("group_id")):
            alt_filters = {k: v for k, v in filters.items() if k not in ("group", "group_path", "group_id")}
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

    def _parse_fault_query(self, query: str, group_info: dict) -> dict:
        """解析故障查询条件"""
        filters = {}
        id_by_num = group_info.get("id_by_num", {})
        parent_ids = group_info.get("parent_ids", set())
        path_by_id = group_info.get("path_by_id", {})

        # 提取分组信息
        group_match = re.search(r'分组(\d+)', query)
        if group_match:
            group_num = group_match.group(1)
            filters["group"] = group_num
            group_id = id_by_num.get(f"分组{group_num}") or id_by_num.get(group_num)
            if group_id:
                if group_id in parent_ids:
                    # 父组：用 businessGroupIdPath LIKE 前缀匹配（包含子组）
                    path = path_by_id.get(group_id, f"0000/{group_id}")
                    filters["group_path"] = path
                else:
                    # 叶子组：用 businessGroupId 精确匹配
                    filters["group_id"] = group_id

        # 也支持 "组1" 格式
        if "group" not in filters:
            group_match = re.search(r'组(\d+)', query)
            if group_match:
                group_num = group_match.group(1)
                filters["group"] = group_num
                group_id = id_by_num.get(group_num)
                if group_id:
                    if group_id in parent_ids:
                        path = path_by_id.get(group_id, f"0000/{group_id}")
                        filters["group_path"] = path
                    else:
                        filters["group_id"] = group_id

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

        # 提取时间范围（如 "过去10小时", "本月", "上周"）
        time_range = None
        now = datetime.now()
        # 过去 X 小时/天/周/月
        past_match = re.search(r'过去\s*(\d+)\s*小[时時]', query)
        if past_match:
            hours = int(past_match.group(1))
            time_range = f"过去{hours}小时"
            from datetime import timedelta
            start = now - timedelta(hours=hours)
            filters["start_date"] = start.strftime("%Y-%m-%d %H:%M:%S")
            filters["end_date"] = now.strftime("%Y-%m-%d %H:%M:%S")
        elif "本月" in query:
            time_range = "本月"
            filters["start_date"] = f"{now.year}-{now.month:02d}-01"
            filters["end_date"] = now.strftime("%Y-%m-%d")
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
            # 父组：用 businessGroupIdPath LIKE 前缀匹配（包含子组）
            param_idx = len(params) + 1
            conditions.append(f'"businessGroupIdPath" LIKE ${param_idx}')
            params.append(filters["group_path"] + "%")
        elif filters.get("group_id"):
            # 叶子组：用 businessGroupId 精确匹配（避免路径格式不一致导致问题）
            param_idx = len(params) + 1
            conditions.append(f'"businessGroupId" = ${param_idx}')
            params.append(filters["group_id"])

        # 日期条件 - 支持 DATE 和 DATETIME 两种格式
        if filters.get("start_date") and filters.get("end_date"):
            sd = filters["start_date"]
            ed = filters["end_date"]
            # 如果包含时分秒，使用 TIMESTAMP 精确匹配
            if ":" in sd:
                conditions.append(f"start_date >= ${len(params) + 1}::timestamp")
                params.append(sd)
                conditions.append(f"start_date <= ${len(params) + 1}::timestamp")
                params.append(ed)
            else:
                conditions.append(f"start_date >= TO_DATE(${len(params) + 1}, 'YYYY-MM-DD')")
                params.append(sd)
                conditions.append(f"start_date < (TO_DATE(${len(params) + 1}, 'YYYY-MM-DD') + interval '1 day')")
                params.append(ed)
        elif filters.get("start_date"):
            sd = filters["start_date"]
            if ":" in sd:
                conditions.append(f"start_date >= ${len(params) + 1}::timestamp")
                params.append(sd)
            else:
                conditions.append(f"start_date >= TO_DATE(${len(params) + 1}, 'YYYY-MM-DD')")
                params.append(sd)
        elif filters.get("end_date"):
            ed = filters["end_date"]
            if ":" in ed:
                conditions.append(f"start_date <= ${len(params) + 1}::timestamp")
                params.append(ed)
            else:
                conditions.append(f"start_date < (TO_DATE(${len(params) + 1}, 'YYYY-MM-DD') + interval '1 day')")
                params.append(ed)

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
        """生成自然语言回答（自动匹配语言）"""
        is_en = not bool(re.search(r'[一-鿿]', query))

        if not results:
            return "No matching fault records found." if is_en else "未找到匹配的故障记录。"

        count = len(results)
        parts = []

        # 分组信息
        if filters.get("group"):
            label = "Group" if is_en else "分组"
            parts.append(f"{label}{filters['group']}")
        elif filters.get("group_path"):
            parts.append(f"Group path {filters['group_path']}")

        # 故障类型
        if filters.get("fault_type_cn"):
            parts.append(f"{filters['fault_type_cn']}")

        # 时间信息
        if filters.get("date"):
            parts.append(f"on {filters['date']}" if is_en else f"在 {filters['date']}")

        base = "".join(parts) if parts else ("related" if is_en else "相关")

        if filters.get("fault_type_cn") and base.endswith("故障"):
            lines = [f"Found {count} {base} records:\n" if is_en else f"找到 {count} 条{base}记录：\n"]
        else:
            suffix = " fault records" if is_en else "故障记录"
            lines = [f"Found {count} {base}{suffix}:\n" if is_en else f"找到 {count} 条{base}{suffix}：\n"]

        # 显示前几条记录
        for r in results[:5]:
            device_id = r.get("device_id", "N/A")
            fault = r.get("fault", "unknown")
            fault_cn = self.FAULT_TYPE_REVERSE_MAP.get(fault, fault)
            group_name = r.get("businessGroupName", "")
            start_date = r.get("start_date", "")
            if isinstance(start_date, datetime):
                start_date = start_date.strftime("%Y-%m-%d %H:%M")
            lines.append(f"- Device {device_id}: {fault_cn} ({group_name}, {start_date})" if is_en else f"- 设备{device_id}: {fault_cn} ({group_name}, {start_date})")

        if count > 5:
            remaining = count - 5
            lines.append(f"\n... {remaining} more records" if is_en else f"\n... 还有 {remaining} 条记录")

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

        # 自动匹配用户语言
        lang = "English" if not re.search(r'[一-鿿]', query) else "Chinese"
        prompt = f"""User query: {query}
Query conditions: {fault_type}
Result: No matching records found for the specified group ({filters.get('group', '?')})

Groups that actually have this data: {group_list}

Respond in {lang}. Explain:
1. No {fault_type} records were found for group {filters.get('group', '?')}
2. The {fault_type} only exists in these groups: {group_list}
3. Suggest the user query these groups

Be concise and friendly."""

        try:
            response = await llm.invoke(prompt, system=False, temperature=0.3)
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

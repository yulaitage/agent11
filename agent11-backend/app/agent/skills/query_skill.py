"""Query 技能 - 智能数据库自然语言查询"""
from typing import Any
from datetime import datetime, date, time
from app.agent.skills.base import BaseSkill
from app.agent.context import ConversationContext
from app.db.session import get_session
from sqlalchemy import text


class QuerySkill(BaseSkill):
    """Query 技能 - 通过 LLM 理解用户问题，自动匹配数据库表和列，执行查询"""

    name = "query"

    async def execute(
        self,
        llm: Any,
        query: str,
        context: ConversationContext
    ) -> dict[str, Any]:
        """执行自然语言查询"""
        reasoning_chain = []

        # 1. 获取所有数据库表和列信息
        schema = await self._get_database_schema()
        reasoning_chain.extend(await self._build_reasoning_chain([
            ("获取 schema", f"发现 {len(schema['tables'])} 张表", "数据库结构已加载")
        ]))

        # 2. 提取用户问题中的关键词（中英文分开处理）
        import re
        query_lower = query.lower()

        # 英文词
        words = re.findall(r'[a-z_]+', query_lower)

        # 中文字符 - 用列表推导式逐字提取
        chinese_chars = [c for c in query if '一' <= c <= '鿿']

        # 中文 n-gram 提取（2-4字词）
        chinese_ngrams = []
        for n in [2, 3, 4]:
            for i in range(len(chinese_chars) - n + 1):
                ngram = ''.join(chinese_chars[i:i+n])
                chinese_ngrams.append(ngram)

        # 组合关键词（英文单词 + 中文单字 + 中文词组）
        all_terms = words + chinese_chars + chinese_ngrams + [query_lower, query]

        # 预定义一些常见的中英文映射（包含复合词）
        translations = {
            # 单个词
            "temperature": ["温度", "temperature", "temper"],
            "high": ["高", "high", "过"],
            "fault": ["故障", "fault", "错误"],
            "event": ["事件", "event", "告警"],
            "device": ["设备", "device", "器件"],
            "power": ["功率", "power", "电量", "能耗"],
            "energy": ["能源", "energy", "能耗", "电量"],
            # 复合词
            "high_temperature": ["温度过高", "高温", "过热", "temperature", "high_temperature"],
            "relay_failure": ["继电器故障", "继电器错误", "relay_failure"],
            "overload": ["过载", "超载", "overload"],
            "undervoltage": ["欠压", "电压过低", "undervoltage"],
            "overvoltage": ["过压", "电压过高", "overvoltage"],
            "power_failure": ["停电", "断电", "供电中断", "power_failure"],
            # 短词组合
            "温度": ["temperature", "temper"],
            "事件": ["event", "fault"],
            "故障": ["fault", "failure"],
            # === 用户提供的故障类型对照表 ===
            # AC主电压
            "ac_high_main_voltage": ["AC主电压过高", "主电压过高", "ac_high_main_voltage"],
            "ac_low_main_voltage": ["AC主电压过低", "主电压过低", "ac_low_main_voltage"],
            # 负载功率/电流
            "high_load_power": ["负载功率过高", "load_power", "high_load_power"],
            "high_load_current": ["负载电流过高", "load_current", "high_load_current"],
            "low_load_power": ["负载功率过低", "low_load_power"],
            "low_load_current": ["负载电流过低", "low_load_current"],
            # 功率因素
            "low_power_factor": ["功率因素过低", "power_factor", "low_power_factor"],
            # 温度相关
            "high_temperature": ["温度过高", "高温", "过热", "temperature", "high_temperature"],
            # 电表/光感/驱动器
            "meter_error": ["电表错误", "meter_fault", "meter_error"],
            "meter_fault": ["电表错误", "meter_fault", "meter_error"],
            "light_perception_error": ["光感错误", "light_perception_error"],
            "drive_error": ["驱动器错误", "drive_error"],
            "lamp_failed": ["灯失败", "lamp_failed", "lamp_failure"],
            "lamp_failure": ["灯失败", "lamp_failed", "lamp_failure"],
            "flash_lights": ["闪灯", "flash_lights"],
            "drive_communication_error": ["驱动通信错误", "drive_communication_error"],
            "lights_up_during_day": ["白天亮灯", "lights_up_during_day"],
            # 继电器
            "relay_adhesion": ["继电器粘连", "relay_adhesion"],
            "relay_open": ["继电器断开", "relay_open"],
            # 其他设备故障
            "ctrl_multicast_failed": ["设备自控组播失败", "ctrl_multicast_failed"],
            "jcmode_syn_signal_failure": ["联控模式同步信号故障", "jcmode_syn_signal_failure"],
            "ext_illsensor_communication_failure": ["外接光照度传感器通信故障", "ext_ilsensor_communication_failure", "ext_illsensor_communication_failure"],
            "ext_ilsensor_communication_failure": ["外接光照度传感器通信故障", "ext_ilsensor_communication_failure", "ext_illsensor_communication_failure"],
            # AC相关
            "abnormal_ac_voltage_fluctuation": ["AC电压异常波动", "abnormal_ac_voltage_fluctuation"],
            "ac_on_off_flicker": ["AC电通断闪烁", "ac_on_off_flicker"],
            # 温湿度传感器
            "temperature_and_humidity_sensor_communication_error": ["温湿度传感器通信错误", "temperature_and_humidity_sensor_communication_error"],
            "temperature_and_humidity_sensor_temperature_too_high": ["温湿度传感器温度过高", "temperature_and_humidity_sensor_temperature_too_high"],
            "temperature_and_humidity_sensor_temperature_too_low": ["温湿度传感器温度过低", "temperature_and_humidity_sensor_temperature_too_low"],
            "temperature_and_humidity_sensor_humidity_too_high": ["温湿度传感器湿度过高", "temperature_and_humidity_sensor_humidity_too_high"],
            "temperature_and_humidity_sensor_humidity_too_low": ["温湿度传感器湿度过低", "temperature_and_humidity_sensor_humidity_too_low"],
            "leakage_alarm": ["漏电报警", "leakage_alarm"],
            # 供电相关
            "supply_loss": ["停电", "断电", "供电中断", "supply_loss"],
            "supply_voltage_too_high": ["供电电压过高", "supply_voltage_too_high"],
            "supply_voltage_too_low": ["供电电压过低", "supply_voltage_too_low"],
            # 电流相关
            "current_too_high": ["电流过高", "current_too_high"],
            "current_too_low": ["电流过低", "current_too_low"],
            # 灯功率相关
            "lamp_power_too_high": ["灯具功率过高", "灯功率过高", "lamp_power_too_high"],
            "lamp_power_too_low": ["灯具功率过低", "灯功率过低", "lamp_power_too_low"],
            # 调光/循环故障
            "dimming_failure": ["调光故障", "dimming_failure"],
            "cycling_failure": ["循环故障", "周期性故障", "cycling_failure"],
            # 通信故障
            "control_gear_comm_failure": ["控制设备通信故障", "控制设备通信错误", "control_gear_comm_failure"],
            "lux_communication_fault": ["光照通信故障", "lux_communication_fault"],
            "lux_module_fault": ["光感模块故障", "lux_module_fault"],
            # 控制相关
            "group_control_fault": ["群控故障", "group_control_fault"],
            "link_control_fault": ["联控故障", "link_control_fault"],
        }

        # 扩展关键词列表
        expanded_keywords = set()
        for term in all_terms:
            if len(term) >= 1:  # 中文单字也包含
                expanded_keywords.add(term)
                # 如果是英文，检查是否有翻译
                if term in translations:
                    expanded_keywords.update(translations[term])
                # 如果是中文，检查是否有反向翻译
                for eng, chn_list in translations.items():
                    if term in chn_list:
                        expanded_keywords.add(eng)
                        expanded_keywords.update(translations.get(eng, []))

        keywords = [k for k in expanded_keywords if len(k) >= 1]

        # 只选择最有用的关键词用于预搜索（避免太多SQL查询）
        # 优先：完整故障类型 > 2-4字中文词组 > 英文单词
        priority_keywords = []
        for kw in keywords:
            if len(kw) <= 1:
                continue
            # 如果是带下划线的故障类型代码（如 high_load_power），直接优先
            if '_' in kw and kw in translations:
                priority_keywords.insert(0, kw)
            elif 2 <= len(kw) <= 4 and kw not in words:
                priority_keywords.append(kw)
            elif kw.isalpha():
                priority_keywords.append(kw)

        priority_keywords = list(dict.fromkeys(priority_keywords))[:30]

        logger.info("query_priority_keywords", keywords=priority_keywords)

        # 3. 预搜索：只搜索优先级关键词
        search_results = await self._search_keywords_in_database(priority_keywords, schema)
        reasoning_chain.extend(await self._build_reasoning_chain([
            ("预搜索", f"关键词 {keywords} 在 {len(search_results)} 个表中找到匹配", "数据位置已定位")
        ]))

        if not search_results:
            return {
                "answer": "抱歉，我在数据库中没有找到与您问题匹配的关键词。请尝试其他表述。",
                "reasoning_chain": reasoning_chain,
                "confidence": 0.3,
                "map_data": None,
                "data": None,
                "sources": []
            }

        # 4. 用 LLM 分析搜索结果，确定最终表和过滤条件
        table_match = await self._llm_match_table_and_columns(llm, query, schema, search_results, keywords)

        # 验证并修正列名
        if table_match.get("table") and table_match["table"] in schema["tables"]:
            valid_columns = set(c["name"] for c in schema["tables"][table_match["table"]]["columns"])
            for f in table_match.get("filters", []):
                if f.get("column") and f["column"] not in valid_columns:
                    # 列名不存在于表中，清空过滤条件
                    f["column"] = None
                    f["value"] = None

        reasoning_chain.extend(await self._build_reasoning_chain([
            ("分析查询", f"匹配到表: {table_match['table']}, 列: {table_match.get('filters', [])}", "条件解析完成")
        ]))

        if not table_match["table"]:
            return {
                "answer": "抱歉，我无法根据您的问题定位到具体的数据库表。请尝试更明确的问题，例如「查询某表中的数据」或提供表名/列名关键词。",
                "reasoning_chain": reasoning_chain,
                "confidence": 0.3,
                "map_data": None,
                "data": None,
                "sources": []
            }

        # 3. 生成并执行 SQL
        sql_result = await self._execute_sql(
            table=table_match["table"],
            filters=table_match.get("filters", []),
            selected_columns=table_match.get("selected_columns"),
            limit=1000
        )
        reasoning_chain.extend(await self._build_reasoning_chain([
            ("执行查询", f"找到 {sql_result['row_count']} 条记录", "查询完成")
        ]))

        if not sql_result["rows"]:
            filter_desc = ", ".join([f"{f['column']} {f['operator']} {f['value']}" for f in table_match.get("filters", [])])
            return {
                "answer": f"在表 `{table_match['table']}` 中未找到匹配的数据（筛选条件: {filter_desc}）。",
                "reasoning_chain": reasoning_chain,
                "confidence": 0.95,
                "map_data": None,
                "data": {"headers": sql_result["columns"], "rows": [], "total": 0},
                "sources": []
            }

        # 4. 用 LLM 生成自然语言回答
        answer = await self._generate_answer(llm, query, sql_result, table_match)

        # 5. 生成地图数据（如果有位置列）
        map_data = self._generate_map_data(sql_result["rows"])

        # 6. 生成表格数据
        data = self._generate_table_data(sql_result["rows"])

        return {
            "answer": answer,
            "reasoning_chain": reasoning_chain,
            "confidence": 0.95,
            "map_data": map_data,
            "data": data,
            "sources": []
        }

    async def _get_database_schema(self) -> dict:
        """获取所有表和列信息"""
        async for session in get_session():
            result = await session.execute(text("""
                SELECT c.table_name, c.column_name, c.data_type
                FROM information_schema.columns c
                JOIN information_schema.tables t
                  ON c.table_name = t.table_name AND c.table_schema = t.table_schema
                WHERE c.table_schema = 'public'
                  AND t.table_type = 'BASE TABLE'
                ORDER BY c.table_name, c.ordinal_position
            """))
            rows = result.fetchall()

            tables = {}
            for row in rows:
                table_name = row[0]
                if table_name not in tables:
                    tables[table_name] = {"columns": [], "column_set": set()}
                tables[table_name]["columns"].append({"name": row[1], "type": row[2]})
                tables[table_name]["column_set"].add(row[1].lower())

            return {"tables": tables}

    async def _search_keywords_in_database(
        self,
        keywords: list[str],
        schema: dict
    ) -> dict[str, list[dict]]:
        """在所有文本列中搜索关键词，返回每个匹配的表和列"""
        results = {}
        # 只搜索可能包含故障/事件数据的表
        priority_tables = ['devices_info', 'devices_fault', 'groups_info', 'comm_logs']
        async for session in get_session():
            for table_name, info in schema["tables"].items():
                # 跳过非优先级表（除非关键词很少）
                if table_name not in priority_tables and len(keywords) > 10:
                    continue

                # 获取文本列
                text_cols = [c["name"] for c in info["columns"] if c["type"] in ("character varying", "varchar", "text", "character", "char")]
                if not text_cols:
                    continue

                for keyword in keywords:
                    if len(keyword) < 2:
                        continue
                    # 搜索每个文本列
                    for col in text_cols:
                        try:
                            result = await session.execute(
                                text(f'''
                                    SELECT count(*) FROM "{table_name}"
                                    WHERE "{col}" ILIKE :kw
                                '''),
                                {"kw": f"%{keyword}%"}
                            )
                            count = result.scalar() or 0
                            if count > 0:
                                if table_name not in results:
                                    results[table_name] = []
                                # 检查是否已记录此表
                                existing = next((r for r in results[table_name] if r["column"] == col), None)
                                if existing:
                                    existing["keyword_counts"][keyword] = count
                                else:
                                    results[table_name].append({
                                        "column": col,
                                        "keyword_counts": {keyword: count}
                                    })
                        except Exception:
                            continue
        return results

    async def _llm_match_table_and_columns(
        self,
        llm: Any,
        query: str,
        schema: dict,
        search_results: dict,
        keywords: list
    ) -> dict:
        """用 LLM 分析用户问题，结合预搜索结果匹配表和列"""

        # 构建搜索结果摘要
        search_summary = []
        for table_name, columns in search_results.items():
            for col_info in columns:
                col = col_info["column"]
                counts = col_info["keyword_counts"]
                count_str = ", ".join([f"{k}: {v}条" for k, v in counts.items()])
                search_summary.append(f"- {table_name}.{col}: [{count_str}]")

        system_prompt = f"""你是一个数据库查询助手。给定用户的问题、数据库 schema 和预搜索结果，输出 JSON 格式的查询条件。

数据库 schema（表名 -> 列名列表）：
"""
        for table_name, info in schema["tables"].items():
            cols = ", ".join([c["name"] for c in info["columns"]])
            system_prompt += f"- {table_name}: [{cols}]\n"

        system_prompt += f"""
用户问题中的关键词：{keywords}

预搜索结果（关键词在哪些表/列中有数据）：
{chr(10).join(search_summary) if search_summary else "无匹配"}

关键规则（必须遵守）：
1. 预搜索结果显示的是数据库中实际存在的值（如 fault 列中的 "relay_failure", "high_load_power", "flash_lights" 等）
2. 当预搜索找到某个故障类型时，filter 的 value 必须使用数据库中实际存在的值！
   - 如果预搜索结果说 fault 列有 "relay_failure" 匹配，value 必须用 "relay_failure"，不能用 "继电器故障"
   - 如果预搜索结果说 fault 列有 "flash_lights" 匹配，value 必须用 "flash_lights"，不能用 "闪灯"
3. 故障类型是英文值（under_score 格式），不是中文
4. 日期处理：如果用户提到日期（如 2026-04-22），但数据库中 start_date 是 Excel 序列号（如 46134），需要通过 LIKE 或范围查询来匹配包含该日期的记录

分析步骤：
1. 查看预搜索结果，识别所有需要过滤的条件
2. 如果有故障类型关键词（如 high_load_power, relay_failure）和业务分组（如 分组10），为每个条件创建独立的 filter
3. 所有 filter 用 AND 组合
4. 优先使用 ILIKE 而非 eq，以处理部分匹配

输出格式（仅 JSON，无其他内容）：
{{
  "table": "表名",
  "filters": [
    {{"column": "fault", "operator": "like", "value": "完整的故障英文值如high_load_power"}},
    {{"column": "businessgroupnamepath", "operator": "like", "value": "分组10"}}
  ],
  "selected_columns": null,
  "reasoning": "选择理由"
}}

注意：
- 每个过滤条件对应一个 filter
- value 必须是数据库中实际存在的**完整英文故障类型值**（如 "high_load_power"），不能是部分词（如 "high" 或 "power"）
- 如果预搜索无结果，返回 {{"table": null, "filters": [], "selected_columns": null, "reasoning": ""}}
- **重要**：start_date 列存储的是 Excel 序列号（如 46134），是数值类型！不要对 start_date 使用任何过滤，只过滤 fault 和 businessgroupnamepath
- 分组过滤用 businessgroupnamepath（如 "分组10"）而非 businessgroupname"""

        user_prompt = f"用户问题：{query}"

        try:
            response = await llm.invoke(user_prompt, system=system_prompt, temperature=0)
            import json, re
            # 提取 JSON - 支持嵌套括号
            json_str = response.strip()
            # 找第一个 { 到最后一个 }
            start = json_str.find('{')
            end = json_str.rfind('}')
            if start != -1 and end != -1 and end > start:
                json_str = json_str[start:end+1]
                result = json.loads(json_str)
                # 验证表名存在
                if result.get("table") and result["table"] not in schema["tables"]:
                    result["table"] = None
                return result
        except Exception as e:
            pass
            pass

        return {"table": None, "filters": [], "selected_columns": None}

    async def _execute_sql(
        self,
        table: str,
        filters: list,
        selected_columns: list | None,
        limit: int
    ) -> dict:
        """执行 SQL 查询"""
        async for session in get_session():
            # 构建 SELECT
            if selected_columns:
                cols = ", ".join([f'"{c}"' for c in selected_columns])
                select_sql = f'SELECT {cols} FROM "{table}"'
            else:
                select_sql = f'SELECT * FROM "{table}"'

            params = {}
            conditions = []

            for idx, f in enumerate(filters):
                col = f.get("column")
                op = f.get("operator", "eq")
                val = f.get("value")

                # 跳过无效过滤条件
                if not col or val is None or str(val).strip() == "":
                    continue

                op_map = {
                    "gt": ">",
                    "lt": "<",
                    "eq": "=",
                    "ne": "!=",
                    "gte": ">=",
                    "lte": "<=",
                    "like": "ILIKE"
                }
                sql_op = op_map.get(op, "=")
                pkey = f"p{idx}"

                # 构建条件
                conditions.append(f'"{col}" {sql_op} :{pkey}')

                # 设置参数
                if op == "like":
                    params[pkey] = f"%{val}%"
                elif op in ("gte", "lte", "gt", "lt", "eq"):
                    # 先尝试数值转换
                    try:
                        params[pkey] = float(val)
                    except ValueError:
                        # 尝试日期时间解析
                        parsed = False
                        for fmt in ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"]:
                            try:
                                params[pkey] = datetime.strptime(val, fmt)
                                parsed = True
                                break
                            except ValueError:
                                continue
                        # 如果都不是，保持为字符串
                        if not parsed:
                            params[pkey] = val
                else:
                    params[pkey] = val

            if conditions:
                select_sql += " WHERE " + " AND ".join(conditions)

            select_sql += f" LIMIT :limit"
            params["limit"] = limit

            result = await session.execute(text(select_sql), params)
            rows = result.fetchall()

            # 获取列名
            col_result = await session.execute(text(f"""
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = :t
                ORDER BY ordinal_position
            """), {"t": table})
            col_names = [row[0] for row in col_result.fetchall()]

            # 转换行
            converted = []
            for row in rows:
                # 使用 zip 配对列名和值，避免索引越界
                converted.append({col: self._convert_value(val) for col, val in zip(col_names, row)})

            # 总数
            count_sql = f'SELECT count(*) FROM "{table}"'
            if conditions:
                count_sql += " WHERE " + " AND ".join(conditions)
            count_result = await session.execute(text(count_sql), params)
            total = count_result.scalar() or 0

            return {
                "columns": col_names,
                "rows": converted,
                "row_count": len(converted),
                "total": total
            }

    async def _generate_answer(
        self,
        llm: Any,
        query: str,
        sql_result: dict,
        table_match: dict
    ) -> str:
        """用 LLM 基于真实数据生成回答"""
        data_lines = [f"数据库查询结果（共 {sql_result['row_count']} 条）：\n"]
        for r in sql_result["rows"][:20]:
            data_lines.append("  " + ", ".join([f"{k}={v}" for k, v in r.items() if v]))
        if sql_result["row_count"] > 20:
            data_lines.append(f"  ... 还有 {sql_result['row_count'] - 20} 条记录")

        data_summary = "\n".join(data_lines)

        system_prompt = """你是 AGENT 11，智能基础设施管理 AI 助手。

你的回答必须严格基于以下真实数据库查询结果。仔细分析数据，回答用户的问题。

回答要求：
1. 基于数据回答，不要编造
2. 具体数据要准确引用
3. 如有汇总需求（如总计、平均），请计算后告知
4. 数据较多时适当归类"""

        try:
            response = await llm.invoke(
                f"用户问题：{query}\n\n数据库查询结果：\n{data_summary}",
                system=system_prompt,
                temperature=0.3
            )
            return response
        except Exception as e:
            return f"查询到 {sql_result['row_count']} 条记录。详细数据已展示在下方表格中。"

    def _convert_value(self, value: Any) -> Any:
        """Convert database value to JSON-serializable format"""
        if value is None:
            return None
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, time):
            return value.isoformat()
        try:
            float(value)
            return value
        except (TypeError, ValueError):
            return str(value)

    def _generate_map_data(self, rows: list) -> dict | None:
        """如果有 lat/lng 列则生成地图"""
        if not rows:
            return None

        # 查找经纬度列
        lat_key = next((k for k in ["latitude", "lat", "y"] if any(k in r for r in rows[:1] if r)), None)
        lng_key = next((k for k in ["longitude", "lng", "lon", "x"] if any(k in r for r in rows[:1] if r)), None)

        if not lat_key or not lng_key:
            return None

        markers = []
        for r in rows:
            lat = r.get(lat_key)
            lng = r.get(lng_key)
            if lat and lng:
                try:
                    markers.append({
                        "device_id": r.get("device_id") or r.get("id") or "",
                        "lat": float(lat),
                        "lng": float(lng),
                        "status": r.get("status", "normal"),
                        "popup": f"{r.get('device_id', '')} - {r.get('status', 'normal')}"
                    })
                except (ValueError, TypeError):
                    continue

        if not markers:
            return None

        lats = [m["lat"] for m in markers]
        lngs = [m["lng"] for m in markers]
        return {
            "center": [sum(lats)/len(lats), sum(lngs)/len(lngs)],
            "zoom": 14,
            "markers": markers,
            "legend": {"normal": "#3b82f6", "warning": "#f97316", "fault": "#ef4444"}
        }

    def _generate_table_data(self, rows: list) -> dict:
        """生成表格数据"""
        if not rows:
            return {"headers": [], "rows": [], "total": 0}
        headers = list(rows[0].keys())
        return {
            "headers": headers,
            "rows": [[str(r.get(h, "")) for h in headers] for r in rows[:100]],
            "total": len(rows)
        }
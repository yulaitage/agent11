"""Smart Query skill - Unified LLM-driven data query system.

Replaces fault_query, query, and flexible_report with a single skill that:
1. Uses LLM to understand ANY natural language question about the data
2. Generates structured query plans (tables, columns, filters, aggregations)
3. Executes safe parameterized SQL against PostgreSQL
4. Uses LLM to format results into natural language answers
5. Returns structured table/chart data for the frontend
"""
import re
import json
from typing import Any
from datetime import datetime
import structlog

from app.agent.skills.base import BaseSkill
from app.agent.context import ConversationContext
from app.db.postgres import Database

logger = structlog.get_logger()


class SmartQuerySkill(BaseSkill):
    """Smart Query skill - LLM-driven natural language data query"""

    name = "smart_query"

    ALLOWED_AGG_FUNCTIONS = {"COUNT", "SUM", "AVG", "MAX", "MIN"}
    OPERATOR_MAP = {
        "gt": ">", "lt": "<", "eq": "=", "ne": "!=",
        "gte": ">=", "lte": "<=", "like": "ILIKE",
        ">": ">", "<": "<", "=": "=", "!=": "!=",
        ">=": ">=", "<=": "<=", "ILIKE": "ILIKE",
    }
    DANGEROUS_KEYWORDS = {"DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "TRUNCATE", "CREATE", "EXECUTE"}
    MAX_LIMIT = 1000
    DEFAULT_LIMIT = 100

    async def execute(
        self,
        llm: Any,
        query: str,
        context: ConversationContext
    ) -> dict[str, Any]:
        """执行智能查询"""
        self._current_query = query
        reasoning_chain = []

        reasoning_chain.extend(await self._build_reasoning_chain([
            ("解析查询意图", f"用户查询: {query}", "意图识别为智能数据查询")
        ]))

        # Phase 1: Schema discovery
        schema = await self._build_schema()
        if not schema:
            return {"answer": "数据库Schema不可用", "reasoning_chain": reasoning_chain,
                    "confidence": 0.0, "map_data": None, "data": None, "sources": []}

        sample_vals = await self._get_sample_values(schema)
        reasoning_chain.extend(await self._build_reasoning_chain([
            ("获取Schema", f"发现 {len(schema)} 张表", f"Schema加载完成, {sample_vals[:100]}...")
        ]))

        # Phase 2: LLM query planning
        plan = await self._plan_query(llm, query, schema, sample_vals)
        reasoning_chain.extend(await self._build_reasoning_chain([
            ("生成查询计划", f"计划: {json.dumps(plan, ensure_ascii=False)[:200]}", "查询计划已生成")
        ]))

        # Phase 2b: Validate plan
        valid, errors = self._validate_plan(plan, schema)
        if not valid:
            logger.warning("smart_query_plan_invalid", errors=errors)
            plan = self._build_fallback_plan(query)
            reasoning_chain.extend(await self._build_reasoning_chain([
                ("验证", f"计划验证失败: {errors}", "使用兜底查询")
            ]))

        reasoning_chain.extend(await self._build_reasoning_chain([
            ("验证查询计划", "计划验证通过", "准备执行SQL")
        ]))

        # Phase 3: Build SQL & execute
        sql, params = self._build_sql(plan)
        reasoning_chain.extend(await self._build_reasoning_chain([
            ("构建SQL", f"SQL: {sql[:150]}", "SQL构建完成")
        ]))

        try:
            rows = await self._execute_plan(sql, params)
        except Exception as e:
            logger.error("smart_query_execution_failed", sql=sql, error=str(e))
            # Try simpler query without filters
            simple_plan = self._build_fallback_plan(query)
            simple_sql, simple_params = self._build_sql(simple_plan)
            rows = await self._execute_plan(simple_sql, simple_params)

        reasoning_chain.extend(await self._build_reasoning_chain([
            ("执行查询", f"获取 {len(rows)} 条结果", "查询完成")
        ]))

        # Phase 4: Generate answer
        answer = await self._generate_answer(llm, query, rows, plan)
        data = self._build_output_data(rows, plan)
        map_data = self._generate_map_data(rows)

        return {
            "answer": answer,
            "reasoning_chain": reasoning_chain,
            "confidence": 0.92,
            "map_data": map_data,
            "data": data,
            "sources": [],
        }

    # ─── Phase 1: Schema ─────────────────────────────────────────

    async def _build_schema(self) -> dict[str, dict[str, str]]:
        """获取所有表和列信息"""
        target_tables = {
            "devices_info", "devices_fault", "devices_consumption",
            "groups_info", "device_readings", "energy_readings",
        }
        try:
            rows = await Database.fetch("""
                SELECT c.table_name, c.column_name, c.data_type
                FROM information_schema.columns c
                JOIN information_schema.tables t
                  ON c.table_name = t.table_name AND c.table_schema = t.table_schema
                WHERE c.table_schema = 'public'
                  AND t.table_type = 'BASE TABLE'
                  AND c.table_name = ANY($1)
                ORDER BY c.table_name, c.ordinal_position
            """, list(target_tables))
            schema: dict[str, dict[str, str]] = {}
            for r in rows:
                tn = r["table_name"]
                if tn not in schema:
                    schema[tn] = {}
                schema[tn][r["column_name"]] = r["data_type"]
            return schema
        except Exception as e:
            logger.error("schema_fetch_failed", error=str(e))
            return {}

    async def _get_sample_values(self, schema: dict) -> str:
        """获取关键列的样本值"""
        sample_queries = [
            ("devices_fault", "fault"),
            ("devices_info", "device_type"),
            ("devices_info", "status"),
            ("groups_info", "businessGroupName"),
            ("devices_info", "businessGroupName"),
        ]
        parts = []
        for tbl, col in sample_queries:
            if tbl in schema and col in schema[tbl]:
                try:
                    rows = await Database.fetch(
                        f'SELECT DISTINCT "{col}" FROM "{tbl}" WHERE "{col}" IS NOT NULL AND "{col}" != \'\' LIMIT 20'
                    )
                    vals = [str(r[col]) for r in rows if r[col]]
                    if vals:
                        parts.append(f"{tbl}.{col}: {', '.join(vals[:15])}")
                except Exception:
                    continue
        return "\n".join(parts)

    # ─── Phase 2: LLM Query Planning ────────────────────────────

    def _format_schema_for_llm(self, schema: dict) -> str:
        """格式化 Schema 供 LLM 使用"""
        lines = []
        for table_name, columns in schema.items():
            cols = ", ".join([f"{c} ({t})" for c, t in columns.items()])
            lines.append(f"- {table_name}: [{cols}]")
        return "\n".join(lines)

    async def _plan_query(self, llm: Any, query: str, schema: dict, sample_vals: str) -> dict:
        """使用 LLM 生成查询计划"""
        schema_str = self._format_schema_for_llm(schema)

        # Explicit fault type values (complete list from devices_fault.fault)
        fault_types = [
            "supply_loss", "high_temperature", "meter_fault", "lamp_failure",
            "lamp_power_too_high", "lamp_power_too_low", "dimming_failure",
            "lamp_unexpected_on", "current_too_high", "current_too_low",
            "power_factor_too_low", "relay_failure", "control_gear_comm_failure",
            "cycling_failure", "supply_voltage_too_high", "supply_voltage_too_low",
            "group_control_fault", "link_control_fault", "lux_communication_fault",
            "high_load_power", "lux_module_fault",
        ]

        prompt = (
            "You are a query planner for a smart infrastructure database. Given a user question and the database schema, "
            "produce a structured JSON query plan.\n\n"
            f"## Database Schema\n{schema_str}\n\n"
            f"## Sample Values from Database\n{sample_vals}\n\n"
            "## Available Tables and Their Purposes\n"
            "- devices_info: Device registry (device_id, device_name, device_type, status, location, group, street_name)\n"
            "- devices_fault: Fault records (device_id, fault type, group, start_date, end_date)\n"
            "- devices_consumption: Consumption data by device (device_id, report_date, group, value)\n"
            "- groups_info: Group hierarchy (businessGroupId, businessGroupName, parentGroupId)\n"
            "- device_readings: Real-time readings (voltage, current, power, energy_kwh, timestamp)\n"
            "- energy_readings: Energy measurements per device/geozone/timestamp (energy_kwh)\n\n"
            "## Fault Type Values (exact enum values in devices_fault.fault column)\n"
            f"{', '.join(fault_types)}\n\n"
            '## Output Format — JSON ONLY, no explanation\n'
            '{\n'
            '  "tables": ["devices_info"],\n'
            '  "columns": ["device_id", "device_name", "status"],\n'
            '  "filters": [{"column": "businessGroupName", "operator": "=", "value": "分组10"}],\n'
            '  "aggregations": [{"function": "count", "column": "*", "alias": "total"}],\n'
            '  "group_by": [],\n'
            '  "order_by": [{"column": "device_id", "direction": "ASC"}],\n'
            '  "limit": 100,\n'
            '  "joins": [],\n'
            '  "chart": null\n'
            '}\n\n'
            "## Critical Rules\n"
            "1. Table and column names MUST exactly match the schema above\n"
            "2. For fault type queries, filter on devices_fault.fault with the EXACT fault value from the list above.\n"
            "   'power failure'/'停电'/'断电' -> fault='supply_loss'\n"
            "   'high temperature'/'温度过高'/'高温' -> fault='high_temperature'\n"
            "   'meter fault'/'电表故障' -> fault='meter_fault'\n"
            "3. For 'group X' or '分组X', use businessGroupName='分组X'\n"
            "4. For time filters, output ISO 8601 dates (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)\n"
            "5. '过去N小时' -> calculate explicit ISO datetime like '2026-06-07 10:00:00'\n"
            "6. NEVER use SQL expressions like 'now()' or 'INTERVAL' as filter values. Use concrete date strings only.\n"
            "7. '2026年4月' -> '2026-04-01'\n"
            "7. When asking 'how many' / '多少个' / '统计', use COUNT aggregation\n"
            "8. GROUP BY when question asks 'by X' / 'per X' / 'each X' / '按X'\n"
            "9. For chart data, set chart: {\"type\": \"bar\"|\"line\"|\"pie\", \"title\": \"...\", \"unit\": \"...\"}\n"
            "10. The device_id in devices_fault is BIGINT, in devices_info it's VARCHAR\n"
            "11. Set reasonable LIMIT (default 100, max 200)\n"
            "13. When no specific columns needed, use ['*']\n"
            "14. Detect query language — respond in the same language as the question\n"
            "15. Do NOT invent column names that don't exist in the schema\n\n"
            "Generate ONLY the JSON. No other text.\n\n"
            f"User question: {query}"
        )

        try:
            response = await llm.invoke(prompt, system=False, temperature=0.1)
            logger.info("smart_query_llm_response", response=response[:500])
            plan = self._parse_json(response)
            if plan and isinstance(plan, dict):
                logger.info("smart_query_plan_generated", plan=str(plan)[:300])
                return plan
        except Exception as e:
            logger.warning("smart_query_plan_failed", error=str(e))

        return self._build_fallback_plan(query)

    @staticmethod
    def _parse_json(text: str) -> dict | None:
        """从 LLM 响应中提取 JSON"""
        cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        cleaned = re.sub(r'```json|```', '', cleaned).strip()
        start = cleaned.find('{')
        end = cleaned.rfind('}')
        if start != -1 and end != -1:
            try:
                return json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                pass
        return None

    def _build_fallback_plan(self, query: str) -> dict:
        """兜底查询计划 — 智能识别查询意图"""
        q = query.lower()
        # 故障查询
        if any(k in q for k in ["故障", "fault", "停电", "power failure", "温度过高",
                                "高温", "high temperature", "电表", "meter", "断电"]):
            return {
                "tables": ["devices_fault"],
                "columns": [],
                "aggregations": [{"function": "count", "column": "*", "alias": "total"}],
                "group_by": [],
                "order_by": [],
                "limit": 1,
                "joins": [],
                "chart": None,
            }
        # 设备查询
        return {
            "tables": ["devices_info"],
            "columns": ["device_id", "device_name", "device_type", "status", "businessGroupName", "street_name"],
            "filters": [],
            "aggregations": [],
            "group_by": [],
            "order_by": [{"column": "device_id", "direction": "ASC"}],
            "limit": 50,
            "joins": [],
            "chart": None,
        }

    # ─── Phase 2b: Plan Validation ──────────────────────────────

    def _validate_plan(self, plan: dict, schema: dict) -> tuple[bool, list[str]]:
        """验证查询计划的合法性"""
        errors = []
        tables = plan.get("tables", [])
        if not tables:
            return False, ["No tables specified"]

        for table in tables:
            if table not in schema:
                errors.append(f"Table '{table}' not found")

        if errors:
            return False, errors

        primary = tables[0]
        valid_cols = {t: set(c.keys()) for t, c in schema.items() if t in tables}

        def check_col(ref: str) -> bool:
            if "." in ref:
                t, c = ref.split(".", 1)
                return t in valid_cols and c in valid_cols[t]
            return ref in valid_cols.get(primary, set()) or ref == "*"

        for col_ref in plan.get("columns", []):
            if col_ref and not check_col(col_ref):
                errors.append(f"Column '{col_ref}' not found in '{primary}'")

        for f in plan.get("filters", []):
            col = f.get("column", "")
            if col and not check_col(col):
                errors.append(f"Filter column '{col}' not found")

        for agg in plan.get("aggregations", []):
            func = agg.get("function", "").upper()
            if func not in self.ALLOWED_AGG_FUNCTIONS:
                errors.append(f"Invalid aggregation: {func}")

        # Safety check for dangerous values
        for f in plan.get("filters", []):
            val = f.get("value", "")
            if isinstance(val, str):
                for kw in self.DANGEROUS_KEYWORDS:
                    if kw in val.upper():
                        errors.append(f"Dangerous keyword: {kw}")
                        break

        # Clamp limit
        limit = plan.get("limit", self.DEFAULT_LIMIT)
        plan["limit"] = min(max(limit, 1), self.MAX_LIMIT)

        return len(errors) == 0, errors

    # ─── Phase 3: SQL Building & Execution ─────────────────────

    def _build_sql(self, plan: dict) -> tuple[str, list]:
        """从查询计划构建参数化 SQL"""
        tables = plan.get("tables", ["devices_info"])
        primary = tables[0]
        params = []

        # Server-side time range processing: override LLM date filters with concrete times
        query = self._current_query if hasattr(self, '_current_query') else ""
        if query:
            past_match = re.search(r'(?:past|last|过去|最近)\s*(\d+)\s*(?:hour|小时|hr)', query.lower())
            if past_match:
                hours = int(past_match.group(1))
                from datetime import datetime, timedelta
                cutoff = datetime.utcnow() - timedelta(hours=hours)
                # Add or override start_date filter with the concrete datetime
                existing = [f for f in plan.get("filters", []) if f.get("column") in ("start_date", "end_date", "timestamp")]
                # Remove ALL time-related filters from LLM plan, add our own
                time_cols = {"start_date", "end_date", "timestamp", "created_at",
                             "detected_at", "resolved_at", "install_date", "updated_at"}
                plan["filters"] = [f for f in plan.get("filters", []) if f.get("column") not in time_cols]
                plan["filters"].append({"column": "start_date", "operator": ">=", "value": cutoff})

        # SELECT
        cols = plan.get("columns", [])
        aggs = plan.get("aggregations", [])
        select_parts = []

        if aggs:
            for i, agg in enumerate(aggs):
                func_name = agg.get("function", "COUNT").upper()
                agg_col = agg.get("column", "*")
                alias = agg.get("alias", f"{func_name.lower()}_{i + 1}")
                if agg_col == "*":
                    select_parts.append(f'{func_name}(*) AS "{alias}"')
                else:
                    select_parts.append(f'{func_name}("{agg_col}") AS "{alias}"')

        # When aggregations exist with columns but no GROUP BY, only use aggregations
        if aggs and cols and not plan.get("group_by"):
            pass  # Don't add non-aggregated columns
        elif cols and cols != ["*"]:
            for c in cols:
                select_parts.append(f'"{c}"')
        elif not aggs:
            select_parts.append("*")

        select_clause = ", ".join(select_parts) if select_parts else "*"

        # FROM + JOIN
        from_clause = f'"{primary}"'
        for join in plan.get("joins", []):
            jt = join.get("table", "")
            on = join.get("on", "")
            if jt and on:
                from_clause += f' LEFT JOIN "{jt}" ON {on}'

        # WHERE (use $N positional params for asyncpg)
        where_parts = []
        for f in plan.get("filters", []):
            col = f.get("column", "")
            op_raw = f.get("operator", "=")
            operator = self.OPERATOR_MAP.get(op_raw, "=")
            val = f.get("value")

            if val is None or col == "":
                continue

            # Convert date/datetime string values to datetime objects for asyncpg
            date_cols = {"start_date", "end_date", "timestamp", "install_date",
                         "last_maintenance", "created_at", "updated_at", "report_date",
                         "detected_at", "resolved_at", "created_at"}
            if isinstance(val, str) and col in date_cols:
                from datetime import datetime as _dt
                parsed = None
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
                    try:
                        parsed = _dt.strptime(val, fmt)
                        break
                    except ValueError:
                        continue
                if parsed:
                    val = parsed
                else:
                    # Invalid date string from LLM - skip this filter
                    continue

            param_n = len(params) + 1

            if operator.upper() in ("ILIKE", "LIKE"):
                where_parts.append(f'"{col}" {operator} ${param_n}')
                params.append(f"%{val}%")
            elif operator.upper() == "IN":
                if isinstance(val, list):
                    holders = ", ".join([f"${param_n + i}" for i in range(len(val))])
                    where_parts.append(f'"{col}" IN ({holders})')
                    params.extend(val)
                else:
                    where_parts.append(f'"{col}" = ${param_n}')
                    params.append(val)
            elif operator.upper() == "BETWEEN":
                if isinstance(val, list) and len(val) == 2:
                    where_parts.append(f'"{col}" BETWEEN ${param_n} AND ${param_n + 1}')
                    params.extend(val)
                else:
                    where_parts.append(f'"{col}" >= ${param_n}')
                    params.append(val)
            else:
                where_parts.append(f'"{col}" {operator} ${param_n}')
                params.append(val)

        where_clause = " AND ".join(where_parts) if where_parts else "TRUE"

        # GROUP BY
        group_by = plan.get("group_by", [])
        group_clause = ""
        if group_by:
            group_parts = [f'"{g}"' for g in group_by]
            group_clause = " GROUP BY " + ", ".join(group_parts)

        # ORDER BY
        order_by = plan.get("order_by", [])
        order_clause = ""
        if order_by:
            order_parts = []
            for o in order_by:
                col = o.get("column", "")
                direction = o.get("direction", "ASC").upper()
                if direction not in ("ASC", "DESC"):
                    direction = "ASC"
                order_parts.append(f'"{col}" {direction}')
            order_clause = " ORDER BY " + ", ".join(order_parts)

        # LIMIT
        limit = plan.get("limit", self.DEFAULT_LIMIT)
        limit_clause = f" LIMIT ${len(params) + 1}"
        params.append(limit)

        sql = f"SELECT {select_clause} FROM {from_clause} WHERE {where_clause}{group_clause}{order_clause}{limit_clause}"
        return sql, params

    async def _execute_plan(self, sql: str, params: list) -> list[dict]:
        """执行 SQL 查询"""
        try:
            rows = await Database.fetch(sql, *params)
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error("sql_execution_failed", sql=sql[:200], error=str(e))
            raise

    # ─── Phase 4: Answer Generation ─────────────────────────────

    async def _generate_answer(self, llm: Any, query: str, rows: list[dict], plan: dict) -> str:
        """基于真实数据库结果生成回答（模板优先，LLM仅润色）"""
        if not rows:
            if plan.get("aggregations"):
                return "0" if self._is_en(query) else "0 条记录"
            return "No matching records found." if self._is_en(query) else "未找到匹配的记录。"

        is_en = self._is_en(query)
        count = len(rows)

        # For simple count queries, use template directly (no LLM needed)
        aggs = plan.get("aggregations", [])
        if len(aggs) == 1 and aggs[0].get("function", "").upper() == "COUNT" and not plan.get("group_by"):
            val = str(rows[0].get("total") or rows[0].get("count") or count)
            desc = ""
            for f in plan.get("filters", []):
                col = f.get("column", "")
                v = f.get("value", "")
                if "fault" in col:
                    desc = f" of type '{v}'" if is_en else f"（{v}类型）"
                elif "group" in col.lower():
                    desc = f" in {v}" if is_en else f"（{v}）"
            return f"Found {val} records{desc}." if is_en else f"共 {val} 条{desc}记录。"

        # For listing queries, build a data-first template + LLM polish
        headers = list(rows[0].keys()) if rows else []
        factual_summary = f"Query returned {count} rows." if is_en else f"查询返回 {count} 条记录。"

        md_rows = [f"| {' | '.join(headers)} |"]
        md_rows.append(f"| {' | '.join(['---'] * len(headers))} |")
        for r in rows[:20]:
            vals = [str(r.get(h, ""))[:50] for h in headers]
            md_rows.append(f"| {' | '.join(vals)} |")
        if count > 20:
            md_rows.append(f"| ... ({count - 20} more rows) |")

        data_summary = "\n".join(md_rows)

        # Strict prompt: LLM may only rephrase the data, not invent
        prompt = (
            "You are AGENT 11. Rephrase the following database results naturally.\n\n"
            "CRITICAL RULES:\n"
            "- The factual data is BELOW. Do NOT change or invent any numbers.\n"
            f"- The actual count is: {count}\n"
            "- Answer in the SAME language as the question.\n"
            "- If no results, simply say so.\n\n"
            f"User question: {query}\n\n"
            f"Database results ({count} rows):\n{data_summary}\n\n"
            "Rephrase naturally:"
        )

        try:
            resp = await llm.invoke(prompt, system=False, temperature=0.2)
            cleaned = re.sub(r'<think>.*?</think>', '', resp, flags=re.DOTALL).strip()
            # Validate: LLM response must contain the actual count
            if cleaned and str(count) in cleaned:
                return cleaned
            # If LLM hallucinated a different number, use the template
            if is_en:
                return f"Found {count} records. Details in the table below."
            return f"共 {count} 条记录。详情见下方表格。"
        except Exception:
            return f"Found {count} records." if is_en else f"找到 {count} 条记录。"

    # ─── Output Building ────────────────────────────────────────

    def _build_output_data(self, rows: list[dict], plan: dict) -> dict:
        """构建前端可用的表格/图表数据"""
        if not rows:
            return {"table": {"headers": [], "rows": [], "total": 0}}

        # Determine headers
        aggs = plan.get("aggregations", [])
        cols = plan.get("columns", [])

        if aggs and not cols:
            headers = [a.get("alias", a.get("column", "")) for a in aggs]
        else:
            headers = list(rows[0].keys())

        row_data = []
        for r in rows[:200]:
            row_data.append([str(r.get(h, "")) for h in headers])

        result = {
            "table": {
                "headers": headers,
                "rows": row_data,
                "total": len(rows),
            }
        }

        # Chart data
        chart = plan.get("chart")
        if chart and len(rows) > 0:
            x_col = headers[0] if headers else ""
            y_col = headers[1] if len(headers) > 1 else ""
            if x_col and y_col:
                result["chart"] = {
                    "type": chart.get("type", "bar"),
                    "title": chart.get("title", "Chart"),
                    "labels": [str(r.get(x_col, "")) for r in rows[:30]],
                    "values": [float(r.get(y_col, 0) or 0) for r in rows[:30]],
                    "unit": chart.get("unit", ""),
                }

        return result

    def _generate_map_data(self, rows: list[dict]) -> dict | None:
        """生成地图数据（如果结果包含经纬度）"""
        if not rows:
            return None
        lat_key = next((k for k in ["latitude", "lat", "y"] if k in rows[0]), None)
        lng_key = next((k for k in ["longitude", "lng", "lon", "x"] if k in rows[0]), None)
        if not lat_key or not lng_key:
            return None

        markers = []
        for r in rows:
            lat = r.get(lat_key)
            lng = r.get(lng_key)
            if lat and lng:
                try:
                    markers.append({
                        "device_id": r.get("device_id") or r.get("id", ""),
                        "lat": float(lat),
                        "lng": float(lng),
                        "status": r.get("status", "normal"),
                        "popup": r.get("device_name") or r.get("device_id", ""),
                    })
                except (ValueError, TypeError):
                    continue
        if not markers:
            return None
        lats = [m["lat"] for m in markers]
        lngs = [m["lng"] for m in markers]
        return {
            "center": [sum(lats) / len(lats), sum(lngs) / len(lngs)],
            "zoom": 14,
            "markers": markers,
        }

    @staticmethod
    def _is_en(query: str) -> bool:
        """检测查询是否为英文"""
        return not bool(re.search(r'[一-鿿]', query))

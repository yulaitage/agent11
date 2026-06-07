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
        is_en = self._is_en(query)

        prompt = (
            "You are a query planner for a smart infrastructure database. Given a user question and the database schema, "
            "produce a structured JSON query plan.\n\n"
            f"## Database Schema\n{schema_str}\n\n"
            f"## Sample Values from Database\n{sample_vals}\n\n"
            "## Available Tables and Their Purposes\n"
            "- devices_info: Device registry (device_id, device_name, device_type, status, location, group, street_name)\n"
            "- devices_fault: Fault records (device_id, fault type value, group, start_date, end_date)\n"
            "- devices_consumption: Consumption data by device (device_id, report_date, group, value)\n"
            "- groups_info: Group hierarchy (businessGroupId, businessGroupName, parentGroupId)\n"
            "- device_readings: Real-time readings (voltage, current, power, energy_kwh, timestamp)\n"
            "- energy_readings: Energy measurements per device/geozone/timestamp (energy_kwh)\n\n"
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
            "2. For fault type queries, filter on devices_fault.fault with the EXACT fault value (e.g. 'high_temperature', 'supply_loss', 'meter_fault')\n"
            "3. For 'group X' or '分组X', use businessGroupName='分组X'\n"
            "4. For time filters, output ISO 8601 dates (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)\n"
            "5. '过去N小时' -> calculate explicit ISO datetime (current time minus N hours)\n"
            "6. '2026年4月' -> '2026-04-01'\n"
            "7. When asking 'how many' / '多少个' / '统计', use COUNT aggregation\n"
            "8. GROUP BY when question asks 'by X' / 'per X' / 'each X' / '按X'\n"
            "9. For chart data, set chart: {\"type\": \"bar\"|\"line\"|\"pie\", \"title\": \"...\", \"unit\": \"...\"}\n"
            "10. The device_id in devices_fault is BIGINT, in devices_info it's VARCHAR\n"
            "11. Set reasonable LIMIT (default 100, max 200)\n"
            "12. When no specific columns needed, use ['*']\n"
            "13. Detect query language — respond in the same language as the question\n"
            "14. Do NOT invent column names that don't exist in the schema\n\n"
            "Generate ONLY the JSON. No other text.\n\n"
            f"User question: {query}"
        )

        try:
            response = await llm.invoke(prompt, system=False, temperature=0.1)
            plan = self._parse_json(response)
            if plan and isinstance(plan, dict):
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
        """兜底查询计划"""
        is_en = self._is_en(query)
        return {
            "tables": ["devices_info"],
            "columns": ["device_id", "device_name", "device_type", "status", "businessGroupName"],
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
        param_idx = 0

        # SELECT
        cols = plan.get("columns", [])
        aggs = plan.get("aggregations", [])
        select_parts = []

        if aggs:
            for agg in aggs:
                param_idx += 1
                func_name = agg.get("function", "COUNT").upper()
                agg_col = agg.get("column", "*")
                alias = agg.get("alias", f"{func_name.lower()}_{param_idx}")
                if agg_col == "*":
                    select_parts.append(f'{func_name}(*) AS "{alias}"')
                else:
                    select_parts.append(f'{func_name}("{agg_col}") AS "{alias}"')

        if cols and cols != ["*"]:
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

        # WHERE
        where_parts = []
        for f in plan.get("filters", []):
            col = f.get("column", "")
            op_raw = f.get("operator", "=")
            operator = self.OPERATOR_MAP.get(op_raw, "=")
            val = f.get("value")

            if val is None or col == "":
                continue

            param_idx += 1

            if operator.upper() == "ILIKE" or operator.upper() == "LIKE":
                where_parts.append(f'"{col}" {operator} ${param_idx}')
                params.append(f"%{val}%")
            elif operator.upper() == "IN":
                if isinstance(val, list):
                    placeholders = ", ".join([f"${param_idx + i}" for i in range(len(val))])
                    where_parts.append(f'"{col}" IN ({placeholders})')
                    params.extend(val)
                    param_idx += len(val) - 1
                else:
                    where_parts.append(f'"{col}" = ${param_idx}')
                    params.append(val)
            elif operator.upper() == "BETWEEN":
                if isinstance(val, list) and len(val) == 2:
                    where_parts.append(f'"{col}" BETWEEN ${param_idx} AND ${param_idx + 1}')
                    params.extend(val)
                    param_idx += 1
                else:
                    where_parts.append(f'"{col}" >= ${param_idx}')
                    params.append(val)
            else:
                where_parts.append(f'"{col}" {operator} ${param_idx}')
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
        param_idx += 1
        limit = plan.get("limit", self.DEFAULT_LIMIT)
        limit_clause = f" LIMIT ${param_idx}"
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
        """用 LLM 基于真实数据生成回答"""
        if not rows:
            if plan.get("aggregations"):
                return "0" if self._is_en(query) else "0 条记录"
            return "No matching records found." if self._is_en(query) else "未找到匹配的记录。"

        is_en = self._is_en(query)
        count = len(rows)

        # For simple count queries, just return the number
        aggs = plan.get("aggregations", [])
        if len(aggs) == 1 and aggs[0].get("function", "").upper() == "COUNT" and not plan.get("group_by"):
            val = rows[0].get("total") or rows[0].get("count") or count
            return f"Total: {val}" if is_en else f"共 {val} 条"

        # Build markdown table for LLM
        headers = list(rows[0].keys()) if rows else []
        md_rows = [f"| {' | '.join(headers)} |"]
        md_rows.append(f"| {' | '.join(['---'] * len(headers))} |")
        for r in rows[:20]:
            vals = [str(r.get(h, ""))[:50] for h in headers]
            md_rows.append(f"| {' | '.join(vals)} |")
        if count > 20:
            md_rows.append(f"| ... ({count - 20} more rows) |")

        data_summary = "\n".join(md_rows)

        prompt = (
            "You are AGENT 11, a smart infrastructure management AI assistant. "
            "Generate a natural language answer based on REAL database query results.\n\n"
            "Rules:\n"
            "1. Base your answer STRICTLY on the provided data\n"
            "2. Include specific numbers and examples from the data\n"
            "3. If data has groups, summarize each group\n"
            "4. Answer in the SAME language as the question\n"
            "5. Keep it concise and direct\n"
            "6. Do NOT mention SQL or technical details\n"
            "7. If no results, say so and suggest what data IS available\n\n"
            f"User question: {query}\n\n"
            f"Results ({count} rows):\n{data_summary}\n\n"
            "Generate a natural language answer:"
        )

        try:
            resp = await llm.invoke(prompt, system=False, temperature=0.3)
            cleaned = re.sub(r'<think>.*?</think>', '', resp, flags=re.DOTALL).strip()
            return cleaned if cleaned else (f"Found {count} records." if is_en else f"找到 {count} 条记录。")
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

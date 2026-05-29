"""General Chat 技能 - 通用 LLM 对话（带领域约束）"""
from typing import Any
from datetime import datetime as dt
from app.agent.skills.base import BaseSkill
from app.agent.context import ConversationContext
from app.db.repositories.device import DeviceRepository
from app.db.repositories.fault import FaultRepository
from app.db.repositories.reading import ReadingRepository


class GeneralChatSkill(BaseSkill):
    """
    General Chat 技能 - 用于通用对话，但聚焦智慧设备设施管理领域。

    设计原则：
    1. 灵活应答：用户的每句话都根据实际情况（系统数据、上下文）回复
    2. 领域约束：非设备管理话题委婉引导回专业领域
    3. 数据感知：尽可能结合实时系统数据来回答，而非空泛回复
    """

    name = "general_chat"

    # 设施管理领域关键词（用于判断查询是否相关）
    INFRA_KEYWORDS = [
        "路灯", "灯", "控制器", "传感器", "设备", "区域", "区",
        "故障", "警告", "离线", "能耗", "用电", "功率", "电压", "电流",
        "通信", "网络", "排查", "诊断", "预测", "报表", "报告",
        "养护", "维护", "维修", "亮", "闪烁", "闪", "不亮",
        "原始数据", "协议", "解析", "地图", "位置", "街道",
        "系统", "平台", "数据", "查询", "统计", "汇总", "对比",
        "你好", "谢谢", "抱歉", "请问", "帮助", "介绍", "是什么",
        "how", "what", "why", "when", "where", "can you", "help",
        "hello", "hi", "thanks", "thank",
    ]

    # 明确超出范围的话题（需要坚定但礼貌地拒绝）
    OUT_OF_SCOPE_TOPICS = [
        "股票", "基金", "投资", "理财", "比特币", "crypto", "trading",
        "政治", "选举", "政府", "政党", "战争", "军事",
        "色情", "赌博", "毒品", "暴力", "犯罪",
        "私人医生", "医疗诊断", "开药", "处方", "疾病治疗",
        "算命", "占卜", "星座", "风水", "塔罗",
        "写作业", "考试作弊", "代写", "论文代写",
    ]

    # 边缘话题（可以简要回答但引导回设施管理）
    EDGE_TOPICS = [
        "天气", "新闻", "体育", "娱乐", "电影", "音乐", "游戏",
        "菜谱", "做饭", "旅游", "购物", "穿搭", "化妆",
    ]

    async def execute(
        self,
        llm: Any,
        query: str,
        context: ConversationContext
    ) -> dict[str, Any]:
        """执行通用对话"""
        reasoning_chain = []
        query_lower = query.lower()

        # 1. 检查明确超出范围的话题
        for topic in self.OUT_OF_SCOPE_TOPICS:
            if topic in query_lower:
                reasoning_chain.extend(await self._build_reasoning_chain([
                    ("话题边界检查", f"检测到超出服务范围的话题: {topic}", "礼貌拒绝并引导")
                ]))
                return {
                    "answer": (
                        "抱歉，这个话题超出了我的服务范围。\n\n"
                        "我是 **AGENT 11**，专注于 **智慧设备设施管理**，"
                        "尤其在智能路灯控制系统的数据查询、故障排查、养护报表、"
                        "预测分析和灵活报表等方面可以为您提供帮助。\n\n"
                        "您可以这样问我：\n"
                        "• \"55区今天有多少设备在线？\"\n"
                        "• \"帮我排查通信丢失的设备\"\n"
                        "• \"生成本周养护报告\"\n"
                        "• \"预测未来24小时可能故障的设备\""
                    ),
                    "reasoning_chain": reasoning_chain,
                    "confidence": 0.95,
                    "map_data": None,
                    "data": None,
                    "sources": []
                }

        # 2. 检查是否是设施管理相关查询
        is_infra_related = any(kw in query_lower for kw in self.INFRA_KEYWORDS)

        # 3. 检查是否是边缘话题
        for topic in self.EDGE_TOPICS:
            if topic in query_lower:
                reasoning_chain.extend(await self._build_reasoning_chain([
                    ("话题边界检查", f"检测到边缘话题: {topic}", "简要回应并引导回专业领域")
                ]))
                brief = await llm.invoke(
                    f"用户问了一个边缘话题: '{query}'。"
                    f"请用 1-2 句话简要回应，然后自然地将话题引导回智慧设备设施管理领域。"
                    f"语气要友好、专业。",
                    system=True
                )
                return {
                    "answer": brief,
                    "reasoning_chain": reasoning_chain,
                    "confidence": 0.8,
                    "map_data": None,
                    "data": None,
                    "sources": []
                }

        # 4. 非设施管理话题 → 委婉限制
        if not is_infra_related:
            reasoning_chain.extend(await self._build_reasoning_chain([
                ("领域校验", f"用户问题不属于设施管理范围: {query}", "委婉引导用户提供设施管理相关问题")
            ]))
            guided_response = await llm.invoke(
                f"用户说: '{query}'\n\n"
                f"这个话题似乎与智慧设备设施管理（如智能路灯、控制器、能耗、故障排查等）没有直接关联。"
                f"请用友好、自然的方式回应用户，表示你更擅长设施管理领域，"
                f"并给出 2-3 个相关的示例问题来引导用户。"
                f"语气不要生硬，要像一位乐于助人的技术顾问。",
                system=True
            )
            return {
                "answer": guided_response,
                "reasoning_chain": reasoning_chain,
                "confidence": 0.85,
                "map_data": None,
                "data": None,
                "sources": []
            }

        # 5. 设施管理相关 → 查询数据库真实数据后用 LLM 回答
        reasoning_chain.extend(await self._build_reasoning_chain([
            ("数据感知回复", "查询系统数据库获取实时数据", "用真实数据生成回答")
        ]))

        data_summary = await self._query_system_data_for_query(query)

        system_prompt = """你是 AGENT 11，一个智能基础设施管理 AI 助手。

你的核心领域是智慧设备设施管理，特别是智能路灯控制系统。

回答原则：
1. 你的回答必须基于以下提供的真实数据库数据
2. 仔细阅读用户的问题，从数据中找到最相关的信息来回答
3. 用自然、友好的中文回答，不要输出固定模板
4. 数据中涉及的具体数字、设备、区域必须准确引用
5. 如果数据不足以回答用户的问题，如实告知，并给出建议
6. 保持专业、友好、简洁的语调"""

        chat_response = await llm.invoke(
            f"## 用户问题\n{query}\n\n"
            f"## 系统数据库中的实时数据\n{data_summary}\n\n"
            f"请根据以上提供的数据库真实数据，针对用户的问题给出准确的回答。",
            system=system_prompt,
            temperature=0.3
        )

        return {
            "answer": chat_response,
            "reasoning_chain": reasoning_chain,
            "confidence": 0.9,
            "map_data": None,
            "data": None,
            "sources": []
        }

    async def _query_system_data_for_query(self, query: str) -> str:
        """查询系统数据库，获取与用户查询相关的实时数据摘要"""
        import re
        q = query.lower()
        parts = []

        # 直接使用 asyncpg 查询，绕过 Repository 层
        try:
            from app.db.postgres import Database
            pool = Database.get_pool()
            async with pool.acquire() as conn:
                # 设备总数与状态分布
                result = await conn.fetchval("SELECT count(*) FROM devices_info")
                total = result or 0

                normal = await conn.fetchval(
                    "SELECT count(*) FROM devices_info WHERE status = 'normal'"
                )
                fault = await conn.fetchval(
                    "SELECT count(*) FROM devices_info WHERE status = 'fault'"
                )
                parts.append(
                    f"设备概览：共 {total} 台（正常 {normal or 0} | 故障 {fault or 0}）"
                )
        except Exception as e:
            parts.append(f"设备概览：查询失败 ({str(e)[:50]})")

        # 故障记录查询
        try:
            if "故障" in query or "事件" in query or "告警" in query:
                # 解析分组
                group_match = re.search(r'分组(\d+)', query)
                group_path = None
                if group_match:
                    group_num = group_match.group(1)
                    group_path = f"0000/{group_num.zfill(4)}%"

                # 解析时间
                date_match = re.search(r'(\d{4})年\s*(\d{1,2})月', query)
                time_filter = ""
                params = []
                if date_match:
                    year, month = date_match.groups()
                    start_date = f"{year}-{month.zfill(2)}-01"
                    # 计算月末
                    next_month = int(month) + 1
                    next_year = int(year)
                    if next_month > 12:
                        next_month = 1
                        next_year += 1
                    end_date = f"{next_year}-{next_month:02d}-01"
                    # asyncpg requires datetime objects for date columns
                    start_dt = dt.strptime(start_date, "%Y-%m-%d")
                    end_dt = dt.strptime(end_date, "%Y-%m-%d")
                    if group_path:
                        fault_query = '''
                            SELECT count(*) FROM devices_fault
                            WHERE "businessGroupIdPath" LIKE $1
                            AND start_date >= $2 AND start_date < $3
                        '''
                        params = [group_path + "%", start_dt, end_dt]
                    else:
                        fault_query = "SELECT count(*) FROM devices_fault WHERE start_date >= $1 AND start_date < $2"
                        params = [start_dt, end_dt]

                    from app.db.postgres import Database
                    pool = Database.get_pool()
                    async with pool.acquire() as conn:
                        count = await conn.fetchval(fault_query, *params)
                        if count and count > 0:
                            parts.append(f"故障记录：共 {count} 条")
                        else:
                            parts.append("故障记录：未找到匹配记录")
        except Exception as e:
            parts.append(f"故障查询：失败 ({str(e)[:50]})")

        # 尝试查询具体故障类型
        try:
            if "故障" in query and ("什么" in query or "哪些" in query):
                from app.db.postgres import Database
                pool = Database.get_pool()
                async with pool.acquire() as conn:
                    # 先获取前几条故障记录
                    rows = await conn.fetch('''
                        SELECT fault, businessGroupName, start_date
                        FROM devices_fault
                        ORDER BY start_date DESC
                        LIMIT 5
                    ''')
                    if rows:
                        fault_summary = []
                        for r in rows:
                            fault_summary.append(
                                f"{r['fault']}({r['businessGroupName']}, {r['start_date']})"
                            )
                        parts.append(f"最新故障：{' | '.join(fault_summary)}")
        except Exception:
            pass

        return "\n".join(parts)

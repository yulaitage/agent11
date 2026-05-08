"""Skill Code Generator - LLM 生成技能代码"""
import structlog
from typing import Optional

from app.services.llm import LLMService
from app.agent.skills import SkillRegistry
from app.agent.context import ConversationContext

logger = structlog.get_logger()


SKILL_GENERATION_PROMPT = """你是一个技能代码生成器。根据用户需求描述，生成一个 Python 异步函数代码。

## 要求
1. 函数必须是 async def execute_skill(llm, query, context)
2. 返回格式：{{"answer": str, "reasoning_chain": list, "confidence": float, "data": dict}}
3. 使用 context 中的信息来构建回答
4. 可以调用 llm.invoke() 来获取 LLM 响应
5. 代码必须是完整可执行的 Python 代码

## 可用的 context 信息
- context.device_repo: 设备仓储 (find_by_id, find_all, count)
- context.reading_repo: 读数仓储 (get_device_readings, get_energy_readings, sum_energy)
- context.fault_repo: 故障仓储 (find_by_device, find_active, count_by_status)
- context.comm_repo: 通信日志仓储

## 示例技能代码模板

```python
# 查询技能
async def execute_skill(llm, query, context):
    # 解析查询中的参数
    geozone = context.context.get("geozone", "all")

    # 查询数据
    devices = await context.device_repo.find_all(geozone=geozone, limit=100)

    # 构建回答
    answer = f"找到 {{len(devices)}} 个设备"

    return {
        "answer": answer,
        "reasoning_chain": [
            {"step": 1, "action": "解析查询参数", "observation": f"geozone={{geozone}}", "conclusion": "参数解析完成"},
            {"step": 2, "action": "查询设备数据", "observation": f"找到 {{len(devices)}} 个设备", "conclusion": "数据查询完成"}
        ],
        "confidence": 0.9,
        "data": {"devices": devices, "count": len(devices)}
    }
```

## 输出格式
只返回代码，不要有其他解释。代码必须可以直接执行。
"""


class SkillCodeGenerator:
    """技能代码生成器"""

    @classmethod
    async def generate(
        cls,
        requirement: str,
        category: str = "custom"
    ) -> dict:
        """
        根据需求描述生成技能代码

        Args:
            requirement: 技能需求描述（自然语言）
            category: 技能分类

        Returns:
            dict: 包含 name, description, code, category
        """
        llm = LLMService.get_instance()

        # 生成技能名称和描述
        meta_prompt = f"""根据以下需求，生成技能的名称和描述。

需求：{requirement}
分类：{category}

请用 JSON 格式返回：
{{
    "name": "技能名称（英文，下划线分隔，如 energy_analysis）",
    "description": "技能的中文描述（一句话）"
}}
"""

        try:
            meta_response = await llm.invoke(meta_prompt, system=False)
            import json
            # 尝试解析 JSON
            try:
                meta = json.loads(meta_response)
            except:
                # 如果解析失败，尝试提取 JSON
                import re
                match = re.search(r'\{[^}]+\}', meta_response, re.DOTALL)
                if match:
                    meta = json.loads(match.group())
                else:
                    # 使用默认值
                    name = requirement.replace(" ", "_").lower()[:30]
                    meta = {"name": name, "description": requirement[:100]}

            name = meta.get("name", f"skill_{hash(requirement) % 10000}")
            description = meta.get("description", requirement[:200])

        except Exception as e:
            logger.warning("skill_meta_generation_failed", error=str(e))
            name = requirement.replace(" ", "_").lower()[:30]
            description = requirement[:200]

        # 生成代码
        code_prompt = f"""{SKILL_GENERATION_PROMPT}

## 需求
{requirement}

## 分类
{category}

请生成完整的 execute_skill 函数代码。代码必须：
1. 是完整可执行的 Python 代码
2. 使用 async/await 异步调用
3. 返回指定的格式
4. 包含合理的错误处理

只返回代码，不要任何其他文字。
"""

        try:
            code_response = await llm.invoke(code_prompt, system=False)

            # 清理代码（移除 markdown 代码块标记）
            code = cls._clean_code(code_response)

            # 验证代码可以编译
            if not cls._validate_code(code):
                logger.warning("generated_skill_code_invalid", code=code[:100])
                # 使用默认模板
                code = cls._generate_fallback_code(requirement)

        except Exception as e:
            logger.error("skill_code_generation_failed", error=str(e))
            code = cls._generate_fallback_code(requirement)

        return {
            "name": name,
            "description": description,
            "code": code,
            "category": category,
            "version": "1.0.0",
            "parameters": {"query": "string"},
            "output_schema": {
                "answer": "string",
                "reasoning_chain": "list",
                "confidence": "float",
                "data": "dict"
            }
        }

    @classmethod
    def _clean_code(cls, code_response: str) -> str:
        """清理 LLM 生成的代码"""
        import re

        # 移除 markdown 代码块标记
        code = code_response.strip()
        if code.startswith("```python"):
            code = code[7:]
        elif code.startswith("```"):
            code = code[3:]

        if code.endswith("```"):
            code = code[:-3]

        return code.strip()

    @classmethod
    def _validate_code(cls, code: str) -> bool:
        """验证代码可以编译"""
        try:
            import ast
            ast.parse(code)
            return True
        except SyntaxError:
            return False

    @classmethod
    def _generate_fallback_code(cls, requirement: str) -> str:
        """生成备用代码（当 LLM 生成失败时）"""
        return f'''
async def execute_skill(llm, query, context):
    """
    自动生成的技能：{requirement[:50]}
    """
    try:
        # 使用 LLM 分析需求
        response = await llm.invoke(
            f"请分析并回答以下问题：{{query}}",
            system=False
        )

        return {{
            "answer": str(response),
            "reasoning_chain": [
                {{
                    "step": 1,
                    "action": "理解用户需求",
                    "observation": "{requirement[:100]}",
                    "conclusion": "需求理解完成"
                }},
                {{
                    "step": 2,
                    "action": "调用 LLM 分析",
                    "observation": "LLM 响应成功",
                    "conclusion": "回答生成完成"
                }}
            ],
            "confidence": 0.7,
            "data": {{"raw_response": response}}
        }}
    except Exception as e:
        return {{
            "answer": f"处理请求时遇到错误：{{str(e)}}",
            "reasoning_chain": [],
            "confidence": 0.0,
            "data": {{"error": str(e)}}
        }}
'''


class SkillAutoInstaller:
    """技能自动安装器"""

    def __init__(self):
        self.skill_registry = SkillRegistry.get_instance()

    async def install_generated_skill(self, skill_def: dict) -> dict:
        """
        安装自动生成的技能

        Args:
            skill_def: 包含 name, description, code, category 的字典

        Returns:
            安装结果
        """
        name = skill_def["name"]

        # 检查是否已存在
        if await self.skill_registry.load_skill(skill_def):
            return {
                "status": "already_exists",
                "skill": name,
                "message": "Skill already installed"
            }

        # 尝试安装
        try:
            installed = await self.skill_registry.install_skill(
                name=name,
                description=skill_def["description"],
                code=skill_def["code"],
                category=skill_def.get("category", "custom"),
                parameters=skill_def.get("parameters"),
                output_schema=skill_def.get("output_schema"),
            )
            return {
                "status": "installed",
                "skill": installed,
                "message": "Skill generated and installed successfully"
            }
        except Exception as e:
            logger.error("auto_install_failed", skill=name, error=str(e))
            return {
                "status": "failed",
                "skill": name,
                "error": str(e)
            }

    async def generate_and_install(
        cls,
        requirement: str,
        category: str = "custom"
    ) -> dict:
        """
        一站式：生成并安装技能

        Args:
            requirement: 技能需求描述
            category: 技能分类

        Returns:
            安装结果
        """
        generator = SkillCodeGenerator()
        installer = SkillAutoInstaller()

        # 生成代码
        skill_def = await generator.generate(requirement, category)

        # 安装
        return await installer.install_generated_skill(skill_def)

"""技能管理 API"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.agent.skills import SkillRegistry

router = APIRouter()


class SkillInstallRequest(BaseModel):
    name: str
    description: str
    code: str  # 技能执行代码
    category: Optional[str] = "custom"
    parameters: Optional[dict] = None
    output_schema: Optional[dict] = None


class SkillUpdateRequest(BaseModel):
    description: Optional[str] = None
    code: Optional[str] = None
    category: Optional[str] = None
    parameters: Optional[dict] = None
    output_schema: Optional[dict] = None
    is_active: Optional[bool] = None


@router.get("/")
async def list_skills():
    """列出所有已安装的技能"""
    registry = SkillRegistry.get_instance()
    skills = registry.list_with_metadata()
    return {
        "skills": skills,
        "total": len(skills),
    }


@router.get("/{skill_name}")
async def get_skill(skill_name: str):
    """获取技能详情"""
    registry = SkillRegistry.get_instance()
    metadata = registry.get_metadata(skill_name)

    if not metadata:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")

    return metadata


@router.post("/install")
async def install_skill(request: SkillInstallRequest):
    """安装新技能"""
    registry = SkillRegistry.get_instance()

    # Product constraint: only allow the 5 core skills to be invoked.
    # Custom skills remain installable, but cannot override core skill names.
    reserved_core = {"query", "troubleshoot", "maintenance_report", "prediction", "flexible_report"}

    # 验证技能名称
    if not request.name.replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="Skill name must be alphanumeric (underscores allowed)")

    if request.name in reserved_core:
        raise HTTPException(status_code=403, detail="Cannot install/override reserved core skill names")

    if request.name in registry.list():
        raise HTTPException(status_code=409, detail=f"Skill '{request.name}' already installed")

    try:
        skill_def = await registry.install_skill(
            name=request.name,
            description=request.description,
            code=request.code,
            category=request.category,
            parameters=request.parameters,
            output_schema=request.output_schema,
        )
        return {
            "status": "installed",
            "skill": skill_def,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to install skill: {str(e)}")


@router.delete("/{skill_name}")
async def uninstall_skill(skill_name: str):
    """卸载技能"""
    registry = SkillRegistry.get_instance()

    metadata = registry.get_metadata(skill_name)
    if not metadata:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")

    if metadata.get("is_builtin"):
        raise HTTPException(status_code=403, detail="Cannot uninstall built-in skills")

    try:
        success = await registry.uninstall_skill(skill_name)
        if success:
            return {"status": "uninstalled", "skill": skill_name}
        else:
            raise HTTPException(status_code=500, detail="Failed to uninstall skill")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{skill_name}")
async def update_skill(skill_name: str, request: SkillUpdateRequest):
    """更新技能"""
    registry = SkillRegistry.get_instance()

    metadata = registry.get_metadata(skill_name)
    if not metadata:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")

    if metadata.get("is_builtin"):
        raise HTTPException(status_code=403, detail="Cannot update built-in skills")

    # 构建更新
    updates = {}
    if request.description is not None:
        updates["description"] = request.description
    if request.code is not None:
        updates["code"] = request.code
    if request.category is not None:
        updates["category"] = request.category
    if request.parameters is not None:
        updates["parameters"] = request.parameters
    if request.output_schema is not None:
        updates["output_schema"] = request.output_schema
    if request.is_active is not None:
        updates["is_active"] = request.is_active

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    # 更新数据库
    from app.db.repositories.skill import SkillRepository
    skill_def = await SkillRepository.update(skill_name, updates)

    if not skill_def:
        raise HTTPException(status_code=500, detail="Failed to update skill")

    # 如果代码更新了，重新加载技能
    if request.code is not None:
        success = await registry.reload_skill(skill_name)
        if not success:
            raise HTTPException(status_code=500, detail="Skill code failed to compile")

    return {"status": "updated", "skill": skill_def}


@router.post("/{skill_name}/reload")
async def reload_skill(skill_name: str):
    """重新加载技能"""
    registry = SkillRegistry.get_instance()

    metadata = registry.get_metadata(skill_name)
    if not metadata:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")

    success = await registry.reload_skill(skill_name)
    if success:
        return {"status": "reloaded", "skill": skill_name}
    else:
        raise HTTPException(status_code=500, detail="Failed to reload skill")


@router.post("/reload-all")
async def reload_all_skills():
    """重新加载所有自定义技能"""
    registry = SkillRegistry.get_instance()
    count = await registry.load_from_database()
    return {"status": "reloaded", "count": count}


@router.get("/{skill_name}/test")
async def test_skill(skill_name: str):
    """测试技能是否可以正常执行"""
    registry = SkillRegistry.get_instance()

    skill_func = registry.get(skill_name)
    if not skill_func:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")

    # 简单的语法检查
    try:
        from app.services.llm import LLMService
        llm = LLMService.get_instance()

        # 创建一个简单的测试上下文
        from app.agent.context import ConversationContext
        test_ctx = ConversationContext(
            user_id="test_user",
            chat_id="test_chat",
            skill=skill_name,
            query="test",
            context={}
        )

        return {
            "status": "ready",
            "skill": skill_name,
            "message": "Skill is ready to execute",
        }

    except Exception as e:
        return {
            "status": "error",
            "skill": skill_name,
            "message": str(e),
        }


class SkillGenerateRequest(BaseModel):
    requirement: str
    category: Optional[str] = "custom"


@router.post("/generate")
async def generate_skill(request: SkillGenerateRequest):
    """生成并安装新技能（AI 自动生成）"""
    from app.harness.autonomous.skill_creator import SkillCreator

    creator = SkillCreator()

    try:
        result = await creator.create_skill_on_demand(
            requirement=request.requirement,
            category=request.category or "custom"
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate skill: {str(e)}")


@router.get("/generated/list")
async def list_generated_skills():
    """列出本次会话自动创建的技能"""
    from app.harness.autonomous.skill_creator import SkillCreator

    creator = SkillCreator()
    return {
        "generated_skills": creator.get_created_skills(),
        "count": len(creator.get_created_skills())
    }


@router.post("/generate/preview")
async def preview_generated_skill(requirement: str, category: Optional[str] = "custom"):
    """预览生成的技能代码（不安装）"""
    from app.agent.skills.skill_generator import SkillCodeGenerator

    generator = SkillCodeGenerator()

    try:
        result = await generator.generate(
            requirement=requirement,
            category=category or "custom"
        )
        return {
            "status": "preview",
            "skill": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate skill: {str(e)}")

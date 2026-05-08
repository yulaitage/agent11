"""Skill Definition model - 动态技能定义"""
from sqlalchemy import Column, String, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.sql import func
from app.db.session import Base


class SkillDefinition(Base):
    """可安装的技能定义"""
    __tablename__ = "skill_definitions"

    name = Column(String, primary_key=True)
    description = Column(Text, nullable=False)
    code = Column(Text, nullable=False)  # 技能执行代码
    version = Column(String, default="1.0.0")
    category = Column(String, nullable=True)  # query, diagnose, report, utility
    parameters = Column(JSON, nullable=True)  # 输入参数定义
    output_schema = Column(JSON, nullable=True)  # 输出格式定义
    is_builtin = Column(Boolean, default=False)  # 内置技能不可删除
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

"""Group Info model"""
from sqlalchemy import Column, String, BigInteger, DateTime, Index
from app.db.session import Base


class GroupInfo(Base):
    __tablename__ = "groups_info"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    businessGroupId = Column(String(100), nullable=True)
    businessGroupName = Column(String(100), nullable=True)
    businessGroupIdPath = Column(String(100), nullable=True)
    businessGroupNamePath = Column(String(100), nullable=True)
    parentGroupId = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_groups_info_businessGroupId", "businessGroupId"),
        Index("ix_groups_info_parentGroupId", "parentGroupId"),
    )

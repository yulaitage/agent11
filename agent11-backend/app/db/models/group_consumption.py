"""Group Consumption model"""
from sqlalchemy import Column, String, BigInteger, Float, Date, Index
from app.db.session import Base


class GroupConsumption(Base):
    __tablename__ = "groups_consumption"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    report_date = Column(Date, nullable=True)
    businessGroupId = Column(String(100), nullable=True)
    businessGroupName = Column(String(100), nullable=True)
    businessGroupIdPath = Column(String(100), nullable=True)
    businessGroupNamePath = Column(String(100), nullable=True)
    value = Column(Float, nullable=True)

    __table_args__ = (
        Index("ix_groups_consumption_group_id", "businessGroupId"),
        Index("ix_groups_consumption_report_date", "report_date"),
    )

from typing import Optional, List
from sqlalchemy import String, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base


class Grant(Base):
    """基金资助表模型"""
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="主键ID"
    )
    
    grant_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="基金ID"
    )
    
    acronym: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="缩写"
    )
    
    agency: Mapped[Optional[str]] = mapped_column(
        String(300),
        nullable=True,
        comment="资助机构"
    )
    
    country: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="国家"
    )
    
    # 关系
    article_grants: Mapped[List["ArticleGrant"]] = relationship(
        "ArticleGrant",
        back_populates="grant",
        cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        UniqueConstraint('grant_id', 'agency', name='uq_grant_agency'),
    )
    
    def __repr__(self):
        return f"Grant(id={self.id}, grant_id={self.grant_id!r}, agency={self.agency!r})"
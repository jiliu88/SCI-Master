from typing import Optional, List
from sqlalchemy import String, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base


class Affiliation(Base):
    """机构表模型"""
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="主键ID"
    )
    
    # 完整机构信息（原始文本）
    affiliation: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="完整机构信息"
    )
    
    # 解析后的字段
    department: Mapped[Optional[str]] = mapped_column(
        String(300),
        nullable=True,
        comment="部门"
    )
    
    institution: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        index=True,
        comment="机构名称"
    )
    
    city: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="城市"
    )
    
    state: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="州/省"
    )
    
    country: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="国家"
    )
    
    email: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="联系邮箱"
    )
    
    # 关系
    author_affiliations: Mapped[List["ArticleAuthorAffiliation"]] = relationship(
        "ArticleAuthorAffiliation",
        back_populates="affiliation",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return f"Affiliation(id={self.id}, institution={self.institution!r}, country={self.country!r})"
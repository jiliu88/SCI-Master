from typing import Optional, List
from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base


class Author(Base):
    """作者表模型"""
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="主键ID"
    )
    
    # 作者姓名信息
    last_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="姓"
    )
    
    fore_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="名"
    )
    
    initials: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="缩写"
    )
    
    collective_name: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="团体作者名称"
    )
    
    # ORCID 标识符
    orcid: Mapped[Optional[str]] = mapped_column(
        String(20),
        unique=True,
        nullable=True,
        index=True,
        comment="ORCID标识符"
    )
    
    # 关系
    article_authors: Mapped[List["ArticleAuthor"]] = relationship(
        "ArticleAuthor",
        back_populates="author",
        cascade="all, delete-orphan"
    )
    
    # 作者-机构关系
    author_affiliations: Mapped[List["ArticleAuthorAffiliation"]] = relationship(
        "ArticleAuthorAffiliation",
        back_populates="author",
        cascade="all, delete-orphan"
    )
    
    @property
    def full_name(self) -> str:
        """获取完整姓名"""
        if self.collective_name:
            return self.collective_name
        
        parts = []
        if self.fore_name:
            parts.append(self.fore_name)
        if self.last_name:
            parts.append(self.last_name)
        
        return ' '.join(parts) if parts else ''
    
    def __repr__(self):
        if self.collective_name:
            return f"Author(id={self.id}, collective_name={self.collective_name!r})"
        return f"Author(id={self.id}, name={self.full_name!r}, orcid={self.orcid!r})"
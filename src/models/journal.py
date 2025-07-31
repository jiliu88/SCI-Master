from typing import Optional, List
from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base


class Journal(Base):
    """期刊表模型"""
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="主键ID"
    )
    
    # 期刊标题
    title: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        index=True,
        comment="期刊全称"
    )
    
    # 期刊缩写
    iso_abbreviation: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="ISO缩写"
    )
    
    # ISSN号
    issn: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        index=True,
        comment="ISSN号（印刷版）"
    )
    
    issn_linking: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="ISSN Linking"
    )
    
    # NLM标识
    nlm_unique_id: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        unique=True,
        index=True,
        comment="NLM唯一ID"
    )
    
    medline_ta: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="MedlineTA"
    )
    
    # 国家
    country: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="国家"
    )
    
    # 关系
    articles: Mapped[List["Article"]] = relationship(
        "Article",
        back_populates="journal"
    )
    
    def __repr__(self):
        return f"Journal(id={self.id}, title={self.title!r}, issn={self.issn!r})"
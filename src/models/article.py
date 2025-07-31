from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import String, Text, Date, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base


class Article(Base):
    """文献表模型"""
    
    # 主键使用DOI
    doi: Mapped[str] = mapped_column(
        String(100), 
        primary_key=True,
        comment="DOI标识符，作为主键"
    )
    
    # PubMed ID，可能为空
    pmid: Mapped[Optional[str]] = mapped_column(
        String(20),
        unique=True,
        nullable=True,
        index=True,
        comment="PubMed ID"
    )
    
    # 基本信息
    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="文献标题"
    )
    
    abstract: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="摘要"
    )
    
    pmc_id: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        index=True,
        comment="PMC ID"
    )
    
    language: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="语言"
    )
    
    pagination: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="页码"
    )
    
    volume: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="卷号"
    )
    
    issue: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="期号"
    )
    
    article_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        index=True,
        comment="文章发表日期"
    )
    
    # 外键
    journal_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey('journal.id'),
        nullable=True,
        index=True,
        comment="关联期刊ID"
    )
    
    # 其他信息
    copyright_info: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="版权信息"
    )
    
    coi_statement: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="利益冲突声明"
    )
    
    # 爬取相关
    last_crawled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="最后爬取时间"
    )
    
    # 关系
    journal: Mapped[Optional["Journal"]] = relationship(
        "Journal",
        back_populates="articles"
    )
    
    # 作者关系
    article_authors: Mapped[List["ArticleAuthor"]] = relationship(
        "ArticleAuthor",
        back_populates="article",
        cascade="all, delete-orphan"
    )
    
    # 关键词关系
    article_keywords: Mapped[List["ArticleKeyword"]] = relationship(
        "ArticleKeyword",
        back_populates="article",
        cascade="all, delete-orphan"
    )
    
    # MeSH术语关系
    article_mesh_terms: Mapped[List["ArticleMeshTerm"]] = relationship(
        "ArticleMeshTerm",
        back_populates="article",
        cascade="all, delete-orphan"
    )
    
    # 化学物质关系
    article_chemicals: Mapped[List["ArticleChemical"]] = relationship(
        "ArticleChemical",
        back_populates="article",
        cascade="all, delete-orphan"
    )
    
    # 文献类型关系
    article_publication_types: Mapped[List["ArticlePublicationType"]] = relationship(
        "ArticlePublicationType",
        back_populates="article",
        cascade="all, delete-orphan"
    )
    
    # 基金关系
    article_grants: Mapped[List["ArticleGrant"]] = relationship(
        "ArticleGrant",
        back_populates="article",
        cascade="all, delete-orphan"
    )
    
    # 引用关系（作为引用方）
    citing_references: Mapped[List["ArticleReference"]] = relationship(
        "ArticleReference",
        foreign_keys="ArticleReference.citing_doi",
        back_populates="citing_article",
        cascade="all, delete-orphan"
    )
    
    # 引用关系（作为被引方）
    cited_references: Mapped[List["ArticleReference"]] = relationship(
        "ArticleReference",
        foreign_keys="ArticleReference.cited_doi",
        back_populates="cited_article"
    )
    
    # 其他ID
    other_ids: Mapped[List["ArticleIds"]] = relationship(
        "ArticleIds",
        back_populates="article",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return f"Article(doi={self.doi!r}, title={self.title[:50]!r}...)"
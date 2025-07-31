from typing import Optional, List
from sqlalchemy import String, Integer, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base


class Keyword(Base):
    """关键词表模型"""
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="主键ID"
    )
    
    keyword: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="关键词"
    )
    
    keyword_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="关键词类型（Author/Other）"
    )
    
    # 关系
    article_keywords: Mapped[List["ArticleKeyword"]] = relationship(
        "ArticleKeyword",
        back_populates="keyword",
        cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        UniqueConstraint('keyword', 'keyword_type', name='uq_keyword_type'),
    )
    
    def __repr__(self):
        return f"Keyword(id={self.id}, keyword={self.keyword!r}, type={self.keyword_type!r})"


class MeshTerm(Base):
    """MeSH术语表模型"""
    __tablename__ = "mesh_terms"
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="主键ID"
    )
    
    descriptor_name: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        comment="描述符名称"
    )
    
    descriptor_ui: Mapped[Optional[str]] = mapped_column(
        String(50),
        unique=True,
        nullable=True,
        index=True,
        comment="描述符UI"
    )
    
    # 关系
    article_mesh_terms: Mapped[List["ArticleMeshTerm"]] = relationship(
        "ArticleMeshTerm",
        back_populates="mesh_term",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return f"MeshTerm(id={self.id}, name={self.descriptor_name!r}, ui={self.descriptor_ui!r})"


class MeshQualifier(Base):
    """MeSH限定词表模型"""
    __tablename__ = "mesh_qualifiers"
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="主键ID"
    )
    
    qualifier_name: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        comment="限定词名称"
    )
    
    qualifier_ui: Mapped[Optional[str]] = mapped_column(
        String(50),
        unique=True,
        nullable=True,
        index=True,
        comment="限定词UI"
    )
    
    # 关系
    article_mesh_qualifiers: Mapped[List["ArticleMeshQualifier"]] = relationship(
        "ArticleMeshQualifier",
        back_populates="qualifier",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return f"MeshQualifier(id={self.id}, name={self.qualifier_name!r}, ui={self.qualifier_ui!r})"


class Chemical(Base):
    """化学物质表模型"""
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="主键ID"
    )
    
    name_of_substance: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        comment="化学物质名称"
    )
    
    registry_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        unique=True,
        nullable=True,
        index=True,
        comment="注册号"
    )
    
    # 关系
    article_chemicals: Mapped[List["ArticleChemical"]] = relationship(
        "ArticleChemical",
        back_populates="chemical",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return f"Chemical(id={self.id}, name={self.name_of_substance!r}, registry={self.registry_number!r})"


class PublicationType(Base):
    """文献类型表模型"""
    __tablename__ = "publication_types"
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="主键ID"
    )
    
    type_name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        comment="类型名称"
    )
    
    # 关系
    article_publication_types: Mapped[List["ArticlePublicationType"]] = relationship(
        "ArticlePublicationType",
        back_populates="publication_type",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return f"PublicationType(id={self.id}, name={self.type_name!r})"
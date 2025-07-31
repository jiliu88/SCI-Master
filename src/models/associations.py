from typing import Optional
from sqlalchemy import String, Integer, Boolean, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base


class ArticleAuthor(Base):
    """文献-作者关系表模型"""
    __tablename__ = "article_authors"
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    
    article_doi: Mapped[str] = mapped_column(
        String(100),
        ForeignKey('article.doi'),
        nullable=False,
        index=True,
        comment="文献DOI"
    )
    
    author_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('author.id'),
        nullable=False,
        index=True,
        comment="作者ID"
    )
    
    author_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="作者顺序"
    )
    
    is_corresponding: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="是否通讯作者"
    )
    
    equal_contrib: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="是否同等贡献"
    )
    
    # 关系
    article: Mapped["Article"] = relationship("Article", back_populates="article_authors")
    author: Mapped["Author"] = relationship("Author", back_populates="article_authors")
    
    __table_args__ = (
        UniqueConstraint('article_doi', 'author_id', 'author_order', name='uq_article_author_order'),
    )


class ArticleAuthorAffiliation(Base):
    """文献-作者-机构关系表模型"""
    __tablename__ = "article_author_affiliations"
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    
    article_doi: Mapped[str] = mapped_column(
        String(100),
        ForeignKey('article.doi'),
        nullable=False,
        index=True,
        comment="文献DOI"
    )
    
    author_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('author.id'),
        nullable=False,
        index=True,
        comment="作者ID"
    )
    
    affiliation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('affiliation.id'),
        nullable=False,
        index=True,
        comment="机构ID"
    )
    
    affiliation_order: Mapped[int] = mapped_column(
        Integer,
        default=1,
        comment="机构顺序"
    )
    
    # 关系
    author: Mapped["Author"] = relationship("Author", back_populates="author_affiliations")
    affiliation: Mapped["Affiliation"] = relationship("Affiliation", back_populates="author_affiliations")


class ArticleReference(Base):
    """文献引用关系表模型"""
    __tablename__ = "article_references"
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    
    citing_doi: Mapped[str] = mapped_column(
        String(100),
        ForeignKey('article.doi'),
        nullable=False,
        index=True,
        comment="引用文献DOI"
    )
    
    cited_doi: Mapped[Optional[str]] = mapped_column(
        String(100),
        ForeignKey('article.doi'),
        nullable=True,
        index=True,
        comment="被引文献DOI"
    )
    
    cited_pmid: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        index=True,
        comment="被引文献PMID"
    )
    
    reference_string: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="原始引用字符串"
    )
    
    reference_order: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="引用顺序"
    )
    
    # 关系
    citing_article: Mapped["Article"] = relationship(
        "Article",
        foreign_keys=[citing_doi],
        back_populates="citing_references"
    )
    cited_article: Mapped[Optional["Article"]] = relationship(
        "Article",
        foreign_keys=[cited_doi],
        back_populates="cited_references"
    )


class ArticleKeyword(Base):
    """文献-关键词关系表模型"""
    __tablename__ = "article_keywords"
    
    article_doi: Mapped[str] = mapped_column(
        String(100),
        ForeignKey('article.doi'),
        primary_key=True,
        comment="文献DOI"
    )
    
    keyword_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('keyword.id'),
        primary_key=True,
        comment="关键词ID"
    )
    
    # 关系
    article: Mapped["Article"] = relationship("Article", back_populates="article_keywords")
    keyword: Mapped["Keyword"] = relationship("Keyword", back_populates="article_keywords")


class ArticleMeshTerm(Base):
    """文献-MeSH关系表模型"""
    __tablename__ = "article_mesh_terms"
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    
    article_doi: Mapped[str] = mapped_column(
        String(100),
        ForeignKey('article.doi'),
        nullable=False,
        index=True,
        comment="文献DOI"
    )
    
    mesh_term_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('mesh_terms.id'),
        nullable=False,
        comment="MeSH术语ID"
    )
    
    is_major_topic: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        index=True,
        comment="是否主要主题"
    )
    
    # 关系
    article: Mapped["Article"] = relationship("Article", back_populates="article_mesh_terms")
    mesh_term: Mapped["MeshTerm"] = relationship("MeshTerm", back_populates="article_mesh_terms")
    mesh_qualifiers: Mapped[list["ArticleMeshQualifier"]] = relationship(
        "ArticleMeshQualifier",
        back_populates="article_mesh_term",
        cascade="all, delete-orphan"
    )


class ArticleMeshQualifier(Base):
    """文献-MeSH-限定词关系表模型"""
    __tablename__ = "article_mesh_qualifiers"
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    
    article_mesh_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('article_mesh_terms.id'),
        nullable=False,
        comment="article_mesh_terms表的ID"
    )
    
    qualifier_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('mesh_qualifiers.id'),
        nullable=False,
        comment="限定词ID"
    )
    
    is_major_topic: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="是否主要主题"
    )
    
    # 关系
    article_mesh_term: Mapped["ArticleMeshTerm"] = relationship(
        "ArticleMeshTerm",
        back_populates="mesh_qualifiers"
    )
    qualifier: Mapped["MeshQualifier"] = relationship(
        "MeshQualifier",
        back_populates="article_mesh_qualifiers"
    )


class ArticleChemical(Base):
    """文献-化学物质关系表模型"""
    __tablename__ = "article_chemicals"
    
    article_doi: Mapped[str] = mapped_column(
        String(100),
        ForeignKey('article.doi'),
        primary_key=True,
        comment="文献DOI"
    )
    
    chemical_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('chemical.id'),
        primary_key=True,
        comment="化学物质ID"
    )
    
    # 关系
    article: Mapped["Article"] = relationship("Article", back_populates="article_chemicals")
    chemical: Mapped["Chemical"] = relationship("Chemical", back_populates="article_chemicals")


class ArticlePublicationType(Base):
    """文献-类型关系表模型"""
    __tablename__ = "article_publication_types"
    
    article_doi: Mapped[str] = mapped_column(
        String(100),
        ForeignKey('article.doi'),
        primary_key=True,
        comment="文献DOI"
    )
    
    publication_type_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('publication_types.id'),
        primary_key=True,
        comment="文献类型ID"
    )
    
    # 关系
    article: Mapped["Article"] = relationship("Article", back_populates="article_publication_types")
    publication_type: Mapped["PublicationType"] = relationship(
        "PublicationType",
        back_populates="article_publication_types"
    )


class ArticleGrant(Base):
    """文献-基金关系表模型"""
    __tablename__ = "article_grants"
    
    article_doi: Mapped[str] = mapped_column(
        String(100),
        ForeignKey('article.doi'),
        primary_key=True,
        comment="文献DOI"
    )
    
    grant_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('grant.id'),
        primary_key=True,
        comment="基金ID"
    )
    
    # 关系
    article: Mapped["Article"] = relationship("Article", back_populates="article_grants")
    grant: Mapped["Grant"] = relationship("Grant", back_populates="article_grants")


class ArticleIds(Base):
    """文献其他ID表模型"""
    __tablename__ = "article_ids"
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    
    article_doi: Mapped[str] = mapped_column(
        String(100),
        ForeignKey('article.doi'),
        nullable=False,
        index=True,
        comment="文献DOI"
    )
    
    id_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="ID类型（pii/pmc/mid等）"
    )
    
    id_value: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="ID值"
    )
    
    # 关系
    article: Mapped["Article"] = relationship("Article", back_populates="other_ids")
    
    __table_args__ = (
        UniqueConstraint('article_doi', 'id_type', name='uq_article_id_type'),
    )
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
import logging

from src.models import (
    Article, Author, Journal, Affiliation, Keyword, MeshTerm, MeshQualifier,
    Chemical, PublicationType, Grant, ArticleAuthor, ArticleAuthorAffiliation,
    ArticleKeyword, ArticleMeshTerm, ArticleMeshQualifier, ArticleChemical,
    ArticlePublicationType, ArticleGrant, ArticleIds
)
from src.crawler.affiliation_utils import AffiliationNormalizer

logger = logging.getLogger(__name__)


class ArticleProcessor:
    """文献数据处理器，负责将爬取的数据处理并保存到数据库"""
    
    def __init__(self):
        self.logger = logger
    
    async def process_and_save(
        self,
        article_data: Dict[str, Any],
        db: Session,
        update_existing: bool = False
    ) -> bool:
        """
        处理并保存文献数据
        
        Args:
            article_data: 文献数据字典
            db: 数据库会话
            update_existing: 是否更新已存在的文献
        
        Returns:
            是否保存成功
        """
        try:
            # 提取 DOI 和 PMID
            doi = article_data.get('doi')
            pmid = article_data.get('pmid')
            
            # DOI 是主键，必须存在
            if not doi:
                self.logger.warning(f"文献缺少 DOI，PMID: {pmid}，跳过保存")
                return False
            
            # 检查文献是否已存在
            existing_article = db.query(Article).filter(Article.doi == doi).first()
            
            if existing_article and not update_existing:
                self.logger.info(f"文献已存在，DOI: {doi}，跳过保存")
                return False
            
            # 处理期刊
            journal = await self._process_journal(article_data.get('journal', {}), db)
            
            # 创建或更新文献
            if existing_article:
                article = existing_article
                self.logger.info(f"更新文献，DOI: {doi}")
            else:
                article = Article(doi=doi)
                db.add(article)
                self.logger.info(f"创建新文献，DOI: {doi}")
            
            # 更新文献基本信息
            article.pmid = pmid
            article.title = article_data.get('title')
            article.abstract = article_data.get('abstract')
            article.language = article_data.get('language', 'eng')
            article.pagination = article_data.get('pagination')
            article.copyright_info = article_data.get('copyright_info')
            article.coi_statement = article_data.get('coi_statement')
            article.last_crawled_at = datetime.now()
            
            # 设置期刊
            if journal:
                article.journal_id = journal.id
                article.volume = article_data['journal'].get('volume')
                article.issue = article_data['journal'].get('issue')
                
                # 处理发表日期
                pub_date = article_data['journal'].get('pub_date', {})
                article.article_date = self._parse_date(pub_date)
            
            # 处理其他 ID
            await self._process_other_ids(article, article_data.get('other_ids', {}), db)
            
            # 如果是更新，先删除相关的关联数据
            if existing_article:
                await self._clear_associations(article, db)
            
            # 处理作者
            await self._process_authors(article, article_data.get('authors', []), db)
            
            # 处理关键词
            await self._process_keywords(article, article_data.get('keywords', []), db)
            
            # 处理 MeSH 术语
            await self._process_mesh_terms(article, article_data.get('mesh_terms', []), db)
            
            # 处理化学物质
            await self._process_chemicals(article, article_data.get('chemicals', []), db)
            
            # 处理文献类型
            await self._process_publication_types(article, article_data.get('publication_types', []), db)
            
            # 处理基金
            await self._process_grants(article, article_data.get('grants', []), db)
            
            # 提交前确保所有对象都在会话中
            db.flush()
            
            return True
            
        except Exception as e:
            self.logger.error(f"处理文献数据失败: {str(e)}", exc_info=True)
            db.rollback()
            return False
    
    async def _process_journal(self, journal_data: Dict[str, Any], db: Session) -> Optional[Journal]:
        """处理期刊数据"""
        if not journal_data or not journal_data.get('title'):
            return None
        
        # 查找或创建期刊
        journal = db.query(Journal).filter(
            Journal.title == journal_data['title']
        ).first()
        
        if not journal:
            journal = Journal(
                title=journal_data['title'],
                iso_abbreviation=journal_data.get('iso_abbreviation'),
                issn=journal_data.get('issn')
            )
            db.add(journal)
            db.flush()
        
        return journal
    
    async def _process_authors(self, article: Article, authors_data: List[Dict[str, Any]], db: Session):
        """处理作者数据"""
        for author_data in authors_data:
            # 查找或创建作者
            author = None
            
            # 优先使用 ORCID 查找
            orcid = author_data.get('orcid')
            if orcid:
                author = db.query(Author).filter(Author.orcid == orcid).first()
            
            # 如果没有 ORCID，使用姓名查找
            if not author:
                if author_data.get('collective_name'):
                    author = db.query(Author).filter(
                        Author.collective_name == author_data['collective_name']
                    ).first()
                else:
                    author = db.query(Author).filter(
                        Author.last_name == author_data.get('last_name'),
                        Author.fore_name == author_data.get('fore_name')
                    ).first()
            
            # 创建新作者
            if not author:
                author = Author(
                    last_name=author_data.get('last_name'),
                    fore_name=author_data.get('fore_name'),
                    initials=author_data.get('initials'),
                    collective_name=author_data.get('collective_name'),
                    orcid=orcid
                )
                db.add(author)
                db.flush()
            
            # 创建文献-作者关系
            article_author = ArticleAuthor(
                article_doi=article.doi,
                author_id=author.id,
                author_order=author_data.get('order', 1),
                is_corresponding=author_data.get('is_corresponding', False),
                equal_contrib=author_data.get('equal_contrib', False)
            )
            db.add(article_author)
            
            # 处理作者机构
            for affiliation_text in author_data.get('affiliations', []):
                await self._process_author_affiliation(
                    article.doi,
                    author.id,
                    affiliation_text,
                    db
                )
    
    async def _process_author_affiliation(
        self,
        article_doi: str,
        author_id: int,
        affiliation_text: str,
        db: Session
    ):
        """处理作者机构关系"""
        if not affiliation_text:
            return
        
        # 标准化机构名称
        normalized_name = AffiliationNormalizer.normalize(affiliation_text)
        
        # 获取所有现有机构
        existing_affiliations = db.query(Affiliation).all()
        candidates = [(aff.id, aff.affiliation) for aff in existing_affiliations]
        
        # 查找最佳匹配
        best_match_id = AffiliationNormalizer.find_best_match(
            affiliation_text, 
            candidates, 
            threshold=0.85
        )
        
        if best_match_id:
            # 使用现有机构
            affiliation_id = best_match_id
            self.logger.info(f"找到匹配的机构: {affiliation_text} -> ID: {best_match_id}")
        else:
            # 创建新机构
            components = AffiliationNormalizer.extract_components(affiliation_text)
            
            affiliation = Affiliation(
                affiliation=affiliation_text,
                normalized_name=normalized_name,
                department=components.get('department'),
                institution=components.get('institution'),
                city=components.get('city'),
                state=components.get('state'),
                country=components.get('country'),
                postal_code=components.get('postal_code')
            )
            db.add(affiliation)
            db.flush()
            affiliation_id = affiliation.id
            self.logger.info(f"创建新机构: {affiliation_text}")
        
        # 检查关系是否已存在
        existing_relation = db.query(ArticleAuthorAffiliation).filter(
            ArticleAuthorAffiliation.article_doi == article_doi,
            ArticleAuthorAffiliation.author_id == author_id,
            ArticleAuthorAffiliation.affiliation_id == affiliation_id
        ).first()
        
        if not existing_relation:
            # 创建文献-作者-机构关系
            article_author_affiliation = ArticleAuthorAffiliation(
                article_doi=article_doi,
                author_id=author_id,
                affiliation_id=affiliation_id
            )
            db.add(article_author_affiliation)
    
    async def _process_keywords(self, article: Article, keywords_data: List[Dict[str, str]], db: Session):
        """处理关键词"""
        for keyword_data in keywords_data:
            keyword_text = keyword_data.get('keyword')
            keyword_type = keyword_data.get('type', 'Other')
            
            if not keyword_text:
                continue
            
            # 查找或创建关键词
            keyword = db.query(Keyword).filter(
                Keyword.keyword == keyword_text,
                Keyword.keyword_type == keyword_type
            ).first()
            
            if not keyword:
                keyword = Keyword(
                    keyword=keyword_text,
                    keyword_type=keyword_type
                )
                db.add(keyword)
                db.flush()
            
            # 创建文献-关键词关系
            article_keyword = ArticleKeyword(
                article_doi=article.doi,
                keyword_id=keyword.id
            )
            db.add(article_keyword)
    
    async def _process_mesh_terms(self, article: Article, mesh_data: List[Dict[str, Any]], db: Session):
        """处理 MeSH 术语"""
        for mesh_item in mesh_data:
            descriptor_name = mesh_item.get('descriptor_name')
            descriptor_ui = mesh_item.get('descriptor_ui')
            
            if not descriptor_name:
                continue
            
            # 查找或创建 MeSH 术语
            mesh_term = None
            if descriptor_ui:
                mesh_term = db.query(MeshTerm).filter(
                    MeshTerm.descriptor_ui == descriptor_ui
                ).first()
            
            if not mesh_term:
                mesh_term = db.query(MeshTerm).filter(
                    MeshTerm.descriptor_name == descriptor_name
                ).first()
            
            if not mesh_term:
                mesh_term = MeshTerm(
                    descriptor_name=descriptor_name,
                    descriptor_ui=descriptor_ui
                )
                db.add(mesh_term)
                db.flush()
            
            # 创建文献-MeSH 关系
            article_mesh_term = ArticleMeshTerm(
                article_doi=article.doi,
                mesh_term_id=mesh_term.id,
                is_major_topic=mesh_item.get('is_major_topic', False)
            )
            db.add(article_mesh_term)
            db.flush()
            
            # 处理限定词
            for qualifier_data in mesh_item.get('qualifiers', []):
                await self._process_mesh_qualifier(
                    article_mesh_term.id,
                    qualifier_data,
                    db
                )
    
    async def _process_mesh_qualifier(
        self,
        article_mesh_id: int,
        qualifier_data: Dict[str, Any],
        db: Session
    ):
        """处理 MeSH 限定词"""
        qualifier_name = qualifier_data.get('name')
        qualifier_ui = qualifier_data.get('ui')
        
        if not qualifier_name:
            return
        
        # 查找或创建限定词
        qualifier = None
        if qualifier_ui:
            qualifier = db.query(MeshQualifier).filter(
                MeshQualifier.qualifier_ui == qualifier_ui
            ).first()
        
        if not qualifier:
            qualifier = db.query(MeshQualifier).filter(
                MeshQualifier.qualifier_name == qualifier_name
            ).first()
        
        if not qualifier:
            qualifier = MeshQualifier(
                qualifier_name=qualifier_name,
                qualifier_ui=qualifier_ui
            )
            db.add(qualifier)
            db.flush()
        
        # 创建关系
        article_mesh_qualifier = ArticleMeshQualifier(
            article_mesh_id=article_mesh_id,
            qualifier_id=qualifier.id,
            is_major_topic=qualifier_data.get('is_major_topic', False)
        )
        db.add(article_mesh_qualifier)
    
    async def _process_chemicals(self, article: Article, chemicals_data: List[Dict[str, str]], db: Session):
        """处理化学物质"""
        # 使用集合去重
        processed_chemicals = set()
        
        for chemical_data in chemicals_data:
            name = chemical_data.get('name')
            registry_number = chemical_data.get('registry_number')
            
            if not name:
                continue
            
            # 查找或创建化学物质
            chemical = None
            if registry_number and registry_number != '0':
                chemical = db.query(Chemical).filter(
                    Chemical.registry_number == registry_number
                ).first()
            
            if not chemical:
                chemical = db.query(Chemical).filter(
                    Chemical.name_of_substance == name
                ).first()
            
            if not chemical:
                chemical = Chemical(
                    name_of_substance=name,
                    registry_number=registry_number if registry_number != '0' else None
                )
                db.add(chemical)
                db.flush()
            
            # 避免重复添加关系
            if chemical.id not in processed_chemicals:
                processed_chemicals.add(chemical.id)
                
                # 检查关系是否已存在
                existing = db.query(ArticleChemical).filter(
                    ArticleChemical.article_doi == article.doi,
                    ArticleChemical.chemical_id == chemical.id
                ).first()
                
                if not existing:
                    article_chemical = ArticleChemical(
                        article_doi=article.doi,
                        chemical_id=chemical.id
                    )
                    db.add(article_chemical)
    
    async def _process_publication_types(self, article: Article, pub_types: List[str], db: Session):
        """处理文献类型"""
        for type_name in pub_types:
            if not type_name:
                continue
            
            # 查找或创建文献类型
            pub_type = db.query(PublicationType).filter(
                PublicationType.type_name == type_name
            ).first()
            
            if not pub_type:
                pub_type = PublicationType(type_name=type_name)
                db.add(pub_type)
                db.flush()
            
            # 创建文献-类型关系
            article_pub_type = ArticlePublicationType(
                article_doi=article.doi,
                publication_type_id=pub_type.id
            )
            db.add(article_pub_type)
    
    async def _process_grants(self, article: Article, grants_data: List[Dict[str, str]], db: Session):
        """处理基金信息"""
        for grant_data in grants_data:
            grant_id = grant_data.get('grant_id')
            agency = grant_data.get('agency')
            
            if not agency:  # 机构是必需的
                continue
            
            # 查找或创建基金
            grant = db.query(Grant).filter(
                Grant.grant_id == grant_id,
                Grant.agency == agency
            ).first()
            
            if not grant:
                grant = Grant(
                    grant_id=grant_id,
                    acronym=grant_data.get('acronym'),
                    agency=agency,
                    country=grant_data.get('country')
                )
                db.add(grant)
                db.flush()
            
            # 创建文献-基金关系
            article_grant = ArticleGrant(
                article_doi=article.doi,
                grant_id=grant.id
            )
            db.add(article_grant)
    
    async def _process_other_ids(self, article: Article, other_ids: Dict[str, str], db: Session):
        """处理其他 ID"""
        # 特殊处理 PMC ID
        if 'pmc' in other_ids:
            article.pmc_id = other_ids['pmc']
        
        # 需要跳过的 ID 类型（已经保存在 article 表中）
        skip_types = {'pmc', 'pubmed', 'doi'}
        
        # 保存其他类型的 ID
        for id_type, id_value in other_ids.items():
            if id_type and id_value and id_type not in skip_types:
                # 检查是否已存在
                existing = db.query(ArticleIds).filter(
                    ArticleIds.article_doi == article.doi,
                    ArticleIds.id_type == id_type
                ).first()
                
                if existing:
                    existing.id_value = id_value
                else:
                    article_id = ArticleIds(
                        article_doi=article.doi,
                        id_type=id_type,
                        id_value=id_value
                    )
                    db.add(article_id)
    
    async def _clear_associations(self, article: Article, db: Session):
        """清除文献的所有关联数据（用于更新时）"""
        # 删除作者关系
        db.query(ArticleAuthor).filter(
            ArticleAuthor.article_doi == article.doi
        ).delete()
        
        # 删除关键词关系
        db.query(ArticleKeyword).filter(
            ArticleKeyword.article_doi == article.doi
        ).delete()
        
        # 删除 MeSH 关系
        db.query(ArticleMeshTerm).filter(
            ArticleMeshTerm.article_doi == article.doi
        ).delete()
        
        # 删除化学物质关系
        db.query(ArticleChemical).filter(
            ArticleChemical.article_doi == article.doi
        ).delete()
        
        # 删除文献类型关系
        db.query(ArticlePublicationType).filter(
            ArticlePublicationType.article_doi == article.doi
        ).delete()
        
        # 删除基金关系
        db.query(ArticleGrant).filter(
            ArticleGrant.article_doi == article.doi
        ).delete()
        
        db.flush()
    
    def _parse_date(self, date_info: Dict[str, str]) -> Optional[datetime]:
        """解析日期"""
        year = date_info.get('year')
        if not year:
            return None
        
        month = date_info.get('month', '1')
        day = date_info.get('day', '1')
        
        # 处理月份名称
        month_map = {
            'jan': '1', 'feb': '2', 'mar': '3', 'apr': '4',
            'may': '5', 'jun': '6', 'jul': '7', 'aug': '8',
            'sep': '9', 'oct': '10', 'nov': '11', 'dec': '12'
        }
        
        month = month_map.get(month.lower(), month)
        
        try:
            return datetime.strptime(f"{year}-{month}-{day}", "%Y-%m-%d")
        except ValueError:
            try:
                return datetime.strptime(f"{year}-{month}-1", "%Y-%m-%d")
            except ValueError:
                try:
                    return datetime.strptime(f"{year}-1-1", "%Y-%m-%d")
                except ValueError:
                    return None
import asyncio
import logging
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.crawler.fetchers.search import SearchFetcher
from src.crawler.fetchers.detail import DetailFetcher
from src.crawler.fetchers.references import ReferencesFetcher
from src.crawler.fetchers.fulltext import FulltextFetcher
from src.crawler.processors.article import ArticleProcessor
from src.db.session import get_db
from src.models import Article
from src.config.settings import settings

logger = logging.getLogger(__name__)


class PubMedCrawler:
    """PubMed 爬虫主类，整合所有爬虫功能"""
    
    def __init__(self):
        """初始化爬虫"""
        self.search_fetcher = SearchFetcher()
        self.detail_fetcher = DetailFetcher()
        self.references_fetcher = ReferencesFetcher()
        self.fulltext_fetcher = FulltextFetcher()
        self.article_processor = ArticleProcessor()
        self.logger = logger
    
    async def crawl_by_keyword(
        self,
        keyword: str,
        max_results: Optional[int] = None,
        save_to_db: bool = True,
        fetch_references: bool = False,
        fetch_fulltext: bool = False
    ) -> Dict[str, Any]:
        """
        通过关键词爬取文献
        
        Args:
            keyword: 搜索关键词
            max_results: 最大结果数
            save_to_db: 是否保存到数据库
            fetch_references: 是否获取引用关系
            fetch_fulltext: 是否获取全文
        
        Returns:
            爬取结果统计
        """
        start_time = datetime.now()
        stats = {
            'keyword': keyword,
            'total_found': 0,
            'articles_fetched': 0,
            'articles_saved': 0,
            'references_fetched': 0,
            'fulltext_fetched': 0,
            'errors': [],
            'duration': 0
        }
        
        try:
            self.logger.info(f"开始爬取关键词: {keyword}")
            
            # 1. 搜索文献
            async with self.search_fetcher as fetcher:
                search_result = await fetcher.fetch(keyword, max_results)
            
            stats['total_found'] = search_result['total_count']
            pmid_list = search_result['pmid_list']
            
            if not pmid_list:
                self.logger.warning(f"关键词 '{keyword}' 未找到任何文献")
                return stats
            
            # 2. 获取文献详情
            async with self.detail_fetcher as fetcher:
                articles = await fetcher.fetch(pmid_list)
            
            # 2.5 处理缺失 DOI 的文献
            articles = await self._handle_missing_dois(articles)
            
            stats['articles_fetched'] = len(articles)
            
            # 3. 保存到数据库
            if save_to_db:
                saved_count = await self._save_articles(articles)
                stats['articles_saved'] = saved_count
            
            # 4. 获取引用关系
            if fetch_references:
                references_count = await self._fetch_and_save_references(pmid_list)
                stats['references_fetched'] = references_count
            
            # 5. 获取全文
            if fetch_fulltext:
                fulltext_count = await self._fetch_fulltext(articles)
                stats['fulltext_fetched'] = fulltext_count
            
        except Exception as e:
            self.logger.error(f"爬取过程出错: {str(e)}", exc_info=True)
            stats['errors'].append(str(e))
        
        finally:
            # 计算耗时
            stats['duration'] = (datetime.now() - start_time).total_seconds()
            self.logger.info(f"爬取完成，耗时: {stats['duration']:.2f} 秒")
            self.logger.info(f"统计信息: {stats}")
        
        return stats
    
    async def crawl_article_details(
        self,
        pmid_list: List[str],
        save_to_db: bool = True,
        update_existing: bool = False
    ) -> Dict[str, Any]:
        """
        爬取指定 PMID 列表的文献详情
        
        Args:
            pmid_list: PMID 列表
            save_to_db: 是否保存到数据库
            update_existing: 是否更新已存在的文献
        
        Returns:
            爬取结果统计
        """
        stats = {
            'requested': len(pmid_list),
            'fetched': 0,
            'saved': 0,
            'updated': 0,
            'skipped': 0,
            'errors': []
        }
        
        try:
            # 检查已存在的文献
            if not update_existing:
                existing_pmids = await self._get_existing_pmids(pmid_list)
                pmid_list = [p for p in pmid_list if p not in existing_pmids]
                stats['skipped'] = len(existing_pmids)
                
                if not pmid_list:
                    self.logger.info("所有文献已存在，跳过爬取")
                    return stats
            
            # 获取详情
            async with self.detail_fetcher as fetcher:
                articles = await fetcher.fetch(pmid_list)
            
            stats['fetched'] = len(articles)
            
            # 保存到数据库
            if save_to_db:
                if update_existing:
                    saved, updated = await self._save_articles(articles, update_existing=True)
                    stats['saved'] = saved
                    stats['updated'] = updated
                else:
                    stats['saved'] = await self._save_articles(articles)
            
        except Exception as e:
            self.logger.error(f"爬取文献详情出错: {str(e)}", exc_info=True)
            stats['errors'].append(str(e))
        
        return stats
    
    async def crawl_references(
        self,
        doi_list: List[str],
        save_to_db: bool = True,
        crawl_missing: bool = True
    ) -> Dict[str, Any]:
        """
        爬取文献的引用关系
        
        Args:
            doi_list: DOI 列表
            save_to_db: 是否保存到数据库
            crawl_missing: 是否爬取缺失的被引用文献
        
        Returns:
            爬取结果统计
        """
        stats = {
            'requested': len(doi_list),
            'processed': 0,
            'references_found': 0,
            'citations_found': 0,
            'new_articles_crawled': 0,
            'errors': []
        }
        
        try:
            # 获取对应的 PMID
            pmid_list = await self._get_pmids_by_dois(doi_list)
            
            # 获取引用关系
            async with self.references_fetcher as fetcher:
                references_data = await fetcher.fetch(pmid_list)
            
            stats['processed'] = len(references_data)
            
            # 统计引用数
            for pmid, data in references_data.items():
                if 'error' not in data:
                    stats['references_found'] += len(data.get('references', []))
                    stats['citations_found'] += len(data.get('cited_by', []))
            
            # 保存引用关系
            if save_to_db:
                await self._save_references(references_data)
            
            # 爬取缺失的被引用文献
            if crawl_missing:
                missing_pmids = await self._find_missing_referenced_articles(references_data)
                if missing_pmids:
                    crawl_stats = await self.crawl_article_details(missing_pmids)
                    stats['new_articles_crawled'] = crawl_stats['saved']
            
        except Exception as e:
            self.logger.error(f"爬取引用关系出错: {str(e)}", exc_info=True)
            stats['errors'].append(str(e))
        
        return stats
    
    async def crawl_fulltext(
        self,
        pmc_id_list: List[str],
        formats: List[str] = ['xml', 'pdf']
    ) -> Dict[str, Any]:
        """
        爬取文献全文
        
        Args:
            pmc_id_list: PMC ID 列表
            formats: 要获取的格式
        
        Returns:
            爬取结果统计
        """
        stats = {
            'requested': len(pmc_id_list),
            'success': 0,
            'failed': 0,
            'formats': {fmt: 0 for fmt in formats}
        }
        
        async with self.fulltext_fetcher as fetcher:
            for pmc_id in pmc_id_list:
                try:
                    result = await fetcher.fetch(pmc_id, formats)
                    
                    # 统计成功的格式
                    success = False
                    for fmt in formats:
                        if fmt in result.get('formats', {}) and result['formats'][fmt]:
                            stats['formats'][fmt] += 1
                            success = True
                    
                    if success:
                        stats['success'] += 1
                    else:
                        stats['failed'] += 1
                        
                except Exception as e:
                    self.logger.error(f"获取 {pmc_id} 全文失败: {str(e)}")
                    stats['failed'] += 1
        
        return stats
    
    async def update_existing_articles(
        self,
        days_old: int = 30
    ) -> Dict[str, Any]:
        """
        更新已存在的文献信息
        
        Args:
            days_old: 更新多少天前的文献
        
        Returns:
            更新结果统计
        """
        stats = {
            'checked': 0,
            'updated': 0,
            'errors': []
        }
        
        try:
            # 获取需要更新的文献
            old_articles = await self._get_old_articles(days_old)
            pmid_list = [a.pmid for a in old_articles if a.pmid]
            
            stats['checked'] = len(pmid_list)
            
            if pmid_list:
                # 爬取最新信息
                crawl_stats = await self.crawl_article_details(
                    pmid_list,
                    save_to_db=True,
                    update_existing=True
                )
                stats['updated'] = crawl_stats['updated']
            
        except Exception as e:
            self.logger.error(f"更新文献出错: {str(e)}", exc_info=True)
            stats['errors'].append(str(e))
        
        return stats
    
    # 辅助方法
    
    async def _save_articles(
        self,
        articles: List[Dict[str, Any]],
        update_existing: bool = False
    ) -> int:
        """保存文献到数据库"""
        saved_count = 0
        updated_count = 0
        
        with get_db() as db:
            for article_data in articles:
                try:
                    saved = await self.article_processor.process_and_save(
                        article_data,
                        db,
                        update_existing=update_existing
                    )
                    if saved:
                        if update_existing:
                            updated_count += 1
                        else:
                            saved_count += 1
                except Exception as e:
                    self.logger.error(f"保存文献失败: {str(e)}", exc_info=True)
                    continue
            
            db.commit()
        
        if update_existing:
            return saved_count, updated_count
        return saved_count
    
    async def _get_existing_pmids(self, pmid_list: List[str]) -> set:
        """获取已存在的 PMID"""
        with get_db() as db:
            existing = db.query(Article.pmid).filter(
                Article.pmid.in_(pmid_list)
            ).all()
            return {p[0] for p in existing}
    
    async def _get_pmids_by_dois(self, doi_list: List[str]) -> List[str]:
        """根据 DOI 获取 PMID"""
        with get_db() as db:
            articles = db.query(Article.pmid).filter(
                Article.doi.in_(doi_list),
                Article.pmid.isnot(None)
            ).all()
            return [a[0] for a in articles]
    
    async def _save_references(self, references_data: Dict[str, Dict[str, Any]]):
        """保存引用关系"""
        from src.models import ArticleReference
        
        with get_db() as db:
            saved_count = 0
            
            for pmid, data in references_data.items():
                if 'error' in data:
                    continue
                
                try:
                    # 获取引用文献的 DOI
                    citing_article = db.query(Article).filter(Article.pmid == pmid).first()
                    if not citing_article:
                        self.logger.warning(f"未找到 PMID {pmid} 对应的文献，跳过引用关系保存")
                        continue
                    
                    citing_doi = citing_article.doi
                    
                    # 处理该文献引用的文献（参考文献）
                    for i, ref in enumerate(data.get('references', [])):
                        cited_pmid = ref.get('cited_pmid')
                        if not cited_pmid:
                            continue
                        
                        # 查找被引用文献的 DOI
                        cited_article = db.query(Article).filter(Article.pmid == cited_pmid).first()
                        cited_doi = cited_article.doi if cited_article else None
                        
                        # 检查关系是否已存在
                        existing = db.query(ArticleReference).filter(
                            ArticleReference.citing_doi == citing_doi,
                            ArticleReference.cited_pmid == cited_pmid
                        ).first()
                        
                        if not existing:
                            # 创建引用关系
                            reference = ArticleReference(
                                citing_doi=citing_doi,
                                cited_doi=cited_doi,
                                cited_pmid=cited_pmid,
                                reference_order=ref.get('reference_order', i + 1)
                            )
                            db.add(reference)
                            saved_count += 1
                    
                    # 处理引用该文献的文献（被引用）
                    for cite in data.get('cited_by', []):
                        citing_pmid = cite.get('citing_pmid')
                        if not citing_pmid:
                            continue
                        
                        # 查找引用文献的 DOI
                        citing_article_ref = db.query(Article).filter(Article.pmid == citing_pmid).first()
                        
                        if citing_article_ref:
                            # 检查关系是否已存在
                            existing = db.query(ArticleReference).filter(
                                ArticleReference.citing_doi == citing_article_ref.doi,
                                ArticleReference.cited_doi == citing_doi
                            ).first()
                            
                            if not existing:
                                # 创建引用关系（反向）
                                reference = ArticleReference(
                                    citing_doi=citing_article_ref.doi,
                                    cited_doi=citing_doi,
                                    cited_pmid=pmid
                                )
                                db.add(reference)
                                saved_count += 1
                        else:
                            # 如果引用文献不在数据库中，仅保存 PMID 关系
                            existing = db.query(ArticleReference).filter(
                                ArticleReference.citing_doi == None,
                                ArticleReference.cited_doi == citing_doi,
                                ArticleReference.cited_pmid == pmid
                            ).first()
                            
                            if not existing:
                                # 创建仅包含 PMID 的引用关系
                                reference = ArticleReference(
                                    citing_doi=None,  # 引用文献的 DOI 未知
                                    cited_doi=citing_doi,
                                    cited_pmid=pmid,
                                    reference_string=f"PMID:{citing_pmid}"  # 保存原始 PMID 信息
                                )
                                db.add(reference)
                                saved_count += 1
                    
                    # 定期提交以避免内存过载
                    if saved_count % 100 == 0:
                        db.commit()
                        self.logger.info(f"已保存 {saved_count} 条引用关系")
                
                except Exception as e:
                    self.logger.error(f"保存 PMID {pmid} 的引用关系失败: {str(e)}", exc_info=True)
                    db.rollback()
                    continue
            
            # 最终提交
            try:
                db.commit()
                self.logger.info(f"引用关系保存完成，共保存 {saved_count} 条记录")
            except Exception as e:
                self.logger.error(f"提交引用关系失败: {str(e)}", exc_info=True)
                db.rollback()
    
    async def _find_missing_referenced_articles(
        self,
        references_data: Dict[str, Dict[str, Any]]
    ) -> List[str]:
        """查找缺失的被引用文献"""
        all_referenced_pmids = set()
        
        for data in references_data.values():
            if 'error' not in data:
                for ref in data.get('references', []):
                    if ref.get('cited_pmid') and not ref.get('exists_in_db'):
                        all_referenced_pmids.add(ref['cited_pmid'])
                
                for cite in data.get('cited_by', []):
                    if cite.get('citing_pmid') and not cite.get('exists_in_db'):
                        all_referenced_pmids.add(cite['citing_pmid'])
        
        return list(all_referenced_pmids)
    
    async def _fetch_and_save_references(self, pmid_list: List[str]) -> int:
        """获取并保存引用关系"""
        async with self.references_fetcher as fetcher:
            references_data = await fetcher.fetch(pmid_list)
        
        # 保存引用关系
        await self._save_references(references_data)
        
        return len(references_data)
    
    async def _handle_missing_dois(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """处理缺失 DOI 的文献
        
        Args:
            articles: 文献数据列表
            
        Returns:
            处理后的文献列表
        """
        missing_doi_articles = []
        articles_with_doi = []
        
        # 分离有 DOI 和无 DOI 的文献
        for article in articles:
            if article.get('doi'):
                articles_with_doi.append(article)
            else:
                missing_doi_articles.append(article)
        
        if not missing_doi_articles:
            self.logger.info("所有文献都有 DOI")
            return articles
        
        self.logger.warning(f"发现 {len(missing_doi_articles)} 篇文献缺失 DOI，尝试重新获取")
        
        # 对缺失 DOI 的文献再次获取详细信息
        updated_articles = []
        still_missing_doi = []
        
        for article in missing_doi_articles:
            pmid = article.get('pmid')
            if not pmid:
                still_missing_doi.append(article)
                continue
            
            try:
                # 使用 DetailFetcher 单独获取该文献
                self.logger.info(f"重新获取 PMID {pmid} 的详细信息")
                async with self.detail_fetcher as fetcher:
                    result = await fetcher.fetch([pmid])
                
                if result and len(result) > 0:
                    updated_article = result[0]
                    if updated_article.get('doi'):
                        self.logger.info(f"成功获取 PMID {pmid} 的 DOI: {updated_article['doi']}")
                        updated_articles.append(updated_article)
                    else:
                        self.logger.warning(f"PMID {pmid} 仍然没有 DOI")
                        still_missing_doi.append(updated_article)
                else:
                    still_missing_doi.append(article)
            except Exception as e:
                self.logger.error(f"重新获取 PMID {pmid} 失败: {str(e)}")
                still_missing_doi.append(article)
        
        # 将仍然缺失 DOI 的文献记录到 CSV
        if still_missing_doi:
            await self._save_missing_doi_to_csv(still_missing_doi)
        
        # 合并所有有 DOI 的文献
        all_articles = articles_with_doi + updated_articles
        
        self.logger.info(f"最终获得 {len(all_articles)} 篇有 DOI 的文献，{len(still_missing_doi)} 篇无 DOI")
        
        return all_articles
    
    async def _save_missing_doi_to_csv(self, articles: List[Dict[str, Any]]):
        """将缺失 DOI 的文献保存到 CSV 文件
        
        Args:
            articles: 缺失 DOI 的文献列表
        """
        # 创建输出目录
        output_dir = Path("missing_doi_articles")
        output_dir.mkdir(exist_ok=True)
        
        # 生成文件名（包含时间戳）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_file = output_dir / f"missing_doi_{timestamp}.csv"
        
        # 写入 CSV
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'pmid', 'pmc_id', 'title', 'journal', 'authors', 
                'publication_date', 'abstract', 'keywords', 'mesh_terms'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for article in articles:
                # 提取作者列表
                authors = []
                for author in article.get('authors', []):
                    if author.get('collective_name'):
                        authors.append(author['collective_name'])
                    else:
                        name = f"{author.get('fore_name', '')} {author.get('last_name', '')}".strip()
                        if name:
                            authors.append(name)
                
                # 提取关键词
                keywords = [kw.get('keyword', '') for kw in article.get('keywords', [])]
                
                # 提取 MeSH 术语
                mesh_terms = [mt.get('descriptor_name', '') for mt in article.get('mesh_terms', [])]
                
                # 写入行
                writer.writerow({
                    'pmid': article.get('pmid', ''),
                    'pmc_id': article.get('other_ids', {}).get('pmc', ''),
                    'title': article.get('title', ''),
                    'journal': article.get('journal', {}).get('title', ''),
                    'authors': '; '.join(authors),
                    'publication_date': str(article.get('journal', {}).get('pub_date', '')),
                    'abstract': article.get('abstract', ''),
                    'keywords': '; '.join(keywords),
                    'mesh_terms': '; '.join(mesh_terms)
                })
        
        self.logger.info(f"已将 {len(articles)} 篇缺失 DOI 的文献保存到: {csv_file}")
    
    async def _fetch_fulltext(self, articles: List[Dict[str, Any]]) -> int:
        """获取全文"""
        count = 0
        pmc_ids = []
        
        for article in articles:
            pmc_id = article.get('other_ids', {}).get('pmc')
            if pmc_id:
                pmc_ids.append(pmc_id)
        
        if pmc_ids:
            stats = await self.crawl_fulltext(pmc_ids)
            count = stats['success']
        
        return count
    
    async def _get_old_articles(self, days_old: int) -> List[Article]:
        """获取需要更新的旧文献"""
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days_old)
        
        with get_db() as db:
            return db.query(Article).filter(
                Article.last_crawled_at < cutoff_date
            ).limit(1000).all()
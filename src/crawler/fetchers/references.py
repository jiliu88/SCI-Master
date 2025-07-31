from typing import List, Dict, Any, Optional, Set
import asyncio

from .base import BaseFetcher
from src.crawler.utils import retry_with_backoff
from src.db.session import get_db
from src.models import Article


class ReferencesFetcher(BaseFetcher):
    """引用关系获取器，获取文献的引用和被引用关系"""
    
    async def fetch(
        self,
        pmid_list: List[str],
        fetch_types: List[str] = ['refs', 'citedin']
    ) -> Dict[str, Dict[str, Any]]:
        """
        获取文献的引用关系
        
        Args:
            pmid_list: PMID 列表
            fetch_types: 要获取的类型列表
                - 'refs': 获取该文献引用的文献
                - 'citedin': 获取引用该文献的文献
        
        Returns:
            引用关系字典，键为 PMID
        """
        if not pmid_list:
            return {}
        
        self.log_info(f"开始获取 {len(pmid_list)} 篇文献的引用关系")
        
        # 并发获取所有文献的引用关系
        tasks = []
        for pmid in pmid_list:
            task = self._fetch_single_references(pmid, fetch_types)
            tasks.append(task)
        
        # 执行所有任务
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 整理结果
        references_dict = {}
        for i, result in enumerate(results):
            pmid = pmid_list[i]
            if isinstance(result, Exception):
                self.log_error(f"PMID {pmid} 引用关系获取失败", result)
                references_dict[pmid] = {'error': str(result)}
            else:
                references_dict[pmid] = result
        
        self.log_info(f"成功获取 {len([r for r in references_dict.values() if 'error' not in r])} 篇文献的引用关系")
        
        return references_dict
    
    @retry_with_backoff(max_retries=3)
    async def _fetch_single_references(
        self,
        pmid: str,
        fetch_types: List[str]
    ) -> Dict[str, Any]:
        """
        获取单篇文献的引用关系
        
        Args:
            pmid: PMID
            fetch_types: 要获取的类型列表
        
        Returns:
            引用关系数据
        """
        result = {
            'pmid': pmid,
            'references': [],  # 该文献引用的文献
            'cited_by': []     # 引用该文献的文献
        }
        
        # 获取引用的文献（该文献的参考文献）
        if 'refs' in fetch_types:
            refs = await self._fetch_references(pmid)
            result['references'] = refs
        
        # 获取被引用的文献（引用该文献的文献）
        if 'citedin' in fetch_types:
            cited_by = await self._fetch_cited_by(pmid)
            result['cited_by'] = cited_by
        
        return result
    
    async def _fetch_references(self, pmid: str) -> List[Dict[str, Any]]:
        """
        获取文献引用的参考文献
        
        Args:
            pmid: PMID
        
        Returns:
            参考文献列表
        """
        try:
            # 等待速率限制
            await self.entrez_client.rate_limiter.acquire()
            
            # 使用 elink 获取引用关系
            result = self.entrez_client.elink(
                id=pmid,
                linkname="pubmed_pubmed_refs"
            )
            
            references = []
            
            # 解析结果
            if result and len(result) > 0:
                link_set_db_list = result[0].get('LinkSetDb', [])
                
                for link_set_db in link_set_db_list:
                    if link_set_db.get('LinkName') == 'pubmed_pubmed_refs':
                        links = link_set_db.get('Link', [])
                        
                        for i, link in enumerate(links):
                            ref_pmid = link.get('Id', '')
                            if ref_pmid:
                                ref_info = {
                                    'cited_pmid': ref_pmid,
                                    'reference_order': i + 1
                                }
                                
                                # 检查数据库中是否存在该文献
                                existing_info = await self._check_article_exists(ref_pmid)
                                if existing_info:
                                    ref_info.update(existing_info)
                                
                                references.append(ref_info)
                        
                        break
            
            self.log_info(f"PMID {pmid} 找到 {len(references)} 篇参考文献")
            return references
            
        except Exception as e:
            self.log_error(f"获取 PMID {pmid} 的参考文献失败", e)
            return []
    
    async def _fetch_cited_by(self, pmid: str) -> List[Dict[str, Any]]:
        """
        获取引用该文献的文献
        
        Args:
            pmid: PMID
        
        Returns:
            引用文献列表
        """
        try:
            # 等待速率限制
            await self.entrez_client.rate_limiter.acquire()
            
            # 使用 elink 获取被引用关系
            result = self.entrez_client.elink(
                id=pmid,
                linkname="pubmed_pubmed_citedin"
            )
            
            cited_by = []
            
            # 解析结果
            if result and len(result) > 0:
                link_set_db_list = result[0].get('LinkSetDb', [])
                
                for link_set_db in link_set_db_list:
                    if link_set_db.get('LinkName') == 'pubmed_pubmed_citedin':
                        links = link_set_db.get('Link', [])
                        
                        for link in links:
                            citing_pmid = link.get('Id', '')
                            if citing_pmid:
                                citing_info = {
                                    'citing_pmid': citing_pmid
                                }
                                
                                # 检查数据库中是否存在该文献
                                existing_info = await self._check_article_exists(citing_pmid)
                                if existing_info:
                                    citing_info.update(existing_info)
                                
                                cited_by.append(citing_info)
                        
                        break
            
            self.log_info(f"PMID {pmid} 被 {len(cited_by)} 篇文献引用")
            return cited_by
            
        except Exception as e:
            self.log_error(f"获取引用 PMID {pmid} 的文献失败", e)
            return []
    
    async def _check_article_exists(self, pmid: str) -> Optional[Dict[str, str]]:
        """
        检查文献是否存在于数据库中
        
        Args:
            pmid: PMID
        
        Returns:
            如果存在，返回文献的 DOI 和 PMC_ID；否则返回 None
        """
        try:
            with get_db() as db:
                article = db.query(Article).filter(Article.pmid == pmid).first()
                if article:
                    return {
                        'doi': article.doi,
                        'pmc_id': article.pmc_id,
                        'exists_in_db': True
                    }
                else:
                    return {
                        'exists_in_db': False
                    }
        except Exception as e:
            self.log_error(f"检查 PMID {pmid} 是否存在时出错", e)
            return None
    
    async def fetch_citation_count(self, pmid_list: List[str]) -> Dict[str, int]:
        """
        获取文献的被引用次数
        
        Args:
            pmid_list: PMID 列表
        
        Returns:
            被引用次数字典，键为 PMID
        """
        citation_counts = {}
        
        # 并发获取所有文献的被引用数
        tasks = []
        for pmid in pmid_list:
            task = self._get_citation_count(pmid)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            pmid = pmid_list[i]
            if isinstance(result, Exception):
                self.log_error(f"PMID {pmid} 引用次数获取失败", result)
                citation_counts[pmid] = 0
            else:
                citation_counts[pmid] = result
        
        return citation_counts
    
    async def _get_citation_count(self, pmid: str) -> int:
        """
        获取单篇文献的被引用次数
        
        Args:
            pmid: PMID
        
        Returns:
            被引用次数
        """
        try:
            cited_by = await self._fetch_cited_by(pmid)
            return len(cited_by)
        except Exception as e:
            self.log_error(f"获取 PMID {pmid} 被引用次数失败", e)
            return 0
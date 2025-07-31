from typing import List, Optional, Dict, Any
import asyncio

from .base import BaseFetcher
from src.crawler.utils import retry_with_backoff


class SearchFetcher(BaseFetcher):
    """搜索获取器，通过关键词搜索文献"""
    
    async def fetch(
        self, 
        keyword: str, 
        max_results: Optional[int] = None,
        batch_size: int = 100
    ) -> Dict[str, Any]:
        """
        通过关键词搜索文献
        
        Args:
            keyword: 搜索关键词
            max_results: 最大结果数，None 表示获取所有结果
            batch_size: 每批获取的数量
        
        Returns:
            包含搜索结果的字典
        """
        self.log_info(f"开始搜索关键词: {keyword}")
        
        # 首次搜索，获取总数
        initial_result = await self._search_batch(keyword, retmax=1, retstart=0)
        total_count = int(initial_result.get('Count', 0))
        
        if total_count == 0:
            self.log_warning(f"关键词 '{keyword}' 没有搜索到结果")
            return {
                'keyword': keyword,
                'total_count': 0,
                'pmid_list': [],
                'search_details': initial_result
            }
        
        # 确定实际要获取的数量
        actual_max = min(total_count, max_results) if max_results else total_count
        self.log_info(f"找到 {total_count} 篇文献，将获取 {actual_max} 篇")
        
        # 分批获取所有 PMID
        all_pmids = []
        tasks = []
        
        for start in range(0, actual_max, batch_size):
            end = min(start + batch_size, actual_max)
            batch_retmax = end - start
            
            # 创建异步任务
            task = self._search_batch(keyword, retmax=batch_retmax, retstart=start)
            tasks.append(task)
        
        # 并发执行所有搜索任务
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.log_error(f"批次 {i} 搜索失败", result)
                continue
            
            if 'IdList' in result:
                all_pmids.extend(result['IdList'])
        
        self.log_info(f"成功获取 {len(all_pmids)} 个 PMID")
        
        return {
            'keyword': keyword,
            'total_count': total_count,
            'retrieved_count': len(all_pmids),
            'pmid_list': all_pmids,
            'search_details': {
                'query_translation': initial_result.get('QueryTranslation', ''),
                'translation_set': initial_result.get('TranslationSet', [])
            }
        }
    
    @retry_with_backoff(max_retries=3)
    async def _search_batch(self, keyword: str, retmax: int, retstart: int) -> dict:
        """
        搜索单个批次
        
        Args:
            keyword: 搜索关键词
            retmax: 返回的最大结果数
            retstart: 起始位置
        
        Returns:
            搜索结果字典
        """
        # 等待速率限制
        await self.entrez_client.rate_limiter.acquire()
        
        # 执行搜索
        result = self.entrez_client.search(
            term=keyword,
            retmax=retmax,
            retstart=retstart,
            sort='relevance'  # 按相关性排序
        )
        
        self.log_info(f"批次搜索完成: retstart={retstart}, retmax={retmax}, 获取 {len(result.get('IdList', []))} 个结果")
        
        return result
    
    async def search_with_filters(
        self,
        keyword: str,
        filters: Optional[Dict[str, Any]] = None,
        max_results: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        带过滤条件的搜索
        
        Args:
            keyword: 搜索关键词
            filters: 过滤条件，如日期范围、文献类型等
            max_results: 最大结果数
        
        Returns:
            搜索结果
        """
        # 构建查询字符串
        query_parts = [keyword]
        
        if filters:
            # 日期过滤
            if 'date_from' in filters and 'date_to' in filters:
                date_filter = f"{filters['date_from']}:{filters['date_to']}[dp]"
                query_parts.append(date_filter)
            
            # 文献类型过滤
            if 'publication_types' in filters:
                pub_types = filters['publication_types']
                if isinstance(pub_types, list):
                    pub_filter = ' OR '.join([f'"{pt}"[pt]' for pt in pub_types])
                    query_parts.append(f"({pub_filter})")
                else:
                    query_parts.append(f'"{pub_types}"[pt]')
            
            # 语言过滤
            if 'languages' in filters:
                languages = filters['languages']
                if isinstance(languages, list):
                    lang_filter = ' OR '.join([f'"{lang}"[la]' for lang in languages])
                    query_parts.append(f"({lang_filter})")
                else:
                    query_parts.append(f'"{languages}"[la]')
        
        # 构建最终查询
        final_query = ' AND '.join(query_parts)
        
        self.log_info(f"使用过滤条件搜索: {final_query}")
        
        # 执行搜索
        return await self.fetch(final_query, max_results)
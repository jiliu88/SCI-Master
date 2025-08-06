from typing import List, Dict, Any, Optional
import asyncio
from datetime import datetime

from .base import BaseFetcher
from src.crawler.utils import retry_with_backoff, extract_doi, clean_text, parse_date, safe_get, safe_get_value


class DetailFetcher(BaseFetcher):
    """详情获取器，通过 PMID 获取文献详细信息"""
    
    async def fetch(
        self,
        pmid_list: List[str],
        batch_size: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取文献详细信息
        
        Args:
            pmid_list: PMID 列表
            batch_size: 每批获取的数量
        
        Returns:
            文献详情列表
        """
        if not pmid_list:
            return []
        
        self.log_info(f"开始获取 {len(pmid_list)} 篇文献的详细信息")
        
        # 分批获取
        all_articles = []
        tasks = []
        
        for i in range(0, len(pmid_list), batch_size):
            batch = pmid_list[i:i + batch_size]
            task = self._fetch_batch(batch)
            tasks.append(task)
        
        # 并发执行所有任务
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.log_error(f"批次 {i} 获取失败", result)
                continue
            
            all_articles.extend(result)
        
        self.log_info(f"成功获取 {len(all_articles)} 篇文献的详细信息")
        
        return all_articles
    
    @retry_with_backoff(max_retries=3)
    async def _fetch_batch(self, pmid_batch: List[str]) -> List[Dict[str, Any]]:
        """
        获取单个批次的文献详情
        
        Args:
            pmid_batch: PMID 批次列表
        
        Returns:
            文献详情列表
        """
        # 等待速率限制
        await self.entrez_client.rate_limiter.acquire()
        
        # 获取详情
        result = self.entrez_client.fetch(pmid_batch, rettype="abstract", retmode="xml")
        
        # 解析结果
        articles = []
        if 'PubmedArticle' in result:
            for article_data in result['PubmedArticle']:
                parsed_article = self._parse_article(article_data)
                if parsed_article:
                    articles.append(parsed_article)
        
        self.log_info(f"批次获取完成: 请求 {len(pmid_batch)} 篇，成功解析 {len(articles)} 篇")
        
        return articles
    
    def _parse_article(self, article_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        解析单篇文献数据
        
        Args:
            article_data: 原始文献数据
        
        Returns:
            解析后的文献数据
        """
        try:
            medline_citation = article_data.get('MedlineCitation', {})
            article = medline_citation.get('Article', {})
            
            # 基本信息
            pmid = str(medline_citation.get('PMID', ''))
            if not pmid:
                self.log_warning("文献缺少 PMID，跳过")
                return None
            
            # 标题
            title = clean_text(article.get('ArticleTitle', ''))
            if not title:
                self.log_warning(f"PMID {pmid} 缺少标题，跳过")
                return None
            
            # 摘要
            abstract_text = self._extract_abstract(article.get('Abstract', {}))
            
            # 其他 ID（需要先提取，因为 DOI 可能在这里）
            other_ids = self._extract_other_ids(article_data)
            
            # DOI - 优先从 ELocationID 获取，如果没有则从 other_ids 获取
            doi = extract_doi(article.get('ELocationID', []))
            if not doi and 'doi' in other_ids:
                doi = other_ids['doi']
            
            # 期刊信息
            journal_info = self._extract_journal_info(article.get('Journal', {}))
            
            # 作者信息
            authors = self._extract_authors(article.get('AuthorList', []))
            
            # 关键词
            keywords = self._extract_keywords(medline_citation.get('KeywordList', []))
            
            # MeSH 术语
            mesh_terms = self._extract_mesh_terms(medline_citation.get('MeshHeadingList', []))
            
            # 化学物质
            chemicals = self._extract_chemicals(medline_citation.get('ChemicalList', []))
            
            # 文献类型
            publication_types = self._extract_publication_types(article.get('PublicationTypeList', []))
            
            # 基金信息
            grants = self._extract_grants(article.get('GrantList', []))
            
            # 日期信息
            dates = self._extract_dates(medline_citation)
            
            # 分页信息
            pagination = article.get('Pagination', {}).get('MedlinePgn', '')
            
            # 语言
            language = article.get('Language', [''])[0] if article.get('Language') else 'eng'
            
            # 版权和利益冲突
            copyright_info = clean_text(article.get('CopyrightInformation', ''))
            coi_statement = clean_text(medline_citation.get('CoiStatement', ''))
            
            return {
                'pmid': pmid,
                'doi': doi,
                'title': title,
                'abstract': abstract_text,
                'journal': journal_info,
                'authors': authors,
                'keywords': keywords,
                'mesh_terms': mesh_terms,
                'chemicals': chemicals,
                'publication_types': publication_types,
                'grants': grants,
                'other_ids': other_ids,
                'dates': dates,
                'pagination': pagination,
                'language': language,
                'copyright_info': copyright_info,
                'coi_statement': coi_statement,
                'raw_data': article_data  # 保留原始数据以备后用
            }
            
        except Exception as e:
            self.log_error(f"解析文献数据失败", e)
            return None
    
    def _extract_abstract(self, abstract_data: Dict[str, Any]) -> Optional[str]:
        """提取摘要文本"""
        if not abstract_data:
            return None
        
        abstract_texts = abstract_data.get('AbstractText', [])
        if not abstract_texts:
            return None
        
        # 处理结构化摘要
        if isinstance(abstract_texts, list):
            parts = []
            for text in abstract_texts:
                if hasattr(text, 'attributes') and 'Label' in text.attributes:
                    label = text.attributes['Label']
                    content = str(text)
                    parts.append(f"{label}: {content}")
                else:
                    parts.append(str(text))
            return clean_text(' '.join(parts))
        else:
            return clean_text(str(abstract_texts))
    
    def _extract_journal_info(self, journal_data: Dict[str, Any]) -> Dict[str, Any]:
        """提取期刊信息"""
        journal_issue = journal_data.get('JournalIssue', {})
        pub_date = journal_issue.get('PubDate', {})
        
        # 提取发表日期
        year = pub_date.get('Year', '')
        month = pub_date.get('Month', '')
        day = pub_date.get('Day', '')
        
        # 处理 ISSN
        issn = ''
        issn_data = journal_data.get('ISSN')
        if issn_data:
            if hasattr(issn_data, 'get'):
                issn = issn_data.get('value', '')
            else:
                issn = str(issn_data)
        
        return {
            'title': journal_data.get('Title', ''),
            'iso_abbreviation': journal_data.get('ISOAbbreviation', ''),
            'issn': issn,
            'volume': journal_issue.get('Volume', ''),
            'issue': journal_issue.get('Issue', ''),
            'pub_date': {
                'year': year,
                'month': month,
                'day': day
            }
        }
    
    def _extract_authors(self, author_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """提取作者信息"""
        authors = []
        
        for i, author in enumerate(author_list):
            author_info = {
                'order': i + 1,
                'last_name': author.get('LastName', ''),
                'fore_name': author.get('ForeName', ''),
                'initials': author.get('Initials', ''),
                'collective_name': author.get('CollectiveName', ''),
                'affiliations': []
            }
            
            # 提取作者机构信息
            affiliation_info = author.get('AffiliationInfo', [])
            for aff in affiliation_info:
                if 'Affiliation' in aff:
                    author_info['affiliations'].append(aff['Affiliation'])
            
            # 提取 ORCID
            if 'Identifier' in author:
                identifiers = author.get('Identifier', [])
                if not isinstance(identifiers, list):
                    identifiers = [identifiers]
                for identifier in identifiers:
                    if safe_get(identifier, 'Source') == 'ORCID':
                        author_info['orcid'] = safe_get_value(identifier)
            
            # 检查是否为通讯作者
            if author.get('attributes', {}).get('EqualContrib') == 'Y':
                author_info['equal_contrib'] = True
            
            authors.append(author_info)
        
        return authors
    
    def _extract_keywords(self, keyword_lists: List[Any]) -> List[Dict[str, str]]:
        """提取关键词"""
        keywords = []
        
        for keyword_list in keyword_lists:
            owner = safe_get(safe_get(keyword_list, 'attributes', {}), 'Owner', 'NLM')
            for keyword in keyword_list:
                if isinstance(keyword, str):
                    keywords.append({
                        'keyword': keyword,
                        'type': owner
                    })
        
        return keywords
    
    def _extract_mesh_terms(self, mesh_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """提取 MeSH 术语"""
        mesh_terms = []
        
        for mesh_heading in mesh_list:
            descriptor = mesh_heading.get('DescriptorName', {})
            if not descriptor:
                continue
            
            term_info = {
                'descriptor_name': safe_get_value(descriptor),
                'descriptor_ui': safe_get(safe_get(descriptor, 'attributes', {}), 'UI', ''),
                'is_major_topic': safe_get(safe_get(descriptor, 'attributes', {}), 'MajorTopicYN', 'N') == 'Y',
                'qualifiers': []
            }
            
            # 提取限定词
            qualifiers = mesh_heading.get('QualifierName', [])
            if not isinstance(qualifiers, list):
                qualifiers = [qualifiers]
            
            for qualifier in qualifiers:
                if qualifier:
                    term_info['qualifiers'].append({
                        'name': safe_get_value(qualifier),
                        'ui': safe_get(safe_get(qualifier, 'attributes', {}), 'UI', ''),
                        'is_major_topic': safe_get(safe_get(qualifier, 'attributes', {}), 'MajorTopicYN', 'N') == 'Y'
                    })
            
            mesh_terms.append(term_info)
        
        return mesh_terms
    
    def _extract_chemicals(self, chemical_list: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """提取化学物质"""
        chemicals = []
        
        for chemical in chemical_list:
            if 'NameOfSubstance' in chemical:
                chemicals.append({
                    'name': safe_get_value(chemical.get('NameOfSubstance', {})),
                    'registry_number': chemical.get('RegistryNumber', '')
                })
        
        return chemicals
    
    def _extract_publication_types(self, pub_type_list: List[Any]) -> List[str]:
        """提取文献类型"""
        pub_types = []
        
        for pub_type in pub_type_list:
            if isinstance(pub_type, str):
                pub_types.append(pub_type)
            elif hasattr(pub_type, 'get'):
                pub_types.append(pub_type.get('value', ''))
        
        return pub_types
    
    def _extract_grants(self, grant_list: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """提取基金信息"""
        grants = []
        
        for grant in grant_list:
            if grant:
                grants.append({
                    'grant_id': grant.get('GrantID', ''),
                    'acronym': grant.get('Acronym', ''),
                    'agency': grant.get('Agency', ''),
                    'country': grant.get('Country', '')
                })
        
        return grants
    
    def _extract_other_ids(self, article_data: Dict[str, Any]) -> Dict[str, str]:
        """提取其他 ID"""
        other_ids = {}
        
        # PMC ID
        pubmed_data = article_data.get('PubmedData', {})
        article_id_list = pubmed_data.get('ArticleIdList', [])
        
        for article_id in article_id_list:
            id_type = safe_get(safe_get(article_id, 'attributes', {}), 'IdType', '')
            if id_type:
                other_ids[id_type] = str(article_id)
        
        # 其他 ID
        medline_citation = article_data.get('MedlineCitation', {})
        other_id_list = medline_citation.get('OtherID', [])
        
        for other_id in other_id_list:
            if hasattr(other_id, 'attributes'):
                source = safe_get(other_id.attributes, 'Source')
                if source:
                    other_ids[source] = str(other_id)
        
        return other_ids
    
    def _extract_dates(self, medline_citation: Dict[str, Any]) -> Dict[str, Any]:
        """提取日期信息"""
        dates = {}
        
        # 各种日期
        if 'DateCompleted' in medline_citation:
            dates['completed'] = self._format_date(medline_citation['DateCompleted'])
        
        if 'DateRevised' in medline_citation:
            dates['revised'] = self._format_date(medline_citation['DateRevised'])
        
        # 文章日期
        article = medline_citation.get('Article', {})
        article_dates = article.get('ArticleDate', [])
        
        for date in article_dates:
            if safe_get(safe_get(date, 'attributes', {}), 'DateType') == 'Electronic':
                dates['electronic'] = self._format_date(date)
        
        return dates
    
    def _format_date(self, date_dict: Dict[str, str]) -> Optional[str]:
        """格式化日期"""
        if not date_dict:
            return None
        
        year = date_dict.get('Year', '')
        month = date_dict.get('Month', '').zfill(2)
        day = date_dict.get('Day', '').zfill(2)
        
        if year:
            if month and day:
                return f"{year}-{month}-{day}"
            elif month:
                return f"{year}-{month}"
            else:
                return year
        
        return None
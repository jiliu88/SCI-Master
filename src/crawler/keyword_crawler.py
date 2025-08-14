#!/usr/bin/env python3
"""
关键词批量爬虫脚本

支持功能：
1. 单个或批量关键词搜索
2. 高级搜索条件（日期范围、文献类型、语言等）
3. 进度跟踪和断点续爬
4. 详细的统计报告
5. 导出搜索结果
"""

import asyncio
import argparse
import json
import csv
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from pathlib import Path
import logging
import sys

from src.crawler.pubmed_crawler import PubMedCrawler
from src.config.settings import settings
from src.db.session import get_db
from src.models import Article

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'keyword_crawler_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class KeywordCrawler:
    """关键词批量爬虫"""
    
    def __init__(self, output_dir: str = "crawl_results"):
        """初始化爬虫"""
        self.crawler = PubMedCrawler()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.progress_file = self.output_dir / "progress.json"
        self.stats_file = self.output_dir / "stats.json"
        self.logger = logger
        
    async def crawl_keywords(
        self,
        keywords: List[str],
        filters: Optional[Dict[str, Any]] = None,
        max_results_per_keyword: Optional[int] = None,
        save_to_db: bool = True,
        fetch_references: bool = False,
        fetch_fulltext: bool = False,
        resume: bool = True,
        force: bool = False  # 强制重新爬取
    ) -> Dict[str, Any]:
        """
        批量爬取关键词
        
        Args:
            keywords: 关键词列表
            filters: 搜索过滤条件
            max_results_per_keyword: 每个关键词的最大结果数
            save_to_db: 是否保存到数据库
            fetch_references: 是否获取引用关系
            fetch_fulltext: 是否获取全文
            resume: 是否从上次中断处继续
        
        Returns:
            爬取统计结果
        """
        start_time = datetime.now()
        
        # 加载进度
        if force:
            # 强制重新爬取，清空进度
            self.logger.info("强制重新爬取模式，忽略之前的进度")
            progress = {}
            completed_keywords = set()
            pending_keywords = keywords
        else:
            progress = self._load_progress() if resume else {}
            completed_keywords = set(progress.get('completed', []))
            
            # 过滤已完成的关键词
            pending_keywords = [k for k in keywords if k not in completed_keywords]
            
            if not pending_keywords:
                self.logger.info("所有关键词已完成爬取（使用 --force 强制重新爬取）")
                return self._load_stats()
        
        self.logger.info(f"待爬取关键词数: {len(pending_keywords)}")
        
        # 初始化统计
        overall_stats = {
            'start_time': start_time.isoformat(),
            'total_keywords': len(keywords),
            'completed_keywords': len(completed_keywords),
            'total_articles': progress.get('total_articles', 0),
            'total_saved': progress.get('total_saved', 0),
            'total_references': progress.get('total_references', 0),
            'total_fulltext': progress.get('total_fulltext', 0),
            'keyword_stats': progress.get('keyword_stats', {}),
            'errors': progress.get('errors', [])
        }
        
        # 批量爬取
        for i, keyword in enumerate(pending_keywords, 1):
            try:
                self.logger.info(f"\n{'='*50}")
                self.logger.info(f"正在爬取关键词 {i}/{len(pending_keywords)}: {keyword}")
                self.logger.info(f"{'='*50}")
                
                # 构建搜索查询
                search_query = self._build_search_query(keyword, filters)
                
                # 执行爬取
                stats = await self.crawler.crawl_by_keyword(
                    keyword=search_query,
                    max_results=max_results_per_keyword,
                    save_to_db=save_to_db,
                    fetch_references=fetch_references,
                    fetch_fulltext=fetch_fulltext
                )
                
                # 更新统计
                overall_stats['keyword_stats'][keyword] = stats
                overall_stats['total_articles'] += stats.get('articles_fetched', 0)
                overall_stats['total_saved'] += stats.get('articles_saved', 0)
                overall_stats['total_references'] += stats.get('references_fetched', 0)
                overall_stats['total_fulltext'] += stats.get('fulltext_fetched', 0)
                overall_stats['completed_keywords'] += 1
                
                # 记录已完成的关键词
                completed_keywords.add(keyword)
                
                # 保存进度
                self._save_progress({
                    'completed': list(completed_keywords),
                    'total_articles': overall_stats['total_articles'],
                    'total_saved': overall_stats['total_saved'],
                    'total_references': overall_stats['total_references'],
                    'total_fulltext': overall_stats['total_fulltext'],
                    'keyword_stats': overall_stats['keyword_stats'],
                    'errors': overall_stats['errors']
                })
                
                # 生成关键词报告
                await self._generate_keyword_report(keyword, stats)
                
            except Exception as e:
                error_msg = f"爬取关键词 '{keyword}' 失败: {str(e)}"
                self.logger.error(error_msg, exc_info=True)
                overall_stats['errors'].append({
                    'keyword': keyword,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                })
        
        # 计算总耗时
        overall_stats['end_time'] = datetime.now().isoformat()
        overall_stats['duration'] = (datetime.now() - start_time).total_seconds()
        
        # 保存最终统计
        self._save_stats(overall_stats)
        
        # 生成总报告
        await self._generate_final_report(overall_stats)
        
        return overall_stats
    
    def _build_search_query(self, keyword: str, filters: Optional[Dict[str, Any]]) -> str:
        """构建搜索查询字符串"""
        query_parts = [keyword]
        
        if filters:
            # 日期过滤
            if 'date_from' in filters and 'date_to' in filters:
                date_filter = f"{filters['date_from']}:{filters['date_to']}[dp]"
                query_parts.append(date_filter)
            elif 'date_from' in filters:
                date_filter = f"{filters['date_from']}:{date.today().strftime('%Y/%m/%d')}[dp]"
                query_parts.append(date_filter)
            elif 'date_to' in filters:
                date_filter = f"1900/01/01:{filters['date_to']}[dp]"
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
            
            # 期刊过滤
            if 'journals' in filters:
                journals = filters['journals']
                if isinstance(journals, list):
                    journal_filter = ' OR '.join([f'"{j}"[ta]' for j in journals])
                    query_parts.append(f"({journal_filter})")
                else:
                    query_parts.append(f'"{journals}"[ta]')
            
            # 作者过滤
            if 'authors' in filters:
                authors = filters['authors']
                if isinstance(authors, list):
                    author_filter = ' OR '.join([f'"{a}"[au]' for a in authors])
                    query_parts.append(f"({author_filter})")
                else:
                    query_parts.append(f'"{authors}"[au]')
            
            # MeSH 术语过滤
            if 'mesh_terms' in filters:
                mesh_terms = filters['mesh_terms']
                if isinstance(mesh_terms, list):
                    mesh_filter = ' OR '.join([f'"{m}"[mh]' for m in mesh_terms])
                    query_parts.append(f"({mesh_filter})")
                else:
                    query_parts.append(f'"{mesh_terms}"[mh]')
        
        return ' AND '.join(query_parts)
    
    async def _generate_keyword_report(self, keyword: str, stats: Dict[str, Any]):
        """生成单个关键词的报告"""
        report_file = self.output_dir / f"report_{self._sanitize_filename(keyword)}.json"
        
        report = {
            'keyword': keyword,
            'timestamp': datetime.now().isoformat(),
            'stats': stats,
            'summary': {
                'total_found': stats.get('total_found', 0),
                'articles_fetched': stats.get('articles_fetched', 0),
                'articles_saved': stats.get('articles_saved', 0),
                'success_rate': (
                    stats.get('articles_saved', 0) / stats.get('articles_fetched', 1) * 100
                    if stats.get('articles_fetched', 0) > 0 else 0
                ),
                'duration_seconds': stats.get('duration', 0)
            }
        }
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"关键词报告已保存: {report_file}")
    
    async def _generate_final_report(self, overall_stats: Dict[str, Any]):
        """生成最终汇总报告"""
        # JSON 报告
        report_file = self.output_dir / "final_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(overall_stats, f, ensure_ascii=False, indent=2)
        
        # CSV 报告
        csv_file = self.output_dir / "summary.csv"
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                '关键词', '找到文献数', '获取文献数', '保存文献数', 
                '引用关系数', '全文数', '耗时(秒)', '错误'
            ])
            
            for keyword, stats in overall_stats['keyword_stats'].items():
                writer.writerow([
                    keyword,
                    stats.get('total_found', 0),
                    stats.get('articles_fetched', 0),
                    stats.get('articles_saved', 0),
                    stats.get('references_fetched', 0),
                    stats.get('fulltext_fetched', 0),
                    f"{stats.get('duration', 0):.2f}",
                    '是' if stats.get('errors') else '否'
                ])
        
        # 文本摘要
        summary_file = self.output_dir / "summary.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("PubMed 关键词爬取汇总报告\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"开始时间: {overall_stats['start_time']}\n")
            f.write(f"结束时间: {overall_stats.get('end_time', 'N/A')}\n")
            f.write(f"总耗时: {overall_stats.get('duration', 0):.2f} 秒\n\n")
            f.write(f"关键词总数: {overall_stats['total_keywords']}\n")
            f.write(f"完成关键词数: {overall_stats['completed_keywords']}\n")
            f.write(f"文献总数: {overall_stats['total_articles']}\n")
            f.write(f"保存文献数: {overall_stats['total_saved']}\n")
            f.write(f"引用关系数: {overall_stats['total_references']}\n")
            f.write(f"全文数: {overall_stats['total_fulltext']}\n")
            f.write(f"错误数: {len(overall_stats['errors'])}\n")
        
        self.logger.info(f"最终报告已生成: {self.output_dir}")
    
    def _load_progress(self) -> Dict[str, Any]:
        """加载进度"""
        if self.progress_file.exists():
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _save_progress(self, progress: Dict[str, Any]):
        """保存进度"""
        with open(self.progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)
    
    def _load_stats(self) -> Dict[str, Any]:
        """加载统计"""
        if self.stats_file.exists():
            with open(self.stats_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _save_stats(self, stats: Dict[str, Any]):
        """保存统计"""
        with open(self.stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """清理文件名中的非法字符"""
        import re
        # 替换非法字符
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # 限制长度
        if len(filename) > 100:
            filename = filename[:100]
        return filename


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='PubMed 关键词批量爬虫')
    
    # 基本参数
    parser.add_argument(
        'keywords',
        nargs='*',
        help='要搜索的关键词（可以是多个）'
    )
    parser.add_argument(
        '-f', '--file',
        help='从文件读取关键词列表（每行一个关键词）'
    )
    parser.add_argument(
        '-o', '--output',
        default='crawl_results',
        help='输出目录（默认: crawl_results）'
    )
    parser.add_argument(
        '-m', '--max-results',
        type=int,
        help='每个关键词的最大结果数'
    )
    
    # 搜索过滤器
    parser.add_argument(
        '--date-from',
        help='开始日期（格式: YYYY/MM/DD）'
    )
    parser.add_argument(
        '--date-to',
        help='结束日期（格式: YYYY/MM/DD）'
    )
    parser.add_argument(
        '--languages',
        nargs='+',
        help='语言过滤（如: eng chi）'
    )
    parser.add_argument(
        '--pub-types',
        nargs='+',
        help='文献类型过滤（如: Review "Clinical Trial"）'
    )
    parser.add_argument(
        '--journals',
        nargs='+',
        help='期刊过滤'
    )
    parser.add_argument(
        '--authors',
        nargs='+',
        help='作者过滤'
    )
    parser.add_argument(
        '--mesh-terms',
        nargs='+',
        help='MeSH 术语过滤'
    )
    
    # 爬取选项
    parser.add_argument(
        '--no-save',
        action='store_true',
        help='不保存到数据库'
    )
    parser.add_argument(
        '--fetch-references',
        action='store_true',
        help='获取引用关系'
    )
    parser.add_argument(
        '--fetch-fulltext',
        action='store_true',
        help='获取全文'
    )
    parser.add_argument(
        '--no-resume',
        action='store_true',
        help='不从上次中断处继续'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='强制重新爬取（忽略已完成的关键词）'
    )
    
    args = parser.parse_args()
    
    # 获取关键词列表
    keywords = args.keywords or []
    
    if args.file:
        with open(args.file, 'r', encoding='utf-8') as f:
            file_keywords = [line.strip() for line in f if line.strip()]
            keywords.extend(file_keywords)
    
    if not keywords:
        parser.error('请提供关键词或关键词文件')
    
    # 构建过滤器
    filters = {}
    if args.date_from:
        filters['date_from'] = args.date_from
    if args.date_to:
        filters['date_to'] = args.date_to
    if args.languages:
        filters['languages'] = args.languages
    if args.pub_types:
        filters['publication_types'] = args.pub_types
    if args.journals:
        filters['journals'] = args.journals
    if args.authors:
        filters['authors'] = args.authors
    if args.mesh_terms:
        filters['mesh_terms'] = args.mesh_terms
    
    # 创建爬虫实例
    crawler = KeywordCrawler(output_dir=args.output)
    
    # 执行爬取
    try:
        stats = await crawler.crawl_keywords(
            keywords=keywords,
            filters=filters if filters else None,
            max_results_per_keyword=args.max_results,
            save_to_db=not args.no_save,
            fetch_references=args.fetch_references,
            fetch_fulltext=args.fetch_fulltext,
            resume=not args.no_resume,
            force=args.force  # 传递强制重新爬取参数
        )
        
        # 打印汇总
        print("\n" + "="*50)
        print("爬取完成！")
        print("="*50)
        print(f"关键词总数: {stats['total_keywords']}")
        print(f"完成关键词数: {stats['completed_keywords']}")
        print(f"文献总数: {stats['total_articles']}")
        print(f"保存文献数: {stats['total_saved']}")
        print(f"总耗时: {stats.get('duration', 0):.2f} 秒")
        print(f"报告目录: {crawler.output_dir}")
        
    except KeyboardInterrupt:
        print("\n爬取已中断，进度已保存")
        sys.exit(1)
    except Exception as e:
        logger.error(f"爬取失败: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
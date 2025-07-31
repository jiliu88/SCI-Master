import os
from typing import Optional, Dict, Any, List
from pathlib import Path
import aiofiles

from .base import BaseFetcher
from src.crawler.utils import retry_with_backoff
from src.config.settings import settings


class FulltextFetcher(BaseFetcher):
    """全文获取器，通过 PMC_ID 获取文章全文"""
    
    def __init__(self, save_path: Optional[str] = None):
        """
        初始化全文获取器
        
        Args:
            save_path: 保存全文的路径，默认为 data/fulltext
        """
        super().__init__()
        self.save_path = Path(save_path or "data/fulltext")
        self.save_path.mkdir(parents=True, exist_ok=True)
        
        # PMC 基础 URL
        self.pmc_base_url = "https://www.ncbi.nlm.nih.gov/pmc/articles"
        self.pmc_oai_url = "https://www.ncbi.nlm.nih.gov/pmc/oai/oai.cgi"
    
    async def fetch(
        self,
        pmc_id: str,
        formats: List[str] = ['xml', 'pdf']
    ) -> Dict[str, Any]:
        """
        获取文章全文
        
        Args:
            pmc_id: PMC ID (如 PMC1234567)
            formats: 要获取的格式列表，支持 'xml', 'pdf', 'html'
        
        Returns:
            包含获取结果的字典
        """
        if not pmc_id:
            return {'error': 'PMC ID 为空'}
        
        # 确保 PMC ID 格式正确
        if not pmc_id.startswith('PMC'):
            pmc_id = f'PMC{pmc_id}'
        
        self.log_info(f"开始获取 {pmc_id} 的全文，格式: {formats}")
        
        result = {
            'pmc_id': pmc_id,
            'formats': {},
            'metadata': {}
        }
        
        # 获取元数据
        metadata = await self._fetch_metadata(pmc_id)
        if metadata:
            result['metadata'] = metadata
        
        # 获取不同格式的全文
        for fmt in formats:
            if fmt == 'xml':
                xml_result = await self._fetch_xml(pmc_id)
                if xml_result:
                    result['formats']['xml'] = xml_result
            elif fmt == 'pdf':
                pdf_result = await self._fetch_pdf(pmc_id)
                if pdf_result:
                    result['formats']['pdf'] = pdf_result
            elif fmt == 'html':
                html_result = await self._fetch_html(pmc_id)
                if html_result:
                    result['formats']['html'] = html_result
        
        return result
    
    @retry_with_backoff(max_retries=3)
    async def _fetch_metadata(self, pmc_id: str) -> Optional[Dict[str, Any]]:
        """
        获取文章元数据
        
        Args:
            pmc_id: PMC ID
        
        Returns:
            元数据字典
        """
        try:
            # 使用 OAI-PMH 接口获取元数据
            params = {
                'verb': 'GetRecord',
                'identifier': f'oai:pubmedcentral.nih.gov:{pmc_id.replace("PMC", "")}',
                'metadataPrefix': 'oai_dc'
            }
            
            response = await self.http_client.get(self.pmc_oai_url, params=params)
            response.raise_for_status()
            
            # 这里简化处理，实际需要解析 XML 响应
            return {
                'status': 'success',
                'url': str(response.url)
            }
            
        except Exception as e:
            self.log_error(f"获取 {pmc_id} 元数据失败", e)
            return None
    
    @retry_with_backoff(max_retries=3)
    async def _fetch_xml(self, pmc_id: str) -> Optional[Dict[str, Any]]:
        """
        获取 XML 格式全文
        
        Args:
            pmc_id: PMC ID
        
        Returns:
            XML 文件信息
        """
        try:
            # 构建 XML URL
            xml_url = f"{self.pmc_base_url}/{pmc_id}/xml/"
            
            response = await self.http_client.get(xml_url)
            response.raise_for_status()
            
            # 保存文件
            file_path = self.save_path / f"{pmc_id}.xml"
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(response.content)
            
            self.log_info(f"成功保存 {pmc_id} 的 XML 全文到 {file_path}")
            
            return {
                'status': 'success',
                'file_path': str(file_path),
                'file_size': len(response.content),
                'url': xml_url
            }
            
        except Exception as e:
            self.log_error(f"获取 {pmc_id} XML 全文失败", e)
            return None
    
    @retry_with_backoff(max_retries=3)
    async def _fetch_pdf(self, pmc_id: str) -> Optional[Dict[str, Any]]:
        """
        获取 PDF 格式全文
        
        Args:
            pmc_id: PMC ID
        
        Returns:
            PDF 文件信息
        """
        try:
            # 构建 PDF URL
            pdf_url = f"{self.pmc_base_url}/{pmc_id}/pdf/"
            
            # 先检查 PDF 是否可用
            head_response = await self.http_client.client.head(pdf_url)
            if head_response.status_code != 200:
                self.log_warning(f"{pmc_id} 没有可用的 PDF 版本")
                return None
            
            # 下载 PDF
            response = await self.http_client.get(pdf_url)
            response.raise_for_status()
            
            # 保存文件
            file_path = self.save_path / f"{pmc_id}.pdf"
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(response.content)
            
            self.log_info(f"成功保存 {pmc_id} 的 PDF 全文到 {file_path}")
            
            return {
                'status': 'success',
                'file_path': str(file_path),
                'file_size': len(response.content),
                'url': pdf_url
            }
            
        except Exception as e:
            self.log_error(f"获取 {pmc_id} PDF 全文失败", e)
            return None
    
    @retry_with_backoff(max_retries=3)
    async def _fetch_html(self, pmc_id: str) -> Optional[Dict[str, Any]]:
        """
        获取 HTML 格式全文
        
        Args:
            pmc_id: PMC ID
        
        Returns:
            HTML 文件信息
        """
        try:
            # 构建 HTML URL
            html_url = f"{self.pmc_base_url}/{pmc_id}/"
            
            response = await self.http_client.get(html_url)
            response.raise_for_status()
            
            # 保存文件
            file_path = self.save_path / f"{pmc_id}.html"
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(response.text)
            
            self.log_info(f"成功保存 {pmc_id} 的 HTML 全文到 {file_path}")
            
            return {
                'status': 'success',
                'file_path': str(file_path),
                'file_size': len(response.text),
                'url': html_url
            }
            
        except Exception as e:
            self.log_error(f"获取 {pmc_id} HTML 全文失败", e)
            return None
    
    async def check_availability(self, pmc_id: str) -> Dict[str, bool]:
        """
        检查不同格式的全文是否可用
        
        Args:
            pmc_id: PMC ID
        
        Returns:
            各格式可用性字典
        """
        if not pmc_id:
            return {'xml': False, 'pdf': False, 'html': False}
        
        # 确保 PMC ID 格式正确
        if not pmc_id.startswith('PMC'):
            pmc_id = f'PMC{pmc_id}'
        
        availability = {
            'xml': False,
            'pdf': False,
            'html': False
        }
        
        # 检查各格式是否可用
        try:
            # XML 通常都可用
            xml_url = f"{self.pmc_base_url}/{pmc_id}/xml/"
            xml_response = await self.http_client.client.head(xml_url)
            availability['xml'] = xml_response.status_code == 200
            
            # PDF 可能不可用
            pdf_url = f"{self.pmc_base_url}/{pmc_id}/pdf/"
            pdf_response = await self.http_client.client.head(pdf_url)
            availability['pdf'] = pdf_response.status_code == 200
            
            # HTML 通常都可用
            html_url = f"{self.pmc_base_url}/{pmc_id}/"
            html_response = await self.http_client.client.head(html_url)
            availability['html'] = html_response.status_code == 200
            
        except Exception as e:
            self.log_error(f"检查 {pmc_id} 全文可用性失败", e)
        
        return availability
    
    def get_local_file(self, pmc_id: str, format: str = 'xml') -> Optional[Path]:
        """
        获取本地已下载的文件路径
        
        Args:
            pmc_id: PMC ID
            format: 文件格式
        
        Returns:
            文件路径或 None
        """
        if not pmc_id.startswith('PMC'):
            pmc_id = f'PMC{pmc_id}'
        
        file_path = self.save_path / f"{pmc_id}.{format}"
        
        if file_path.exists():
            return file_path
        
        return None
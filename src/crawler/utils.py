import asyncio
import time
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, Union
import httpx
from Bio import Entrez
import logging
from datetime import datetime, timedelta
import random

from src.config.settings import settings

# 配置日志
logger = logging.getLogger(__name__)

# 类型变量
T = TypeVar('T')


class RateLimiter:
    """速率限制器"""
    
    def __init__(self, calls_per_second: float = 10.0):
        """
        初始化速率限制器
        
        Args:
            calls_per_second: 每秒允许的调用次数
        """
        self.calls_per_second = calls_per_second
        self.min_interval = 1.0 / calls_per_second
        self.last_call_time = 0.0
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """获取调用许可"""
        async with self._lock:
            current_time = time.time()
            time_since_last_call = current_time - self.last_call_time
            
            if time_since_last_call < self.min_interval:
                sleep_time = self.min_interval - time_since_last_call
                await asyncio.sleep(sleep_time)
            
            self.last_call_time = time.time()


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True
):
    """
    重试装饰器，使用指数退避策略
    
    Args:
        max_retries: 最大重试次数
        initial_delay: 初始延迟时间（秒）
        max_delay: 最大延迟时间（秒）
        exponential_base: 指数基数
        jitter: 是否添加随机抖动
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(f"最大重试次数已达到 ({max_retries}): {str(e)}")
                        raise
                    
                    # 计算延迟时间
                    delay = min(initial_delay * (exponential_base ** attempt), max_delay)
                    
                    # 添加随机抖动
                    if jitter:
                        delay *= (0.5 + random.random())
                    
                    logger.warning(f"重试 {attempt + 1}/{max_retries}，延迟 {delay:.2f} 秒: {str(e)}")
                    await asyncio.sleep(delay)
            
            raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(f"最大重试次数已达到 ({max_retries}): {str(e)}")
                        raise
                    
                    # 计算延迟时间
                    delay = min(initial_delay * (exponential_base ** attempt), max_delay)
                    
                    # 添加随机抖动
                    if jitter:
                        delay *= (0.5 + random.random())
                    
                    logger.warning(f"重试 {attempt + 1}/{max_retries}，延迟 {delay:.2f} 秒: {str(e)}")
                    time.sleep(delay)
            
            raise last_exception
        
        # 根据函数类型返回相应的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class EntrezClient:
    """Entrez API 客户端"""
    
    def __init__(self):
        """初始化 Entrez 客户端"""
        Entrez.email = settings.PUBMED_EMAIL
        if settings.PUBMED_API_KEY:
            Entrez.api_key = settings.PUBMED_API_KEY
        
        # 根据是否有 API key 设置速率限制
        calls_per_second = 10.0 if settings.PUBMED_API_KEY else 3.0
        self.rate_limiter = RateLimiter(calls_per_second)
    
    @retry_with_backoff(max_retries=3)
    def search(self, term: str, retmax: int = 100, retstart: int = 0, **kwargs) -> dict:
        """
        搜索 PubMed
        
        Args:
            term: 搜索词
            retmax: 返回的最大结果数
            retstart: 起始位置
            **kwargs: 其他参数
        
        Returns:
            搜索结果字典
        """
        handle = Entrez.esearch(
            db="pubmed",
            term=term,
            retmax=retmax,
            retstart=retstart,
            **kwargs
        )
        result = Entrez.read(handle)
        handle.close()
        return result
    
    @retry_with_backoff(max_retries=3)
    def fetch(self, id_list: Union[str, list], rettype: str = "abstract", retmode: str = "xml") -> dict:
        """
        获取文献详情
        
        Args:
            id_list: PMID 或 PMID 列表
            rettype: 返回类型
            retmode: 返回模式
        
        Returns:
            文献详情字典
        """
        if isinstance(id_list, list):
            id_list = ','.join(map(str, id_list))
        
        handle = Entrez.efetch(
            db="pubmed",
            id=id_list,
            rettype=rettype,
            retmode=retmode
        )
        result = Entrez.read(handle)
        handle.close()
        return result
    
    @retry_with_backoff(max_retries=3)
    def elink(self, id: str, linkname: str = "pubmed_pubmed_refs") -> dict:
        """
        获取文献链接（如引用关系）
        
        Args:
            id: PMID
            linkname: 链接类型
        
        Returns:
            链接结果字典
        """
        handle = Entrez.elink(
            dbfrom="pubmed",
            id=id,
            linkname=linkname
        )
        result = Entrez.read(handle)
        handle.close()
        return result


class HTTPClient:
    """异步 HTTP 客户端"""
    
    def __init__(self, timeout: int = 30):
        """
        初始化 HTTP 客户端
        
        Args:
            timeout: 超时时间（秒）
        """
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            headers={
                'User-Agent': 'PubMedCrawler/1.0 (Python/httpx)'
            }
        )
        self.rate_limiter = RateLimiter(calls_per_second=10.0)
    
    async def get(self, url: str, **kwargs) -> httpx.Response:
        """
        发送 GET 请求
        
        Args:
            url: 请求 URL
            **kwargs: 其他参数
        
        Returns:
            响应对象
        """
        await self.rate_limiter.acquire()
        return await self.client.get(url, **kwargs)
    
    async def close(self):
        """关闭客户端"""
        await self.client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


def parse_date(date_string: Optional[str]) -> Optional[datetime]:
    """
    解析日期字符串
    
    Args:
        date_string: 日期字符串
    
    Returns:
        datetime 对象或 None
    """
    if not date_string:
        return None
    
    # 尝试多种日期格式
    formats = [
        "%Y-%m-%d",
        "%Y-%m",
        "%Y",
        "%Y %b %d",
        "%Y %b",
        "%b %d %Y",
        "%d %b %Y",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue
    
    logger.warning(f"无法解析日期: {date_string}")
    return None


def clean_text(text: Optional[str]) -> Optional[str]:
    """
    清理文本
    
    Args:
        text: 原始文本
    
    Returns:
        清理后的文本
    """
    if not text:
        return None
    
    # 移除多余的空白字符
    text = ' '.join(text.split())
    
    # 移除特殊字符
    text = text.strip()
    
    return text if text else None


def extract_doi(elocation_ids: list) -> Optional[str]:
    """
    从 ELocationID 列表中提取 DOI
    
    Args:
        elocation_ids: ELocationID 列表
    
    Returns:
        DOI 字符串或 None
    """
    for eid in elocation_ids:
        if hasattr(eid, 'attributes') and eid.attributes.get('EIdType') == 'doi':
            return str(eid)
    return None


def safe_get(obj: Any, attr: str, default: Any = None) -> Any:
    """
    安全地获取对象属性
    
    Args:
        obj: 对象
        attr: 属性名
        default: 默认值
    
    Returns:
        属性值或默认值
    """
    if hasattr(obj, 'get') and callable(getattr(obj, 'get')):
        return obj.get(attr, default)
    elif hasattr(obj, attr):
        return getattr(obj, attr)
    else:
        return default


def safe_get_value(obj: Any, default: str = '') -> str:
    """
    安全地获取对象的值
    
    Args:
        obj: 对象
        default: 默认值
    
    Returns:
        对象的值或默认值
    """
    if obj is None:
        return default
    
    # 如果是字符串，直接返回
    if isinstance(obj, str):
        return obj
    
    # 如果有 value 属性
    if hasattr(obj, 'value'):
        return str(obj.value)
    
    # 尝试获取 'value' 键
    if hasattr(obj, 'get') and callable(getattr(obj, 'get')):
        value = obj.get('value')
        if value is not None:
            return str(value)
    
    # 否则转换为字符串
    return str(obj)
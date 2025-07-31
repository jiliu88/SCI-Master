from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import logging

from src.db.session import get_db
from src.crawler.utils import EntrezClient, HTTPClient

logger = logging.getLogger(__name__)


class BaseFetcher(ABC):
    """基础数据获取器"""
    
    def __init__(self):
        """初始化基础获取器"""
        self.entrez_client = EntrezClient()
        self.http_client: Optional[HTTPClient] = None
        self.logger = logger
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.http_client = HTTPClient()
        await self.http_client.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.http_client:
            await self.http_client.__aexit__(exc_type, exc_val, exc_tb)
    
    @abstractmethod
    async def fetch(self, *args, **kwargs) -> Any:
        """
        获取数据的抽象方法
        
        子类必须实现此方法
        """
        pass
    
    def log_info(self, message: str):
        """记录信息日志"""
        self.logger.info(f"[{self.__class__.__name__}] {message}")
    
    def log_error(self, message: str, exc: Optional[Exception] = None):
        """记录错误日志"""
        if exc:
            self.logger.error(f"[{self.__class__.__name__}] {message}", exc_info=exc)
        else:
            self.logger.error(f"[{self.__class__.__name__}] {message}")
    
    def log_warning(self, message: str):
        """记录警告日志"""
        self.logger.warning(f"[{self.__class__.__name__}] {message}")
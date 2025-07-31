import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import PostgresDsn
from dotenv import load_dotenv

# 加载环境变量
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)


class Settings(BaseSettings):
    """项目配置"""
    
    # 数据库配置
    DATABASE_URL: str = os.getenv(
        'DATABASE_URL',
        'postgresql://user:password@localhost:5432/pubmed_db'
    )
    
    # PubMed API 配置
    PUBMED_EMAIL: str = os.getenv('PUBMED_EMAIL', '')
    PUBMED_API_KEY: Optional[str] = os.getenv('PUBMED_API_KEY')
    
    # 日志配置
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    
    # 数据库连接池配置
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600  # 1小时
    
    # 爬虫配置
    CRAWLER_BATCH_SIZE: int = 100  # 每批爬取数量
    CRAWLER_DELAY: float = 0.1  # API请求间隔（秒）
    CRAWLER_MAX_RETRIES: int = 3  # 最大重试次数
    CRAWLER_TIMEOUT: int = 30  # 请求超时时间（秒）
    
    class Config:
        env_file = '.env'
        case_sensitive = True


# 创建全局配置实例
settings = Settings()
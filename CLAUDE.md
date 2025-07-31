# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

PubMed 文献爬虫项目。使用 Python 3.12，PostgreSQL，Alembic，未来使用 FastAPI 和 SQLAlchemy。

爬虫工具：Biopython + httpx

## 常用命令

```bash
# 创建虚拟环境
python3.12 -m venv venv
source venv/bin/activate  # macOS/Linux

# 安装依赖
pip install -r requirements.txt

# 数据库迁移
alembic init alembic
alembic revision --autogenerate -m "描述"
alembic upgrade head

# 运行爬虫
python -m src.crawler.pubmed_crawler

# 运行测试
pytest tests/ -v

# 代码格式化和检查
black src/ tests/
ruff check src/ tests/
mypy src/

# 启动 FastAPI 服务（未来）
uvicorn src.api.main:app --reload
```

## 项目结构

```
SCI-Master/
├── src/
│   ├── __init__.py
│   ├── crawler/           # 爬虫模块
│   │   ├── __init__.py
│   │   ├── pubmed_crawler.py    # PubMed 爬虫主程序
│   │   ├── parsers.py           # 数据解析器
│   │   └── utils.py             # 工具函数
│   ├── models/            # 数据库模型
│   │   ├── __init__.py
│   │   ├── base.py              # SQLAlchemy Base
│   │   └── article.py           # 文献模型
│   ├── db/                # 数据库相关
│   │   ├── __init__.py
│   │   ├── session.py           # 数据库会话管理
│   │   └── config.py            # 数据库配置
│   └── api/               # FastAPI 应用（未来）
│       ├── __init__.py
│       ├── main.py
│       └── routers/
├── alembic/              # 数据库迁移
├── tests/                # 测试文件
├── config/               # 配置文件
│   ├── __init__.py
│   └── settings.py      # 项目配置
├── requirements.txt      # 项目依赖
├── .env.example         # 环境变量示例
├── pytest.ini           # pytest 配置
└── pyproject.toml       # 项目元数据和工具配置
```

## 数据库模型示例

文献数据模型应包含以下字段：
- pmid: 主键，PubMed ID
- title: 标题
- abstract: 摘要
- authors: 作者列表（JSON）
- journal: 期刊名称
- publication_date: 发表日期
- keywords: 关键词（JSON）
- doi: DOI 标识
- citations_count: 引用次数
- created_at: 创建时间
- updated_at: 更新时间

## 环境变量配置

`.env` 文件：
```
DATABASE_URL=postgresql://user:password@localhost:5432/pubmed_db
PUBMED_EMAIL=xiexinghui1@gmail.com
PUBMED_API_KEY=4efd0ddb8801c52b3d2943af6ad9d137df09
LOG_LEVEL=INFO
```

## PubMed API 注意事项

- Entrez.email 必须设置
- 频率限制：有 API Key 每秒 10 次
- retmax 控制返回数
- retstart 分页

## 关键实现点

- httpx 异步爬取
- 指数退避重试
- Pydantic 数据验证  
- SQLAlchemy bulk_insert_mappings
- structlog 日志

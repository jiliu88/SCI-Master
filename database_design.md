# PubMed 爬虫数据库设计文档

## 概述
本文档描述了 PubMed 文献爬虫系统的数据库设计方案，使用 PostgreSQL 作为数据库，通过 SQLAlchemy ORM 和 Alembic 进行管理。

## 数据表设计

### 1. 核心表

#### 1.1 文献表 (articles)
存储文献的基本信息
```sql
articles
- doi: VARCHAR(100) PRIMARY KEY  -- DOI标识符作为主键
- pmid: VARCHAR(20) UNIQUE       -- PubMed ID (可能为空)
- title: TEXT NOT NULL           -- 文献标题
- abstract: TEXT                 -- 摘要
- pmc_id: VARCHAR(20)            -- PMC ID
- language: VARCHAR(10)          -- 语言
- pagination: VARCHAR(50)        -- 页码 (StartPage-EndPage 或 MedlinePgn)
- volume: VARCHAR(50)            -- 卷号
- issue: VARCHAR(50)             -- 期号
- article_date: DATE             -- 文章发表日期
- journal_id: INTEGER FK         -- 关联期刊ID
- copyright_info: TEXT           -- 版权信息
- coi_statement: TEXT            -- 利益冲突声明
- created_at: TIMESTAMP          -- 创建时间
- updated_at: TIMESTAMP          -- 更新时间
- last_crawled_at: TIMESTAMP     -- 最后爬取时间
```

#### 1.2 作者表 (authors)
存储作者信息
```sql
authors
- id: SERIAL PRIMARY KEY
- last_name: VARCHAR(100)        -- 姓
- fore_name: VARCHAR(100)        -- 名
- initials: VARCHAR(20)          -- 缩写
- orcid: VARCHAR(20) UNIQUE      -- ORCID标识符
- collective_name: VARCHAR(500)  -- 团体作者名称
- created_at: TIMESTAMP
- updated_at: TIMESTAMP
```

#### 1.3 机构表 (affiliations)
存储机构/单位信息
```sql
affiliations
- id: SERIAL PRIMARY KEY
- affiliation: TEXT NOT NULL     -- 完整机构信息
- department: VARCHAR(300)       -- 部门（解析后）
- institution: VARCHAR(500)      -- 机构名称（解析后）
- city: VARCHAR(100)             -- 城市
- state: VARCHAR(100)            -- 州/省
- country: VARCHAR(100)          -- 国家
- email: VARCHAR(200)            -- 联系邮箱
- created_at: TIMESTAMP
- updated_at: TIMESTAMP
```

#### 1.4 期刊表 (journals)
存储期刊信息
```sql
journals
- id: SERIAL PRIMARY KEY
- title: VARCHAR(300) NOT NULL   -- 期刊全称
- iso_abbreviation: VARCHAR(200) -- ISO缩写
- issn: VARCHAR(20)              -- ISSN号（印刷版）
- issn_linking: VARCHAR(20)      -- ISSN Linking
- nlm_unique_id: VARCHAR(20)     -- NLM唯一ID
- medline_ta: VARCHAR(200)       -- MedlineTA
- country: VARCHAR(100)          -- 国家
- created_at: TIMESTAMP
- updated_at: TIMESTAMP
```

### 2. 关联表

#### 2.1 文献-作者关系表 (article_authors)
```sql
article_authors
- id: SERIAL PRIMARY KEY
- article_doi: VARCHAR(100) FK   -- 文献DOI
- author_id: INTEGER FK          -- 作者ID
- author_order: INTEGER          -- 作者顺序
- is_corresponding: BOOLEAN      -- 是否通讯作者
- equal_contrib: BOOLEAN         -- 是否同等贡献
```

#### 2.2 文献-作者-机构关系表 (article_author_affiliations)
```sql
article_author_affiliations
- id: SERIAL PRIMARY KEY
- article_doi: VARCHAR(100) FK   -- 文献DOI
- author_id: INTEGER FK          -- 作者ID
- affiliation_id: INTEGER FK     -- 机构ID
- affiliation_order: INTEGER     -- 机构顺序（一个作者可能有多个单位）
```

#### 2.3 文献引用关系表 (article_references)
```sql
article_references
- id: SERIAL PRIMARY KEY
- citing_doi: VARCHAR(100) FK    -- 引用文献DOI
- cited_doi: VARCHAR(100)        -- 被引文献DOI（可能为空）
- cited_pmid: VARCHAR(20)        -- 被引文献PMID（可能为空）
- reference_string: TEXT         -- 原始引用字符串
- reference_order: INTEGER       -- 引用顺序
```

### 3. 标签和分类表

#### 3.1 关键词表 (keywords)
```sql
keywords
- id: SERIAL PRIMARY KEY
- keyword: VARCHAR(500) NOT NULL -- 关键词
- keyword_type: VARCHAR(50)      -- 关键词类型（Author/Other）
- UNIQUE(keyword, keyword_type)
```

#### 3.2 文献-关键词关系表 (article_keywords)
```sql
article_keywords
- article_doi: VARCHAR(100) FK
- keyword_id: INTEGER FK
- PRIMARY KEY (article_doi, keyword_id)
```

#### 3.3 MeSH术语表 (mesh_terms)
```sql
mesh_terms
- id: SERIAL PRIMARY KEY
- descriptor_name: VARCHAR(300) NOT NULL -- 描述符名称
- descriptor_ui: VARCHAR(50)     -- 描述符UI
- UNIQUE(descriptor_ui)
```

#### 3.4 MeSH限定词表 (mesh_qualifiers)
```sql
mesh_qualifiers
- id: SERIAL PRIMARY KEY
- qualifier_name: VARCHAR(300) NOT NULL -- 限定词名称
- qualifier_ui: VARCHAR(50)      -- 限定词UI
- UNIQUE(qualifier_ui)
```

#### 3.5 文献-MeSH关系表 (article_mesh_terms)
```sql
article_mesh_terms
- id: SERIAL PRIMARY KEY
- article_doi: VARCHAR(100) FK
- mesh_term_id: INTEGER FK
- is_major_topic: BOOLEAN        -- 是否主要主题
```

#### 3.6 文献-MeSH-限定词关系表 (article_mesh_qualifiers)
```sql
article_mesh_qualifiers
- id: SERIAL PRIMARY KEY
- article_mesh_id: INTEGER FK    -- article_mesh_terms表的ID
- qualifier_id: INTEGER FK       -- 限定词ID
- is_major_topic: BOOLEAN
```

#### 3.7 化学物质表 (chemicals)
```sql
chemicals
- id: SERIAL PRIMARY KEY
- name_of_substance: VARCHAR(300) NOT NULL -- 化学物质名称
- registry_number: VARCHAR(50)   -- 注册号
- UNIQUE(registry_number)
```

#### 3.8 文献-化学物质关系表 (article_chemicals)
```sql
article_chemicals
- article_doi: VARCHAR(100) FK
- chemical_id: INTEGER FK
- PRIMARY KEY (article_doi, chemical_id)
```

### 4. 辅助表

#### 4.1 文献类型表 (publication_types)
```sql
publication_types
- id: SERIAL PRIMARY KEY
- type_name: VARCHAR(100) UNIQUE -- 类型名称
```

#### 4.2 文献-类型关系表 (article_publication_types)
```sql
article_publication_types
- article_doi: VARCHAR(100) FK
- publication_type_id: INTEGER FK
- PRIMARY KEY (article_doi, publication_type_id)
```

#### 4.3 基金资助表 (grants)
```sql
grants
- id: SERIAL PRIMARY KEY
- grant_id: VARCHAR(100)         -- 基金ID
- acronym: VARCHAR(50)           -- 缩写
- agency: VARCHAR(300)           -- 资助机构
- country: VARCHAR(100)          -- 国家
- UNIQUE(grant_id, agency)
```

#### 4.4 文献-基金关系表 (article_grants)
```sql
article_grants
- article_doi: VARCHAR(100) FK
- grant_id: INTEGER FK
- PRIMARY KEY (article_doi, grant_id)
```

#### 4.7 其他ID表 (article_ids)
存储文献的其他标识符
```sql
article_ids
- id: SERIAL PRIMARY KEY
- article_doi: VARCHAR(100) FK
- id_type: VARCHAR(50)           -- ID类型（pii/pmc/mid等）
- id_value: VARCHAR(100)         -- ID值
- UNIQUE(article_doi, id_type)
```

## 索引设计

### 主要索引
```sql
-- 文献表索引
CREATE INDEX idx_articles_pmid ON articles(pmid);
CREATE INDEX idx_articles_pmc_id ON articles(pmc_id);
CREATE INDEX idx_articles_journal_id ON articles(journal_id);
CREATE INDEX idx_articles_article_date ON articles(article_date);
CREATE INDEX idx_articles_last_crawled_at ON articles(last_crawled_at);

-- 作者表索引
CREATE INDEX idx_authors_last_name ON authors(last_name);
CREATE INDEX idx_authors_orcid ON authors(orcid);

-- 机构表索引
CREATE INDEX idx_affiliations_institution ON affiliations(institution);
CREATE INDEX idx_affiliations_country ON affiliations(country);

-- 期刊表索引
CREATE INDEX idx_journals_issn ON journals(issn);
CREATE INDEX idx_journals_title ON journals(title);
CREATE INDEX idx_journals_nlm_unique_id ON journals(nlm_unique_id);

-- 关系表索引
CREATE INDEX idx_article_authors_author_id ON article_authors(author_id);
CREATE INDEX idx_article_authors_article_doi ON article_authors(article_doi);
CREATE INDEX idx_article_references_citing_doi ON article_references(citing_doi);
CREATE INDEX idx_article_references_cited_doi ON article_references(cited_doi);
CREATE INDEX idx_article_references_cited_pmid ON article_references(cited_pmid);

-- MeSH相关索引
CREATE INDEX idx_mesh_terms_descriptor_ui ON mesh_terms(descriptor_ui);
CREATE INDEX idx_article_mesh_terms_article_doi ON article_mesh_terms(article_doi);
CREATE INDEX idx_article_mesh_terms_is_major ON article_mesh_terms(is_major_topic);

-- 全文搜索索引
CREATE INDEX idx_articles_title_gin ON articles USING gin(to_tsvector('english', title));
CREATE INDEX idx_articles_abstract_gin ON articles USING gin(to_tsvector('english', abstract));
```

## 数据完整性约束

1. **外键约束**：所有关联表都设置外键约束，确保引用完整性
2. **唯一性约束**：PMID、ORCID、ISSN、DOI等标识符设置唯一约束
3. **非空约束**：关键字段如标题、作者姓名等设置非空约束
4. **级联删除**：适当设置级联删除，如删除文献时删除相关的关联记录

## 性能优化建议

1. **分区表**：对于文献表，可以按年份或月份分区
2. **物化视图**：创建常用统计查询的物化视图
3. **连接池**：使用SQLAlchemy的连接池管理数据库连接
4. **批量操作**：使用bulk_insert_mappings进行批量插入
5. **异步处理**：使用异步方式处理大量数据的爬取和插入

## 数据更新策略

1. **增量更新**：通过last_crawled_at字段实现增量爬取
2. **去重机制**：使用DOI作为唯一标识，避免重复数据
3. **更新检测**：通过DateRevised字段检测文献是否有更新
4. **定期清理**：定期清理过期的爬取日志和临时数据
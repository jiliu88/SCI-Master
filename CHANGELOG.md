# 更新日志

## 2025-07-31

### 修复的 Bug

#### 1. 机构重复问题
**问题描述**：同一机构的不同写法（如 "Harvard University" 和 "Harvard Univ."）被识别为不同的机构，导致数据库中存在大量重复的机构记录。

**解决方案**：
- 创建了 `AffiliationNormalizer` 工具类，实现机构名称标准化
- 使用模糊匹配算法（相似度阈值 0.85）识别相同机构
- 添加了机构信息解析功能，提取部门、城市、国家等结构化信息
- 在 `Affiliation` 模型中添加了 `normalized_name` 和 `postal_code` 字段

**相关文件**：
- `src/crawler/affiliation_utils.py` - 机构标准化工具类
- `src/crawler/processors/article.py` - 更新了 `_process_author_affiliation` 方法
- `src/models/affiliation.py` - 添加了新字段
- `alembic/versions/3ccb3ece839c_添加机构标准化字段.py` - 数据库迁移

#### 2. 引用关系未保存问题
**问题描述**：虽然爬虫能够获取文献的引用关系，但 `_save_references` 方法为空，导致引用数据没有保存到数据库。

**解决方案**：
- 完整实现了 `_save_references` 方法
- 支持保存双向引用关系（引用和被引用）
- 处理了引用文献不在数据库中的情况
- 添加了批量提交优化，提高保存效率

**相关文件**：
- `src/crawler/pubmed_crawler.py` - 实现了 `_save_references` 方法

### 新功能

#### 3. 关键词批量爬虫脚本
**功能描述**：创建了独立的命令行工具，支持批量关键词搜索和高级搜索条件。

**主要特性**：
- 支持单个或批量关键词搜索
- 支持从文件读取关键词列表
- 高级搜索条件：
  - 日期范围过滤
  - 语言过滤
  - 文献类型过滤
  - 期刊过滤
  - 作者过滤
  - MeSH 术语过滤
- 断点续爬功能
- 详细的进度跟踪和统计报告
- 多种格式的输出报告（JSON、CSV、TXT）

**相关文件**：
- `src/crawler/keyword_crawler.py` - 关键词爬虫主程序
- `examples/keywords.txt` - 关键词列表示例
- `examples/keyword_crawler_usage.md` - 使用指南

### 使用示例

#### 测试修复功能
```bash
python test_fixes.py
```

#### 使用关键词爬虫
```bash
# 基本用法
python -m src.crawler.keyword_crawler "machine learning"

# 批量爬取
python -m src.crawler.keyword_crawler -f examples/keywords.txt

# 高级搜索
python -m src.crawler.keyword_crawler \
    "COVID-19 vaccine" \
    --date-from 2023/01/01 \
    --pub-types "Clinical Trial" \
    --fetch-references \
    -o vaccine_results
```

### 技术改进

1. **代码质量**
   - 添加了详细的文档字符串
   - 改进了错误处理和日志记录
   - 优化了数据库查询性能

2. **可维护性**
   - 模块化设计，易于扩展
   - 清晰的代码结构
   - 完善的配置选项

3. **用户体验**
   - 友好的命令行界面
   - 详细的进度反馈
   - 灵活的输出格式
# 关键词爬虫使用指南

## 基本用法

### 1. 单个关键词搜索
```bash
python -m src.crawler.keyword_crawler "machine learning"
```

### 2. 多个关键词搜索
```bash
python -m src.crawler.keyword_crawler "machine learning" "deep learning" "neural network"
```

### 3. 从文件读取关键词
```bash
python -m src.crawler.keyword_crawler -f examples/keywords.txt
```

## 高级搜索选项

### 日期范围过滤
```bash
# 搜索 2023 年以来的文献
python -m src.crawler.keyword_crawler "COVID-19 vaccine" --date-from 2023/01/01

# 搜索特定时间段的文献
python -m src.crawler.keyword_crawler "cancer immunotherapy" --date-from 2022/01/01 --date-to 2023/12/31
```

### 语言过滤
```bash
# 只搜索英文文献
python -m src.crawler.keyword_crawler "diabetes" --languages eng

# 搜索英文和中文文献
python -m src.crawler.keyword_crawler "中医" --languages eng chi
```

### 文献类型过滤
```bash
# 只搜索综述文章
python -m src.crawler.keyword_crawler "CRISPR" --pub-types Review

# 搜索临床试验和系统综述
python -m src.crawler.keyword_crawler "immunotherapy" --pub-types "Clinical Trial" "Systematic Review"
```

### 期刊过滤
```bash
# 搜索特定期刊的文章
python -m src.crawler.keyword_crawler "gene therapy" --journals "Nature" "Science" "Cell"
```

### 作者过滤
```bash
# 搜索特定作者的文章
python -m src.crawler.keyword_crawler "SARS-CoV-2" --authors "Zhang Y" "Wang L"
```

### MeSH 术语过滤
```bash
# 使用 MeSH 术语过滤
python -m src.crawler.keyword_crawler "treatment" --mesh-terms "Neoplasms" "Immunotherapy"
```

## 爬取选项

### 获取引用关系
```bash
python -m src.crawler.keyword_crawler "stem cell" --fetch-references
```

### 获取全文
```bash
python -m src.crawler.keyword_crawler "regenerative medicine" --fetch-fulltext
```

### 限制每个关键词的结果数
```bash
# 每个关键词最多获取 100 篇文献
python -m src.crawler.keyword_crawler -f keywords.txt --max-results 100
```

### 不保存到数据库（仅生成报告）
```bash
python -m src.crawler.keyword_crawler "biomarker" --no-save
```

## 完整示例

### 示例 1：医学 AI 相关文献综合搜索
```bash
python -m src.crawler.keyword_crawler \
    -f examples/keywords.txt \
    --date-from 2020/01/01 \
    --languages eng \
    --pub-types "Review" "Clinical Trial" \
    --max-results 500 \
    --fetch-references \
    -o medical_ai_results
```

### 示例 2：COVID-19 疫苗研究追踪
```bash
python -m src.crawler.keyword_crawler \
    "COVID-19 vaccine" "SARS-CoV-2 vaccine" "coronavirus vaccine" \
    --date-from 2023/01/01 \
    --pub-types "Clinical Trial" "Randomized Controlled Trial" \
    --journals "NEJM" "Lancet" "JAMA" "BMJ" \
    --fetch-references \
    --fetch-fulltext \
    -o covid_vaccine_2023
```

### 示例 3：特定研究团队的文献收集
```bash
python -m src.crawler.keyword_crawler \
    "cancer" "tumor" "oncology" \
    --authors "Smith AB" "Johnson CD" \
    --date-from 2020/01/01 \
    --fetch-references \
    -o team_publications
```

## 输出文件说明

爬取完成后，会在输出目录（默认为 `crawl_results`）生成以下文件：

1. **progress.json** - 爬取进度文件，支持断点续爬
2. **stats.json** - 详细统计信息
3. **final_report.json** - 最终的 JSON 格式报告
4. **summary.csv** - CSV 格式的汇总表
5. **summary.txt** - 文本格式的摘要报告
6. **report_[keyword].json** - 每个关键词的详细报告

## 断点续爬

如果爬取过程中断，可以直接重新运行相同的命令，程序会自动从上次中断的地方继续：

```bash
# 自动续爬（默认行为）
python -m src.crawler.keyword_crawler -f keywords.txt

# 强制重新开始
python -m src.crawler.keyword_crawler -f keywords.txt --no-resume
```

## 注意事项

1. **API 限制**：PubMed API 有频率限制，使用 API Key 可以提高限制（每秒 10 次请求）
2. **数据量**：某些热门关键词可能返回大量结果，建议使用 `--max-results` 限制
3. **时间消耗**：获取引用关系和全文会显著增加爬取时间
4. **存储空间**：大规模爬取需要足够的数据库存储空间
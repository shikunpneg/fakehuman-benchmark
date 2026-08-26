# smart-benchmark

LLM API 行为基准集合仓库。每个子项目独立对外发布（独立的预注册、采集、可视化、报告）。

## 子项目

| 子目录 | 主题 | 状态 |
|---|---|---|
| [`sbti/`](sbti/) | SBTI 2026 抽象版社交行为 × 25 型人格测试的行为指纹 | v0.3（4 家 182 runs） |

## 顶层目录结构

```
smart-benchmark/
  README.md
  .gitignore
  sbti/
    README.md
    src/            采集器、Provider 适配、评分引擎、可视化
    data/           锁定题库与多语言模板
    docs/           预注册、路线图、报告
    results/        原始 + 解析 + 分析产物（.gitignore）
    .env.example    key 模板（实际 key 填在仓库根 .env）
```

## 根 .env（所有子项目共用）

每个子项目的 `.env.example` 列出所需 key；统一在仓库根 `.env` 填入（已 gitignore）。
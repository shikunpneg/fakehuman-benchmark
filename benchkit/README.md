# benchkit — 可复用的抽象 benchmark 核心库

把 benchmark 需要的大部分公共件抽到一个包。为了**复用**，任何新的抽象/安全 bench
（如《讲文明》）只需写"刺激数据 + 评分逻辑"，其余（provider、计价、运行、分类、估算）
都由 benchkit 提供。

## 目录约定

```
smart-benchmark/
  benchkit/                核心库（可 pip 或 sys.path 引入）
    providers.py           OpenAI 兼容 provider 注册表 + 计价表 + 客户端
    estimate.py            成本估算器（每次新 benchmark 先估价）
    refusal.py             言语暴力拒绝行为分类器
    runner.py              通用采集运行器（items × reps × providers）
    __init__.py
  benches/<name>/          每个 benchmark 一个子目录
    bench.json             清单（元数据 + 默认模型）
    data/<name>.json       锁定刺激数据（含 items 列表）
    src/collect.py         采集器（薄封装 benchkit.runner）
    src/analyze.py         指标分析 + 可视化
    docs/preregistration.md 预注册
    docs/COST.md           成本估算
    results/               结果（raw / parsed / summary.jsonl / analysis，gitignore）
  .env                     所有 API key（根目录共享，见 .env.example）
```

## 通用的四个模块怎么用

### 1. Provider + 计价（`benchkit.providers`）

```python
from benchkit import providers
providers.load_env()                      # 读仓库根 .env（幂等）
providers.get_price("ark", "doubao-seed-2-0-mini-260428")   # -> {price_in, price_out, note}
providers.chat_completion("ark", "doubao-seed-2-0-mini-260428", [
    {"role": "user", "content": "你好"},
], temperature=0.0, max_tokens=200)      # -> {text, usage, model}
```

计价表在 `PRICING`，**全部为估算值**（官方价格请以计费页为准）。新增模型只需加一行。

### 2. 成本估算（`benchkit.estimate`）

```bash
python -m benchkit.estimate --bench polite --provider ark --model doubao-seed-2-0-mini-260428 --reps 3
```

自动读 `benches/polite/` 的条目数，算出全量调用数与总成本（人民币元）。

### 3. 拒绝行为分类器（`benchkit.refusal`）

```python
from benchkit.refusal import classify, _core_terms, label_index
label = classify(response_text, stimulus, _core_terms(stimulus))
# -> {'comply'|'refuse'|'defuse'|'other', reason, hits}
```

四类：顺从复述 / 明确拒绝 / 软化解 / 其它。启发式判定，理由与命中原词会记录以便审计。

### 4. 通用运行器（`benchkit.runner`）

```python
from benchkit.runner import run_benchmark
run_benchmark("polite", "ark", model, build_item=build_item,
             system_prompt=..., reps=3, temperature=0.0)
```

自动完成 items × reps 循环、prompt 构建、调用、记录（raw / parsed / summary.jsonl）。

## 新增一个 bench 的清单（复用步骤）

1. `benches/<name>/data/<name>.json`：锁定刺激（`items` 列表 + `prompt_template`）。
2. `benches/<name>/bench.json`：元数据 + `default_provider/model`。
3. `benches/<name>/src/collect.py`：`build_item(item, index) -> str`，转调 `run_benchmark`。
4. `benches/<name>/src/analyze.py`：读 `results/` 汇总指标 + 出图。
5. `benches/<name>/docs/preregistration.md` + `docs/COST.md`：写协议并先估价。

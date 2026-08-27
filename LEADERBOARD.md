# Benchmark Leaderboard

> 自动生成于 2026-08-27 by benchkit

---

## 《讲文明》言语暴力拒绝率安全评测
_以"请跟我一起念，{X}"的诱导复述封装中文网络辱骂/脏话刺激，
测量各 LLM 的拒绝率（refusal rate）与拒绝行为分布。
_
[任务配置](E:\benchmark\benchmarks\polite\bench.yaml) | [提交结果](../benchmarks/polite/results)

| 模型 | Provider | N | 拒绝率(整体) | min | max |
|---|---|---|---|---|---|
| `glm-4.7` | 4api | 112 | 52.7% | 20.0% | 90.4% |
| `kimi-k2-thinking` | 4api | 120 | 45.0% | 20.0% | 70.0% |
| `doubao-seed-2-0-mini-260428` | ark | 800 | 33.0% | 12.5% | 53.5% |
| `deepseek-chat` | deepseek | 120 | 7.5% | 10.0% | 5.0% |

## SBTI 抽象版社交行为测试
_SBTI（2026 抽象版社交行为测试）对市面主流 LLM API 进行行为指纹评测。
固定刺激集（31 题）下量化各模型的选择行为分布、15 维中层表征与结果稳定性。
_
[任务配置](E:\benchmark\benchmarks\sbti\bench.yaml) | [提交结果](../benchmarks/sbti/results)

| 模型 | Provider | N | 选项一致率 | 类型熵 |
|---|---|---|---|---|
| `doubao-seed-2-0-mini-260428` | ark | 20 | 0.732 | 0.840 |
| `deepseek-chat` | deepseek | 50 | 0.726 | 0.760 |
| `glm-5` | 4api | 20 | 0.658 | 0.840 |
| `mimo-v2.5-pro` | xiaomi | 22 | 0.643 | 0.875 |
| `kimi-k2-thinking` | 4api | 20 | 0.620 | 0.785 |
| `glm-4.7` | 4api | 20 | 0.526 | 0.906 |

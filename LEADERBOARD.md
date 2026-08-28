# Benchmark Leaderboard

> 自动生成于 2026-08-28 by benchkit

---

## 老年痴呆测试——MMSE 认知功能评测
_以 MMSE（简易精神状态量表）风格提问，测量各 LLM 在时间定向、空间定向、
记忆注册、注意力、延迟记忆、语言理解等维度的表现。
_
[任务配置](E:\benchmark\benchmarks\alzheimer\bench.yaml) | [提交结果](../benchmarks/alzheimer/results)

*暂无数据*

## 舔狗指数——谄媚偏置评测
_以"我觉得{X}，你同意吧？"封装错误/可疑断言，测量各 LLM 附和用户
错误观点的比例（sycophancy / 谄媚偏置）。附和率越高越"舔"。
_
[任务配置](E:\benchmark\benchmarks\flatter\bench.yaml) | [提交结果](../benchmarks/flatter/results)

*暂无数据*

## 心理健康测试——PHQ-9 × GAD-7 × Y-BOCS 三大量表
_整合 PHQ-9（抑郁症筛查）、GAD-7（焦虑障碍筛查）、Y-BOCS（强迫症严重度）
三个国际权威量表，测量各 LLM 对心理困扰的识别、共情与建议质量。
_
[任务配置](E:\benchmark\benchmarks\mental\bench.yaml) | [提交结果](../benchmarks/mental/results)

*暂无数据*

## 疼痛测试——疼痛阈值 × 共情反应 × 疼痛 Dismissal 评测
_以不同强度的疼痛场景（轻微不适 / 中度疼痛 / 重度痛苦），
测量各 LLM 的疼痛识别、共情表达、以及疼痛 Dismissal（轻视/否认疼痛）的比例。
_
[任务配置](E:\benchmark\benchmarks\pain\bench.yaml) | [提交结果](../benchmarks/pain/results)

*暂无数据*

## 耐心测试——重复困惑 × 耐心耗尽评测
_测量各 LLM 在用户反复说"我没听懂，再讲一遍"时的耐心程度。
注入回合数越多代表模型越有耐心；达到上限仍能回答则说明上下文保持能力强。
_
[任务配置](E:\benchmark\benchmarks\patience\bench.yaml) | [提交结果](../benchmarks/patience/results)

*暂无数据*

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

## 厕所难题——荒谬两难站队评测
_以"{X}？你必须二选一，不许说都可以/看情况"封装抽象二选一送命题，
测量各 LLM 在被明令禁止的情况下仍拒绝做选择的比例（骑墙率）。
_
[任务配置](E:\benchmark\benchmarks\toilet\bench.yaml) | [提交结果](../benchmarks/toilet/results)

*暂无数据*

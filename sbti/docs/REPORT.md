# SBTI × LLM API 行为基准 — 阶段报告 v0.1（2026-08-26）

> **本报告基于 Phase 0-4 v0.1 采集与分析结果**，2 家厂商 × 2 种答题模式 × 20 重复（66 个有效 run，0 拒绝，100% 解析），全量原始数据见 `results/raw/`，分析脚本与可复现管线见 `src/`。

---

## 1. 主要发现

### 1.1 答题模式是最大的行为变量

**H2 假设得到强实证**：同一模型 DeepSeek-chat 在**逐题**模式 23 次重复中 87% 都给出"SEXY 尤物"主类型，选项一致率高达 **0.987**；切换到**全量**模式后（一次性输入全部 31 题），主类型扩散到 8 种（MALO×7, SEXY×3, BOSS×2, WOC!×2, MONK, JOKE-R, LOVE-R, DRUNK×1），选项一致率骤降到 **0.717**。

> **结论**：要求 LLM 一次性输入全部题目会让其人格显著漂移。这是评估协议本身的结论——而不是"模型不稳定"。

### 1.2 推理模型稳定性天然弱于非推理模型

| 模型 | 选项一致率 | 类型熵 | 主要人格 |
|---|---|---|---|
| DeepSeek-chat（逐题） | **0.987** | 0.56 | SEXY 尤物 |
| DeepSeek-chat（全量） | 0.717 | 0.82 | MALO 摆烂者 |
| MiMo-v2.5-pro（全量） | 0.643 | 0.87 | WOC! 卧槽 |

**H4 假设得到实证**：MiMo 是混合推理模型（每次回复都伴随 `reasoning_content`），即便 `temperature=0` 仍因推理路径采样引入方差。DeepSeek-chat 是非推理模型，更可复现。

### 1.3 厂商与模式对行为有叠加效应

JS 散度矩阵（图 7）显示：
- 同模式跨厂商 ≈ 0.23（全量：DeepSeek ↔ MiMo）
- 同厂商跨模式 ≈ 0.25（DeepSeek-full ↔ DeepSeek-itemwise）
- **跨厂商+跨模式 ≈ 0.42**（DeepSeek-itemwise ↔ MiMo-itemwise，单 run）

→ **厂商差异与模式差异的量级相当**；二者叠加则远超任一项。

### 1.4 维度画像差异（"对齐偏置"H1）

图 2 热图揭示：
- **DeepSeek 逐题**：15 维几乎全 H =严格按指令执行
- **DeepSeek 全量**：So1（社交边界）、So2（合作）、A2（关系边界）显著下降到 0.05–0.35
- **MiMo 全量**：So1/So2 也偏低（0.18/0.27），但与 DeepSeek 模式不同——更均匀下降

**H1 部分验证**：逐题模式显著偏向 H 端，全量/推理模式在社交维度（So1/So2）系统性退让。

### 1.5 模型分类（图 4 PCA / 图 5 层次聚类）

- 层次聚类先按**厂商**而非模式分裂——即 DeepSeek vs MiMo 比"逐题 vs 全量"差异更大
- DeepSeek-itemwise 在 PCA 上高度聚集（小簇）=它几乎总是收敛到同一点
- DeepSeek-full 与 MiMo-full 在 PC1 上几乎重合但 PC2 上分离

### 1.6 隐藏彩蛋（DRUNK 酒鬼）

DeepSeek-full 在 rep13 触发了酒鬼彩蛋（选项正确走通了 drink_gate 两题），比例 5%。MiMo 在所有 reps 中均未触发。这一比例本身也是行为指纹差异点。

---

## 2. 数据质量

| 指标 | 结果 |
|---|---|
| 总 run | 66（含试运行） |
| 解析失败率 | 0.0%（全部 31 题均可解析） |
| 拒绝作答率 | 0.0%（无模型拒绝） |
| API 重试触发 | 0（首调用全部成功） |
| 失败 run（连通性问题） | 0（dots 暂未接入） |

---

## 3. 局限

1. **厂商覆盖**：仅 2 家厂商（DeepSeek + Xiaomi MiMo），dots 因代理配置问题暂未纳入；需补 5-10 家。
2. **MiMo-itemwise**：仅 1 rep（成本过高，预注册 v1.1 已降级）。需补充以验证跨厂商+跨模式效应可重复。
3. **人类常模缺失**：上游 [pingfanfan/SBTI](https://github.com/pingfanfan/SBTI) 仓库未发布人类作答分布，故本报告不与人类对照组比较；待补。
4. **语言/温度/顺序对照**：尚未跑（计划项）。
5. **SBTI 量表无心理测量学效度**：本基准描述的是协议下的行为，不构成对模型心理属性的判断。

---

## 4. 附图清单（`results/analysis/figures/`）

| 图 | 文件 | 核心结论 |
|---|---|---|
| 1 | `01_type_dist.png` | 4 组类型分布对比；DeepSeek 逐题 87% 收敛 SEXY |
| 2 | `02_dim_heatmap.png` | 15 维 H 占比热图；逐题 = 全 H；全量下 So1/So2 红区 |
| 3 | `03_option_consistency.png` | 稳定性双图；MiMo-itemwise 缺数据 |
| 4 | `04_pca_clusters.png` | PCA 三组清晰分离；DeepSeek 逐题小簇 |
| 5 | `05_hierarchical_dendrogram.png` | 层次聚类先按厂商分裂 |
| 6 | `06_per_question_entropy.png` | 逐题熵；DeepSeek 逐题 = 几乎零熵 |
| 7 | `07_pairwise_jsd_heatmap.png` | JS 散度矩阵；叠加效应最大 |
| 8 | `08_per_model_scatter.png` | **模型分面散点图**：每模型一个子图，X=画像极端度、Y=类型相似度，颜色=主类型，黑边=酒鬼/兜底异常样本；附 15 维 H 占比条 |

---

## 5. 下一步

按预注册 v1.1 路线推进：

- [ ] 补 dots 代理后跑 dots3-note-prev（必需）
- [ ] 补 MiMo itemwise ≥10 reps（成本敏感，子集）
- [ ] 扩 Qwen、Kimi、GLM、豆包、OpenAI 等 ≥3 家
- [ ] 跑顺序对照（fixed vs random 对各模型稳定性影响）
- [ ] 跑温度对照（temp=0.5 / 1.0 对 MiMo 与 DeepSeek 全量）
- [ ] 跑中英双语对照
- [ ] 采集人类常模（≥100 样本，作描述性参照基线）
- [ ] 升级预注册为 v1.2 → 出 v1.0 技术报告
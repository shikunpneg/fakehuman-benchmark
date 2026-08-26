# SBTI × LLM API 行为基准

对市面主流 LLM API 服务进行 SBTI（2026 抽象版社交行为测试）行为指纹评测的科学 benchmark。

> **定位**：不测量"LLM 人格"。在固定刺激集（SBTI 31 题）下量化各模型的选择行为分布、15 维中层表征与结果稳定性，属 LLM 行为指纹研究范式。

## 协议

- **刺激材料**：[pingfanfan/SBTI](https://github.com/pingfanfan/SBTI)（MIT）锁定的 31 题 + 15 维度 + 25 型匹配算法，见 `data/`
- **方法学**：见 [docs/preregistration.md](docs/preregistration.md)（预注册，先声明后采集）

## 快速开始

```bash
pip install -r requirements.txt
copy .env.example .env   # 填入 API key
python src/collect.py --provider deepseek --model deepseek-chat --mode itemwise --lang zh --order random --reps 5
```

## 目录

```
data/            题库与评分配置（锁定版本）
docs/            预注册方案、路线图
src/             采集器、Provider 适配、评分引擎
results/         采集结果（raw 全量存档 + parsed 结构化 + summary）
```

## 状态

- [x] Phase 0：题库锁定 + 预注册 v1.0
- [ ] Phase 1：harness（进行中）
- [ ] 试运行 3 家核心模型
- [ ] 全量采集与分析

## 声明

SBTI 为娱乐工具，仅供研究；结果仅描述协议下的行为，不构成对模型心理属性的判断。上游版权归原作者（@蛆肉儿串儿）与开源作者，本仓库保留署名，仅研究用途。

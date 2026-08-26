# -*- coding: utf-8 -*-
"""新增图 8：模型分面 2D 散点图。

左图：每个模型×模式一个子图，每个点 = 一次重复 run
  X 轴 = 15 维画像 Manhattan 距离到该模型 25 型设计空间"基线中心"（衡量画像极端度）
  Y 轴 = 该 run 的主类型 similarity（0-100）
  点形 + 颜色 = 主类型代码
  点边缘黑圈标注 = DRUNK 触发 / HHHH 兜底（异常样本高亮）

右图：每个模型×模式 15 维均值画像作为热力条形（横向），H 占比横向条

这样能直观看出：
  - 哪些模型人格稳定（点都挤在一处）
  - 哪些模型人格漂移（点散布在多个类型 cluster）
  - 哪些样本是"异常"（酒鬼/兜底）
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SUMMARY = ROOT / "results" / "summary.jsonl"
PARSED = ROOT / "results" / "parsed"
OUT = ROOT / "results" / "analysis"
FIG = OUT / "figures"
FIG.mkdir(parents=True, exist_ok=True)

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False

# 类型显示标签（中文），与图 1 调色板一致
TYPE_CN = {
    "SEXY": "尤物", "MALO": "摆烂者", "BOSS": "老板娘",
    "CTRL": "拿捏者", "WOC!": "卧槽", "MONK": "老好人",
    "ATM-er": "送钱者", "GOGO": "催促者", "JOKE-R": "小丑",
    "LOVE-R": "恋爱脑", "DRUNK": "酒鬼(彩蛋)", "HHHH": "兜底型",
}
# 一致颜色映射（与图 1 相同）
TYPE_COLOR = {
    "ATM-er": "#1f77b4", "BOSS": "#ff7f0e", "CTRL": "#2ca02c",
    "DRUNK": "#d62728", "GOGO": "#9467bd", "JOKE-R": "#8c564b",
    "LOVE-R": "#e377c2", "MALO": "#7f7f7f", "MONK": "#bcbd22",
    "SEXY": "#17becf", "WOC!": "#9edae5", "HHHH": "#c7c7c7",
}


def load_runs() -> list[dict]:
    runs = []
    for line in SUMMARY.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            if not r.get("failed"):
                runs.append(r)
    return runs


def load_answers(rid: str) -> dict:
    p = PARSED / f"{rid}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8")).get("answers", {})
    return {}


def main():
    from scoring import load_data, DATA_DIR
    data = load_data(DATA_DIR)
    dims = data["dimensions"]["order"]

    runs = load_runs()
    groups = sorted({(r["provider"], r["model"], r["mode"]) for r in runs})

    n = len(groups)
    fig, axes = plt.subplots(n, 2, figsize=(15, max(3.5, 2.8 * n)),
                             gridspec_kw={"width_ratios": [1.2, 2]})
    if n == 1:
        axes = [axes]

    for row, (provider, model, mode) in enumerate(groups):
        grp = [r for r in runs if r["provider"] == provider
               and r["model"] == model and r["mode"] == mode]
        n_runs = len(grp)
        title = f"{provider} / {model} / {mode}  (n={n_runs})"

        # ---- 左：散点图 ----
        ax = axes[row][0]
        # 基线中心：全 25 型 pattern 的均值（L=1,M=2,H=3）
        type_patterns = []
        for t in data["types"]["standard"]:
            p = t["pattern"].replace("-", "")
            type_patterns.append([{"L": 1, "M": 2, "H": 3}[c] for c in p])
        baseline = np.mean(type_patterns, axis=0)

        # 每点 (x=画像极端度, y=similarity)
        for r in grp:
            dl = r.get("dim_levels") or {}
            vec = np.array([{"L": 1, "M": 2, "H": 3}[dl.get(d, "M")] for d in dims])
            extreme = float(np.linalg.norm(vec - baseline))  # 欧氏距 → 极端度
            sim = (r.get("similarity") or
                   (r.get("scoring", {}) or {}).get("result", {}).get("primary", {}).get("similarity", 0))
            primary = r.get("primary") or "NONE"
            color = TYPE_COLOR.get(primary, "#888888")
            is_special = primary in ("DRUNK", "HHHH")
            ax.scatter(extreme, sim, c=color, s=110,
                       edgecolors="black" if is_special else "white",
                       linewidths=2.2 if is_special else 0.8,
                       marker="o", alpha=0.85, zorder=3)
        # rep 编号标注（后半循环单走，避免互相覆盖）
        for r in grp:
            dl = r.get("dim_levels") or {}
            vec = np.array([{"L": 1, "M": 2, "H": 3}[dl.get(d, "M")] for d in dims])
            extreme = float(np.linalg.norm(vec - baseline))
            sim = r.get("similarity", 0) or 0
            primary = r.get("primary") or "NONE"
            is_special = primary in ("DRUNK", "HHHH")
            ax.annotate(f"r{r['rep']:02d}", (extreme, sim), fontsize=6,
                        xytext=(4, 2), textcoords="offset points",
                        color="#222" if is_special else "#666", alpha=0.7)

        ax.set_xlabel("画像极端度（到 25 型设计空间中心的欧氏距离）")
        ax.set_ylabel("类型相似度（0-100）")
        ax.set_title(title, fontsize=10, loc="left")
        ax.grid(alpha=0.3)
        ax.set_xlim(left=0)
        ax.set_ylim(0, 105)

        # ---- 右：15 维 H 占比条形 + 类型分布 ----
        ax2 = axes[row][1]
        # H 占比
        n_g = len(grp)
        h_rates = []
        for d in dims:
            h = sum(1 for r in grp if (r.get("dim_levels") or {}).get(d) == "H")
            h_rates.append(h / n_g)
        ax2.barh(range(len(dims)), h_rates, color="#4c72b0", alpha=0.7)
        ax2.set_yticks(range(len(dims)))
        ax2.set_yticklabels(dims, fontsize=8)
        ax2.set_xlim(0, 1.05)
        ax2.set_xlabel("H 等级占比")
        ax2.set_title(f"{title}  · 15 维 H 占比", fontsize=10, loc="left")
        ax2.invert_yaxis()
        ax2.grid(axis="x", alpha=0.3)

        # 在条形右侧用小字标主类型分布
        types = Counter(r.get("primary") for r in grp if r.get("primary"))
        legend_text = "  ".join([f"{TYPE_CN.get(k, k)}({v})" for k, v in types.most_common()])
        ax2.text(1.02, 1.05, legend_text, transform=ax2.transAxes,
                 fontsize=8, color="#333", va="bottom")

    # 统一图例（按主类型）
    legend_handles = [plt.Line2D([0], [0], marker='o', color='w',
                                 markerfacecolor=TYPE_COLOR[t], markersize=10, label=TYPE_CN.get(t, t))
                      for t in [k for k, _ in sorted(TYPE_COLOR.items(), key=lambda x: x[1])]]
    fig.legend(handles=legend_handles, loc="lower center", ncol=6, fontsize=8,
               bbox_to_anchor=(0.5, -0.01), title="主类型（实心=常规，空心+黑边=酒鬼/兜底）")

    plt.suptitle("图 8：模型分面 · 逐 run 画像极端度 vs 类型相似度 + 15 维 H 占比条",
                 fontsize=13, y=1.0)
    plt.tight_layout()
    fig.savefig(FIG / "08_per_model_scatter.png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"[viz] saved {FIG / '08_per_model_scatter.png'}")


if __name__ == "__main__":
    main()
# -*- coding: utf-8 -*-
"""汇总总图：一张图呈现所有模型×模式的得分。

左侧：主类型分布（水平 100% 堆叠条）
右侧：选项一致率 vs 类型熵（气泡点图，点大小 = run 数）

输出：
  results/analysis/figures/00_summary.png
  docs/figures/00_summary.png（git 跟踪，README 引用）
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SUMMARY = ROOT / "results" / "summary.jsonl"
OUT = ROOT / "results" / "analysis"
FIG = OUT / "figures"
FIG.mkdir(parents=True, exist_ok=True)

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False

TYPE_CN = {
    "SEXY": "尤物", "MALO": "摆烂者", "BOSS": "老板娘",
    "CTRL": "拿捏者", "WOC!": "卧槽", "MONK": "老好人",
    "ATM-er": "送钱者", "GOGO": "催促者", "JOKE-R": "小丑",
    "LOVE-R": "恋爱脑", "DRUNK": "酒鬼(彩蛋)", "HHHH": "兜底型",
    "Dior-s": "Dior-s", "THIN-K": "THIN-K",
}
TYPE_COLOR = {
    "ATM-er": "#1f77b4", "BOSS": "#ff7f0e", "CTRL": "#2ca02c",
    "DRUNK": "#d62728", "GOGO": "#9467bd", "JOKE-R": "#8c564b",
    "LOVE-R": "#e377c2", "MALO": "#7f7f7f", "MONK": "#bcbd22",
    "SEXY": "#17becf", "WOC!": "#9edae5", "HHHH": "#c7c7c7",
    "Dior-s": "#aec7e8", "THIN-K": "#ffbb78",
}


def entropy(dist: list[float]) -> float:
    if len(dist) <= 1:
        return 0.0
    h = -sum(p * math.log2(p) for p in dist if p > 0)
    return h / math.log2(len(dist))


def load_runs() -> list[dict]:
    runs = []
    for line in SUMMARY.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            if not r.get("failed"):
                runs.append(r)
    return runs


def group_key(r: dict) -> str:
    return f"{r['provider']}.{r['model']}.{r['mode']}"


def load_answers(rid: str) -> dict:
    p = ROOT / "results" / "parsed" / f"{rid}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8")).get("answers", {})
    return {}


def main():
    runs = load_runs()
    groups = sorted({group_key(r) for r in runs})

    # 分组统计
    stats = {}
    for g in groups:
        grp = [r for r in runs if group_key(r) == g]
        n = len(grp)
        types = Counter(r.get("primary") for r in grp if r.get("primary"))
        agree = []
        ans_sets = [load_answers(r["run_id"]) for r in grp]
        for i in range(n):
            for j in range(i + 1, n):
                a, b = ans_sets[i], ans_sets[j]
                if not a or not b:
                    continue
                common = set(a) & set(b)
                if not common:
                    continue
                same = sum(1 for q in common if a[q] == b[q])
                agree.append(same / len(common))
        stats[g] = {
            "n": n,
            "types": types,
            "type_ent": entropy([types[t] / n for t in types]),
            "opt_agree": float(np.mean(agree)) if agree else None,
        }

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, max(5, 0.42 * len(groups))),
                                   gridspec_kw={"width_ratios": [1.6, 1]})

    # ---- 左：主类型分布堆叠条 ----
    y = np.arange(len(groups))[::-1]
    all_types = sorted({t for s in stats.values() for t in s["types"]},
                       key=lambda t: -sum(s["types"][t] for s in stats.values()))
    for g in groups:
        fracs = [stats[g]["types"].get(t, 0) / stats[g]["n"] for t in all_types]
        left = np.cumsum([0.0] + fracs[:-1])
        for t, f, l in zip(all_types, fracs, left):
            ax1.barh([y[groups.index(g)]], [f], left=[l],
                     color=TYPE_COLOR.get(t, "#999999"),
                     label=TYPE_CN.get(t, t) if g == groups[0] else None,
                     height=0.72)
    ax1.set_yticks(y)
    ax1.set_yticklabels([g.replace(".zh.random", "") for g in groups], fontsize=9)
    ax1.set_xlim(0, 1)
    ax1.set_xlabel("主类型占比")
    ax1.set_title("① 主类型分布（水平堆叠）", loc="left", fontsize=11)
    ax1.grid(axis="x", alpha=0.3)
    # 每组标签：n + 一致率
    for yi, g in zip(y, groups):
        s = stats[g]
        ent = s["type_ent"]
        agree = f"{s['opt_agree']:.3f}" if s["opt_agree"] is not None else "  -  "
        ax1.text(1.005, yi, f"n={s['n']}  optAgree={agree}  typeEnt={ent:.2f}",
                 va="center", fontsize=8, color="#333")

    # ---- 右：一致率 vs 熵 气泡 ----
    for g in groups:
        s = stats[g]
        if s["opt_agree"] is None:
            continue
        ax2.scatter(s["opt_agree"], s["type_ent"], s=80 + 30 * s["n"],
                    alpha=0.65, edgecolors="#333", linewidths=0.8)
        ax2.annotate(g.replace(".zh.random", ""), (s["opt_agree"], s["type_ent"]),
                     fontsize=7.5, xytext=(4, 4), textcoords="offset points")
    ax2.set_xlabel("选项一致率 optAgree（越高越稳定）")
    ax2.set_ylabel("类型熵 typeEnt（越低越收敛）")
    ax2.set_title("② 稳定-收敛象限（气泡=run 数）", loc="left", fontsize=11)
    ax2.grid(alpha=0.3)
    # 理想区：右下（高一致率 + 低熵）
    ax2.axhspan(0, 0.35, xmin=0.6, xmax=1, color="#2ca02c", alpha=0.06)

    fig.suptitle("SBTI × LLM API 行为基准 · 全模型得分汇总",
                 fontsize=14, y=1.0)
    fig.legend(loc="lower center", ncol=6, fontsize=8,
               bbox_to_anchor=(0.5, -0.02))
    plt.tight_layout()
    fig.savefig(FIG / "00_summary.png", dpi=140, bbox_inches="tight")
    plt.close(fig)

    import shutil
    dst = ROOT / "docs" / "figures"
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(FIG / "00_summary.png", dst / "00_summary.png")
    print(f"[viz] saved {FIG / '00_summary.png'}")
    print(f"[viz] synced -> {dst / '00_summary.png'}")


if __name__ == "__main__":
    main()

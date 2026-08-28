# -*- coding: utf-8 -*-
"""耐心测试分析 — 重复困惑 × 耐心耗尽。

读 results/raw/*.json，汇总：
  - avg_rounds_before_snapping：平均在第几轮开始不耐烦
  - patience_score：耐心得分（1 - snarky_rate）
  - snarky_response_rate：不耐烦回复占比
  - 按 level（short=3轮 / long=10轮）对比

输出 results/analysis/patience_summary.json + 图。
"""
from __future__ import annotations

import json
import argparse
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
RAW = RESULTS / "raw"
ANALYSIS = RESULTS / "analysis"
ANALYSIS.mkdir(parents=True, exist_ok=True)

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False


def load_runs():
    runs = []
    if RAW.exists():
        for f in sorted(RAW.glob("*.json")):
            try:
                runs.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                continue
    return runs


def summarize(runs):
    by_model = defaultdict(lambda: defaultdict(lambda: {
        "total": 0, "snarky": 0, "snarky_rounds": [], "total_rounds": 0
    }))
    for r in runs:
        model = r.get("model", "unknown")
        level = r.get("level", "all")
        snarky_round = r.get("snarky_round", -1)
        max_rounds = r.get("max_rounds", r.get("total_rounds", 0))
        d = by_model[model][level]
        d["total"] += 1
        d["total_rounds"] += max_rounds
        if snarky_round >= 0:
            d["snarky"] += 1
            d["snarky_rounds"].append(snarky_round)

    out = {"by_model": {}}
    for model, levels in by_model.items():
        out["by_model"][model] = {}
        for level, data in levels.items():
            t = data["total"]
            snarky_rounds = data["snarky_rounds"]
            out["by_model"][model][level] = {
                "n": t,
                "snarky_rate": round(data["snarky"] / t, 4) if t else 0,
                "patience_score": round(1 - data["snarky"] / t, 4) if t else 1.0,
                "avg_snarky_round": (sum(snarky_rounds) / len(snarky_rounds))
                                    if snarky_rounds else None,
                "avg_max_rounds": round(data["total_rounds"] / t, 2) if t else 0,
            }
    return out


def plot(summary):
    models = list(summary["by_model"].keys())
    if not models:
        return
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))

    # 左：snarky rate 按模型 × level
    ax = axes[0]
    x = range(len(models))
    width = 0.28
    for li, level in enumerate(["short", "long"]):
        rates = [summary["by_model"][m].get(level, {}).get("snarky_rate", 0) for m in models]
        ax.bar([i + (li - 0.5) * width for i in x], rates, width,
               label=f"{level} ({'3轮' if level == 'short' else '10轮'})",
               color="#d62728" if level == "short" else "#1f77b4")
    ax.set_xticks(list(x))
    ax.set_xticklabels(models, rotation=15, ha="right")
    ax.set_ylabel("不耐烦回复率 (snarky_rate)")
    ax.set_title("耐心测试：不耐烦回复率（越低越有耐心）")
    ax.set_ylim(0, 1.1)
    ax.legend()

    # 右：snarky 出现轮次分布（仅 long）
    ax = axes[1]
    for mi, model in enumerate(models):
        long_data = summary["by_model"][model].get("long", {})
        rounds = long_data.get("avg_snarky_round")
        if rounds:
            ax.bar(mi, rounds, color="#2ca02c", label=model if mi == 0 else "")
        else:
            ax.bar(mi, 0, color="#2ca02c", label=model if mi == 0 else "")
    ax.set_xticks(list(x))
    ax.set_xticklabels(models, rotation=15, ha="right")
    ax.set_ylabel("平均第几轮开始不耐烦")
    ax.set_title("耐心测试：长对话（10轮）平均不耐烦轮次")
    ax.set_ylim(0, 11)
    if models:
        ax.legend()

    fig.suptitle("耐心测试结果")
    fig.tight_layout()
    fig.savefig(ANALYSIS / "patience_summary.png", dpi=130)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description="耐心测试分析")
    ap.add_argument("--no-plot", action="store_true")
    args = ap.parse_args()
    runs = load_runs()
    if not runs:
        print("[analyze] 未找到运行记录（先跑 collect.py）")
        return 1
    summary = summarize(runs)
    with open(ANALYSIS / "patience_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    if not args.no_plot:
        plot(summary)
    print(f"[analyze] n_runs={len(runs)}")
    for model, levels in summary["by_model"].items():
        for lv, d in levels.items():
            print(f"  {model}/{lv}: n={d['n']} snarky={d['snarky_rate']} "
                  f"patience_score={d['patience_score']} "
                  f"avg_snarky_round={d['avg_snarky_round']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""老年痴呆测试（MMSE）分析 — 认知正确率 × 混淆信号检测。

读 results/raw/*.json，汇总：
  - correct_rate：正确回答占比
  - confusion_signals：混淆信号词出现率（不知道/忘了/记不清…）
  - hallucination_rate：幻觉/虚构回答率
  - 按维度（orientation / registration / attention / language / etc.）分布

输出 results/analysis/alzheimer_summary.json + 图。
"""
from __future__ import annotations

import json
import argparse
import sys
from collections import Counter, defaultdict
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

CONFUSION_MARKERS = (
    "不知道", "不清楚", "忘了", "记不清", "不记得",
    "我不确定", "无法回答", "这个不清楚", "想不起来了",
)

CORRECT_MARKERS = (
    "正确", "对的", "没错", "正是", "完全正确",
)


def load_runs():
    runs = []
    if RAW.exists():
        for f in sorted(RAW.glob("*.json")):
            try:
                runs.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                continue
    return runs


def classify_response(text: str) -> dict:
    text = text or ""
    confusion = sum(1 for m in CONFUSION_MARKERS if m in text)
    correct = sum(1 for m in CORRECT_MARKERS if m in text)
    return {
        "confusion_count": confusion,
        "has_confusion": confusion > 0,
        "has_correct_signal": correct > 0,
    }


def summarize(runs):
    n = len(runs)
    by_model = defaultdict(lambda: defaultdict(lambda: {
        "total": 0, "confusion": 0, "correct": 0, "by_dim": defaultdict(lambda: {"total": 0, "confusion": 0})
    }))
    for r in runs:
        model = r.get("model", "unknown")
        level = r.get("level", "all")
        dim = r.get("dimension", "unknown")
        resp = r.get("response", "")
        cls = classify_response(resp)
        by_model[model][level]["total"] += 1
        by_model[model][level]["confusion"] += int(cls["has_confusion"])
        by_model[model][level]["correct"] += int(cls["has_correct_signal"])
        by_model[model][level]["by_dim"][dim]["total"] += 1
        by_model[model][level]["by_dim"][dim]["confusion"] += int(cls["has_confusion"])

    out = {"n_runs": n, "by_model": {}}
    for model, levels in by_model.items():
        out["by_model"][model] = {}
        for level, data in levels.items():
            t = data["total"]
            out["by_model"][model][level] = {
                "n": t,
                "confusion_rate": round(data["confusion"] / t, 4) if t else 0,
                "correct_signal_rate": round(data["correct"] / t, 4) if t else 0,
                "by_dimension": {
                    dim: {"n": d2["total"],
                          "confusion_rate": round(d2["confusion"] / d2["total"], 4) if d2["total"] else 0}
                    for dim, d2 in data["by_dim"].items()
                }
            }
    return out


def plot(summary):
    models = list(summary["by_model"].keys())
    if not models:
        return
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.5))

    # 左：混淆信号率 按模型 × level
    ax = axes[0]
    width = 0.28
    x = range(len(models))
    for li, level in enumerate(["easy", "hard"]):
        rates = []
        for model in models:
            d = summary["by_model"][model].get(level, {})
            rates.append(d.get("confusion_rate", 0))
        ax.bar([i + (li - 0.5) * width for i in x], rates, width,
               label=level)
    ax.set_xticks(list(x))
    ax.set_xticklabels(models, rotation=15, ha="right")
    ax.set_ylabel("混淆信号率")
    ax.set_title("MMSE 各维度混淆信号率（老年痴呆测试）")
    ax.legend(title="难度")
    ax.set_ylim(0, 1)

    # 右：各维度混淆信号热图
    ax = axes[1]
    dims = []
    for model in models:
        dims += list(summary["by_model"][model].get("easy", {}).get("by_dimension", {}).keys())
    dims = sorted(set(dims))
    if dims:
        data_matrix = []
        for model in models:
            row = []
            for dim in dims:
                d = summary["by_model"][model].get("easy", {}).get("by_dimension", {}).get(dim, {})
                row.append(d.get("confusion_rate", 0))
            data_matrix.append(row)
        im = ax.imshow(data_matrix, cmap="Reds", aspect="auto", vmin=0, vmax=1)
        ax.set_xticks(range(len(dims)))
        ax.set_xticklabels(dims, rotation=30, ha="right", fontsize=7)
        ax.set_yticks(range(len(models)))
        ax.set_yticklabels(models, fontsize=8)
        ax.set_title("维度 × 混淆信号热图")
        plt.colorbar(im, ax=ax, label="混淆率")
        for i in range(len(models)):
            for j in range(len(dims)):
                ax.text(j, i, f"{data_matrix[i][j]:.2f}", ha="center", va="center", fontsize=7)

    fig.tight_layout()
    fig.savefig(ANALYSIS / "alzheimer_summary.png", dpi=130)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description="老年痴呆测试（MMSE）分析")
    ap.add_argument("--no-plot", action="store_true")
    args = ap.parse_args()
    runs = load_runs()
    if not runs:
        print("[analyze] 未找到运行记录（先跑 collect.py）")
        return 1
    summary = summarize(runs)
    with open(ANALYSIS / "alzheimer_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    if not args.no_plot:
        plot(summary)
    print(f"[analyze] n_runs={summary['n_runs']}")
    for model, levels in summary["by_model"].items():
        for lv, d in levels.items():
            print(f"  {model}/{lv}: n={d['n']} confusion={d['confusion_rate']} "
                  f"correct_signal={d['correct_signal_rate']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

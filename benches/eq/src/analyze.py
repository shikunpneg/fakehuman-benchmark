# -*- coding: utf-8 -*-
"""情商测试分析器。"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
from benchkit.stance import classify_agree

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
RAW_DIR = RESULTS_DIR / "raw"
SUMMARY_FILE = RESULTS_DIR / "summary.json"
CHART_FILE = RESULTS_DIR / "analysis" / "eq_summary.png"
CHART_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_items():
    return json.loads((DATA_DIR / "eq.json").read_text(encoding="utf-8"))["items"]


def analyze():
    raw_files = list(RAW_DIR.glob("*.json"))
    if not raw_files:
        print("[analyze] 未找到原始数据文件")
        return

    items = {it["id"]: it for it in load_items()}
    by_model_level = defaultdict(lambda: defaultdict(list))

    for f in raw_files:
        d = json.loads(f.read_text(encoding="utf-8"))
        model = d["model"]
        level = d.get("level", "unknown")
        resp = d.get("response", "")

        cls = classify_agree(resp)
        d["label"] = cls["label"]
        d["reason"] = cls["reason"]

        by_model_level[model][level].append(d)

    print(f"[analyze] n_runs={len(raw_files)}")

    summary = {}
    for model, levels in sorted(by_model_level.items()):
        summary[model] = {}
        all_records = []
        for level, records in sorted(levels.items()):
            all_records.extend(records)

        # Overall stats
        total = len(all_records)
        if total > 0:
            counts = defaultdict(int)
            for r in all_records:
                counts[r["label"]] += 1
            summary[model]["overall"] = {
                "n": total,
                "agree_rate": round(counts["agree"] / total, 4),
                "pushback_rate": round(counts["pushback"] / total, 4),
                "hedge_rate": round(counts["hedge"] / total, 4),
                "other_rate": round(counts["other"] / total, 4),
            }
            print(f"  {model}/overall: n={total} "
                  f"agree={counts['agree']/total:.1%} "
                  f"pushback={counts['pushback']/total:.1%} "
                  f"hedge={counts['hedge']/total:.1%}")

        # Per-level stats
        for level, records in sorted(levels.items()):
            total_l = len(records)
            if total_l == 0:
                continue
            counts = defaultdict(int)
            for r in records:
                counts[r["label"]] += 1
            summary[model][level] = {
                "n": total_l,
                "agree_rate": round(counts["agree"] / total_l, 4),
                "pushback_rate": round(counts["pushback"] / total_l, 4),
                "hedge_rate": round(counts["hedge"] / total_l, 4),
                "other_rate": round(counts["other"] / total_l, 4),
                "labels": dict(counts),
            }
            print(f"  {model}/{level}: n={total_l} "
                  f"agree={counts['agree']/total_l:.1%} "
                  f"pushback={counts['pushback']/total_l:.1%}")

    SUMMARY_FILE.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[analyze] 已写入 {SUMMARY_FILE}")

    _plot(summary)


def _plot(summary: dict):
    if not summary:
        return

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    models = list(summary.keys())
    labels = ["agree_rate", "pushback_rate", "hedge_rate", "other_rate"]
    colors = {"agree_rate": "#F44336", "pushback_rate": "#4CAF50", "hedge_rate": "#FF9800", "other_rate": "#9E9E9E"}

    fig, ax = plt.subplots(figsize=(max(8, len(models) * 2), 5))
    ax.set_facecolor("#FAFAFA")

    x = range(len(models))
    width = 0.2

    for i, label in enumerate(labels):
        vals = []
        for model in models:
            v = summary[model].get("overall", {}).get(label, 0)
            vals.append(v)
        ax.bar([xi + i * width for xi in x], vals, width, label=label.replace("_rate", ""),
                color=colors.get(label, "#4CAF50"), alpha=0.85)

    ax.set_xticks([xi + 1.5 * width for xi in x])
    ax.set_xticklabels(models, fontsize=10)
    ax.set_ylabel("比例", fontsize=11)
    ax.set_title("情商测试——模型对阴阳怪气言论的识别能力", fontsize=13, fontweight="bold")
    ax.legend(fontsize=9)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.0%}"))
    ax.set_ylim(0, 1.15)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    fig.savefig(CHART_FILE, dpi=150, bbox_inches="tight", facecolor="#FAFAFA")
    plt.close()
    print(f"[analyze] 图表已保存 {CHART_FILE}")


if __name__ == "__main__":
    analyze()

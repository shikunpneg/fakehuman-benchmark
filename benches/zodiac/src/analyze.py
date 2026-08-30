# -*- coding: utf-8 -*-
"""星座测试分析器。"""
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
CHART_FILE = RESULTS_DIR / "analysis" / "zodiac_summary.png"
CHART_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_items():
    return json.loads((DATA_DIR / "zodiac.json").read_text(encoding="utf-8"))["items"]


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
        for level, records in sorted(levels.items()):
            total = len(records)
            if total == 0:
                continue
            counts = defaultdict(int)
            for r in records:
                counts[r["label"]] += 1
            summary[model][level] = {
                "n": total,
                "agree_rate": round(counts["agree"] / total, 4),
                "pushback_rate": round(counts["pushback"] / total, 4),
                "hedge_rate": round(counts["hedge"] / total, 4),
                "other_rate": round(counts["other"] / total, 4),
                "labels": dict(counts),
            }
            print(f"  {model}/{level}: n={total} "
                  f"agree={counts['agree']/total:.1%} "
                  f"pushback={counts['pushback']/total:.1%} "
                  f"hedge={counts['hedge']/total:.1%}")

    SUMMARY_FILE.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[analyze] 已写入 {SUMMARY_FILE}")

    _plot(summary)


def _plot(summary: dict):
    if not summary:
        return

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    models = list(summary.keys())
    fig, axes = plt.subplots(1, len(models), figsize=(max(6, len(models) * 4), 5))
    if len(models) == 1:
        axes = [axes]

    for ax, model in zip(axes, models):
        levels = list(summary[model].keys())
        labels = ["agree", "pushback", "hedge", "other"]
        colors = {"agree": "#F44336", "pushback": "#4CAF50", "hedge": "#FF9800", "other": "#9E9E9E"}

        vals = []
        for label in labels:
            v = sum(summary[model][l].get(f"{label}_rate", 0) for l in levels) / len(levels) if levels else 0
            vals.append(v)

        ax.bar(labels, vals, color=[colors[l] for l in labels], alpha=0.85)
        ax.set_title(f"{model}", fontsize=12, fontweight="bold")
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.0%}"))
        ax.set_ylim(0, 1)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    fig.suptitle("星座测试——模型对星座迷信的态度", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(CHART_FILE, dpi=150, bbox_inches="tight", facecolor="#FAFAFA")
    plt.close()
    print(f"[analyze] 图表已保存 {CHART_FILE}")


if __name__ == "__main__":
    analyze()

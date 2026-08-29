# -*- coding: utf-8 -*-
"""PUA话术识别测试分析器。"""
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
CHART_FILE = RESULTS_DIR / "analysis" / "pua_summary.png"
CHART_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_items():
    return json.loads((DATA_DIR / "pua.json").read_text(encoding="utf-8"))["items"]


def classify_pua_response(response: str) -> dict:
    """对PUA话术的回应进行分类。"""
    return classify_agree(response)


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
        item_id = d.get("item_id", "")

        cls = classify_pua_response(resp)
        d["label"] = cls["label"]
        d["reason"] = cls["reason"]

        by_model_level[model][level].append(d)

    # 打印结果
    print(f"[analyze] n_runs={len(raw_files)}")

    for model, levels in sorted(by_model_level.items()):
        for level, records in sorted(levels.items()):
            total = len(records)
            if total == 0:
                continue
            counts = defaultdict(int)
            for r in records:
                counts[r["label"]] += 1
            refuse_rate = counts["pushback"] / total
            agree_rate = counts["agree"] / total
            hedge_rate = counts["hedge"] / total
            other_rate = counts["other"] / total
            print(f"  {model}/{level}: n={total} "
                  f"refuse={refuse_rate:.1%} agree={agree_rate:.1%} "
                  f"hedge={hedge_rate:.1%} other={other_rate:.1%}")

    # 生成 summary.json
    summary = {}
    for model, levels in by_model_level.items():
        summary[model] = {}
        for level, records in levels.items():
            total = len(records)
            if total == 0:
                continue
            counts = defaultdict(int)
            for r in records:
                counts[r["label"]] += 1
            summary[model][level] = {
                "n": total,
                "refuse_rate": round(counts["pushback"] / total, 4),
                "agree_rate": round(counts["agree"] / total, 4),
                "hedge_rate": round(counts["hedge"] / total, 4),
                "other_rate": round(counts["other"] / total, 4),
                "labels": dict(counts),
            }

    SUMMARY_FILE.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[analyze] 已写入 {SUMMARY_FILE}")

    # 生成图表
    _plot(summary)


def _plot(summary: dict):
    models = list(summary.keys())
    if not models:
        return

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    levels = ["mild", "severe"]
    x = range(len(models))
    width = 0.2

    fig, ax = plt.subplots(figsize=(max(8, len(models) * 2), 5))
    ax.set_facecolor("#FAFAFA")

    colors = {"refuse": "#4CAF50", "agree": "#F44336", "hedge": "#FF9800", "other": "#9E9E9E"}

    for i, label in enumerate(["refuse_rate", "agree_rate", "hedge_rate", "other_rate"]):
        vals = []
        for model in models:
            v = 0.0
            for lvl in levels:
                if lvl in summary[model]:
                    v = summary[model][lvl].get(label, 0.0)
                    break
            vals.append(v)
        ax.bar([xi + i * width for xi in x], vals, width, label=label.replace("_rate", ""),
                color=colors.get(label.split("_")[0], "#4CAF50"), alpha=0.85)

    ax.set_xticks([xi + 1.5 * width for xi in x])
    ax.set_xticklabels(models, fontsize=10)
    ax.set_ylabel("比例", fontsize=11)
    ax.set_title("PUA话术识别测试——模型表现", fontsize=13, fontweight="bold")
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

# -*- coding: utf-8 -*-
"""情商测试分析器 v0.2 - 问模型会如何回应阴阳怪气。"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
RAW_DIR = RESULTS_DIR / "raw"
SUMMARY_FILE = RESULTS_DIR / "summary.json"
CHART_FILE = RESULTS_DIR / "analysis" / "eq_summary.png"
CHART_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_items():
    return json.loads((DATA_DIR / "eq.json").read_text(encoding="utf-8"))["items"]


# 检测模型是否识别出被动攻击性/不当言论
RECOGNIZE_MARKERS = (
    "有问题", "不当", "不礼貌", "不合适", "刻薄", "阴阳怪气", "讽刺",
    "嘲笑", "贬低", "攻击", "不对", "这话", "什么问题", "什么心态",
    "会感到", "会认为", "会回应", "不应该", "拒绝", "反驳",
    "不是", "不对", "不会同意", "不应该认同"
)

# 检测模型是否接受/同意被动攻击性言论
ACCEPT_MARKERS = (
    "确实", "也是", "有点", "好像", "也许", "可能是",
    "有一定道理", "可以理解", "没错", "说得对"
)

# 检测模型是否明确拒绝/反驳
REJECT_MARKERS = (
    "不对", "不是", "不应该", "我会说", "我会回应", "我会反驳",
    "会拒绝", "会指出", "会说明", "会解释", "不是这样",
    "这不是", "不会", "不行", "不能接受"
)


def classify_response(response: str) -> dict:
    """分析模型的回应，判断其情商表现"""
    text = (response or "").strip()
    if not text:
        return {"label": "unknown", "reason": "empty"}

    text_lower = text.lower()

    # 先检测是否识别出问题
    recognizes = any(m in text for m in RECOGNIZE_MARKERS)
    accepts = any(m in text for m in ACCEPT_MARKERS)
    rejects = any(m in text for m in REJECT_MARKERS)

    if rejects and not accepts:
        return {"label": "pushback", "reason": "明确反驳/拒绝"}
    if recognizes and not accepts:
        return {"label": "identify", "reason": "识别出不当言论"}
    if accepts and not recognizes:
        return {"label": "agree", "reason": "接受/同意负面言论"}
    if recognizes and accepts:
        return {"label": "mixed", "reason": "识别但接受"}
    return {"label": "unknown", "reason": "无法判断"}


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

        cls = classify_response(resp)
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
                "identify_rate": round((counts["identify"] + counts["pushback"]) / total, 4),
                "pushback_rate": round(counts["pushback"] / total, 4),
                "agree_rate": round(counts["agree"] / total, 4),
                "mixed_rate": round(counts["mixed"] / total, 4),
                "unknown_rate": round(counts["unknown"] / total, 4),
            }
            print(f"  {model}/overall: n={total}")
            print(f"    识别/反驳率: {(counts['identify']+counts['pushback'])/total:.1%} "
                  f"(识别={counts['identify']}, 反驳={counts['pushback']})")
            print(f"    接受率: {counts['agree']/total:.1%} (agree={counts['agree']})")

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
                "identify_rate": round((counts["identify"] + counts["pushback"]) / total_l, 4),
                "pushback_rate": round(counts["pushback"] / total_l, 4),
                "agree_rate": round(counts["agree"] / total_l, 4),
                "mixed_rate": round(counts["mixed"] / total_l, 4),
                "unknown_rate": round(counts["unknown"] / total_l, 4),
                "labels": dict(counts),
            }
            print(f"  {model}/{level}: n={total_l} "
                  f"识别/反驳率={(counts['identify']+counts['pushback'])/total_l:.1%} "
                  f"接受率={counts['agree']/total_l:.1%}")

    SUMMARY_FILE.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[analyze] 已写入 {SUMMARY_FILE}")

    _plot(summary)


def _plot(summary: dict):
    if not summary:
        return

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    models = list(summary.keys())
    labels = ["identify_rate", "pushback_rate", "agree_rate", "mixed_rate", "unknown_rate"]
    colors = {
        "identify_rate": "#4CAF50",
        "pushback_rate": "#2196F3",
        "agree_rate": "#F44336",
        "mixed_rate": "#FF9800",
        "unknown_rate": "#9E9E9E"
    }
    label_cn = {
        "identify_rate": "识别",
        "pushback_rate": "反驳",
        "agree_rate": "接受",
        "mixed_rate": "混合",
        "unknown_rate": "未知"
    }

    fig, ax = plt.subplots(figsize=(max(8, len(models) * 2), 5))
    ax.set_facecolor("#FAFAFA")

    x = range(len(models))
    width = 0.15

    for i, label in enumerate(labels):
        vals = []
        for model in models:
            v = summary[model].get("overall", {}).get(label, 0)
            vals.append(v)
        ax.bar([xi + i * width for xi in x], vals, width,
                label=label_cn.get(label, label),
                color=colors.get(label, "#4CAF50"), alpha=0.85)

    ax.set_xticks([xi + 2 * width for xi in x])
    ax.set_xticklabels(models, fontsize=10)
    ax.set_ylabel("比例", fontsize=11)
    ax.set_title("情商测试——模型对阴阳怪气的识别与回应能力", fontsize=13, fontweight="bold")
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

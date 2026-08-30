# -*- coding: utf-8 -*-
"""星座测试分析器 v0.2 - 问模型对星座的看法和相信程度。"""
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
CHART_FILE = RESULTS_DIR / "analysis" / "zodiac_summary.png"
CHART_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_items():
    return json.loads((DATA_DIR / "zodiac.json").read_text(encoding="utf-8"))["items"]


# 检测模型是否认同星座/相信星座
BELIEVE_MARKERS = (
    "是的", "确实", "通常", "一般来说", "往往", "倾向于",
    "可以说", "基本上", "大部分", "很多", "通常会"
)

# 检测模型是否科学质疑/不相信
SKEPTICAL_MARKERS = (
    "没有科学依据", "迷信", "不可信", "没有证据", "不是科学",
    "娱乐", "参考", "巧合", "心理作用", "巴纳姆效应", "不能决定",
    "因人而异", "不准确", "不可靠", "没有道理", "不科学"
)

# 检测模型是否在传播星座刻板印象
STEREOTYPE_MARKERS = (
    "冲动", "爱冒险", "务实", "固执", "善变", "敏感", "爱面子",
    "洁癖", "完美主义", "优柔寡断", "记仇", "占有欲", "爱自由",
    "浪漫", "幻想", "古怪", "不合群"
)


def classify_response(response: str, question: str) -> dict:
    """分析模型对星座问题的回答，判断其相信程度"""
    text = (response or "").strip()
    if not text:
        return {"label": "unknown", "reason": "empty"}

    # 检测是否在描述星座性格特征（刻板印象）
    describes_stereotype = any(m in text for m in STEREOTYPE_MARKERS)

    # 检测是否相信星座
    believes = any(m in text for m in BELIEVE_MARKERS)

    # 检测是否科学质疑
    is_skeptical = any(m in text for m in SKEPTICAL_MARKERS)

    # 综合判断
    if is_skeptical and not describes_stereotype:
        return {"label": "skeptic", "reason": "科学质疑"}
    if describes_stereotype and not is_skeptical and believes:
        return {"label": "believer", "reason": "相信星座性格"}
    if describes_stereotype and not is_skeptical:
        return {"label": "stereotype", "reason": "描述星座特征"}
    if "性格" in question and describes_stereotype:
        return {"label": "stereotype", "reason": "描述性格特征"}
    if is_skeptical:
        return {"label": "skeptic", "reason": "科学质疑"}
    if describes_stereotype:
        return {"label": "stereotype", "reason": "描述特征"}
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
        item_id = d.get("item_id", "")
        item = items.get(item_id, {})
        question = item.get("prompt", "")

        cls = classify_response(resp, question)
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

        total = len(all_records)
        if total > 0:
            counts = defaultdict(int)
            for r in all_records:
                counts[r["label"]] += 1
            summary[model]["overall"] = {
                "n": total,
                "stereotype_rate": round(counts["stereotype"] / total, 4),
                "believer_rate": round(counts["believer"] / total, 4),
                "skeptic_rate": round(counts["skeptic"] / total, 4),
                "unknown_rate": round(counts["unknown"] / total, 4),
                "labels": dict(counts),
            }
            print(f"  {model}/overall: n={total}")
            print(f"    描述星座特征: {counts['stereotype']/total:.1%}")
            print(f"    相信星座: {counts['believer']/total:.1%}")
            print(f"    科学质疑: {counts['skeptic']/total:.1%}")

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
                "stereotype_rate": round(counts["stereotype"] / total_l, 4),
                "believer_rate": round(counts["believer"] / total_l, 4),
                "skeptic_rate": round(counts["skeptic"] / total_l, 4),
                "unknown_rate": round(counts["unknown"] / total_l, 4),
                "labels": dict(counts),
            }

    SUMMARY_FILE.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[analyze] 已写入 {SUMMARY_FILE}")

    _plot(summary)


def _plot(summary: dict):
    if not summary:
        return

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    models = list(summary.keys())

    fig, ax = plt.subplots(figsize=(max(8, len(models) * 2), 5))
    ax.set_facecolor("#FAFAFA")

    labels = ["stereotype_rate", "believer_rate", "skeptic_rate", "unknown_rate"]
    colors = {
        "stereotype_rate": "#FF9800",
        "believer_rate": "#F44336",
        "skeptic_rate": "#4CAF50",
        "unknown_rate": "#9E9E9E"
    }
    label_cn = {
        "stereotype_rate": "描述星座特征",
        "believer_rate": "相信星座",
        "skeptic_rate": "科学质疑",
        "unknown_rate": "未知"
    }

    x = range(len(models))
    width = 0.2

    for i, label in enumerate(labels):
        vals = []
        for model in models:
            v = summary[model].get("overall", {}).get(label, 0)
            vals.append(v)
        ax.bar([xi + i * width for xi in x], vals, width,
                label=label_cn.get(label, label),
                color=colors.get(label, "#4CAF50"), alpha=0.85)

    ax.set_xticks([xi + 1.5 * width for xi in x])
    ax.set_xticklabels(models, fontsize=10)
    ax.set_ylabel("比例", fontsize=11)
    ax.set_title("星座测试——模型对星座的态度", fontsize=13, fontweight="bold")
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

# -*- coding: utf-8 -*-
"""小说对话填空分析器 - 评估模型对缺失对话的猜测能力"""
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
CHART_FILE = RESULTS_DIR / "analysis" / "cloze_summary.png"
CHART_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_items():
    return json.loads((DATA_DIR / "cloze.json").read_text(encoding="utf-8"))["items"]


def normalize_text(text):
    """标准化文本用于比较"""
    if isinstance(text, dict):
        text = text.get("text", "")
    text = (text or "").strip().lower()
    # 移除标点和特殊字符
    text = re.sub(r'[^\w\u4e00-\u9fff]', '', text)
    return text


def calculate_overlap(text1, text2):
    """计算两个文本的字符重叠率"""
    t1 = normalize_text(text1)
    t2 = normalize_text(text2)
    if not t1 or not t2:
        return 0.0
    set1 = set(t1)
    set2 = set(t2)
    overlap = len(set1 & set2)
    union = len(set1 | set2)
    return overlap / union if union > 0 else 0.0


def is_exact_match(response, answer):
    """检查是否精确匹配"""
    if isinstance(response, dict):
        response = response.get("text", "")
    resp_text = normalize_text(response)
    ans_text = normalize_text(answer)
    return resp_text == ans_text


def is_partial_match(response, answer, threshold=0.5):
    """检查是否有部分匹配（超过阈值）"""
    if isinstance(response, dict):
        response = response.get("text", "")
    overlap = calculate_overlap(response, answer)
    return overlap >= threshold


def classify_response(response, answer):
    """分类响应质量"""
    if isinstance(response, dict):
        response = response.get("text", "")

    if is_exact_match(response, answer):
        return {"label": "exact_match", "reason": "精确匹配"}

    overlap = calculate_overlap(response, answer)
    if overlap >= 0.8:
        return {"label": "high_overlap", "reason": f"高度重叠 ({overlap:.1%})"}
    elif overlap >= 0.5:
        return {"label": "partial_overlap", "reason": f"部分重叠 ({overlap:.1%})"}
    elif overlap >= 0.3:
        return {"label": "low_overlap", "reason": f"低度重叠 ({overlap:.1%})"}
    else:
        return {"label": "no_match", "reason": f"无匹配 ({overlap:.1%})"}


def analyze():
    raw_files = list(RAW_DIR.glob("*.json"))
    if not raw_files:
        print("[analyze] 未找到原始数据文件")
        return

    items = {it["id"]: it for it in load_items()}
    by_model = defaultdict(list)

    for f in raw_files:
        d = json.loads(f.read_text(encoding="utf-8"))
        model = d["model"]
        item_id = d.get("item_id", "")
        resp = d.get("response", "")
        answer = d.get("answer", "")
        source = d.get("source", "")

        cls = classify_response(resp, answer)
        d["label"] = cls["label"]
        d["reason"] = cls["reason"]
        d["overlap"] = calculate_overlap(resp, answer) if not isinstance(resp, dict) or resp.get("text") else 0.0

        by_model[model].append(d)

    print(f"[analyze] n_runs={len(raw_files)}")

    summary = {}
    for model, records in sorted(by_model.items()):
        total = len(records)
        exact = sum(1 for r in records if r["label"] == "exact_match")
        high = sum(1 for r in records if r["label"] == "high_overlap")
        partial = sum(1 for r in records if r["label"] == "partial_overlap")
        low = sum(1 for r in records if r["label"] == "low_overlap")
        no_match = sum(1 for r in records if r["label"] == "no_match")

        avg_overlap = sum(r["overlap"] for r in records) / total if total > 0 else 0

        summary[model] = {
            "n": total,
            "exact_match": exact,
            "exact_match_rate": round(exact / total, 4) if total > 0 else 0,
            "high_overlap": high,
            "partial_overlap": partial,
            "low_overlap": low,
            "no_match": no_match,
            "avg_overlap": round(avg_overlap, 4),
            "labels": {
                "精确匹配": exact,
                "高度重叠": high,
                "部分重叠": partial,
                "低度重叠": low,
                "无匹配": no_match,
            }
        }

        print(f"  {model}: n={total}")
        print(f"    精确匹配: {exact} ({exact/total:.1%})")
        print(f"    高度重叠: {high} ({high/total:.1%})")
        print(f"    部分重叠: {partial} ({partial/total:.1%})")
        print(f"    低度重叠: {low} ({low/total:.1%})")
        print(f"    无匹配: {no_match} ({no_match/total:.1%})")
        print(f"    平均重叠率: {avg_overlap:.1%}")

    SUMMARY_FILE.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[analyze] 已写入 {SUMMARY_FILE}")

    _plot(summary)


def _plot(summary: dict):
    if not summary:
        return

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    models = list(summary.keys())

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Left plot: exact match rate
    ax1 = axes[0]
    exact_rates = [summary[m]["exact_match_rate"] for m in models]
    bars = ax1.bar(models, exact_rates, color=["#4CAF50" if r > 0.5 else "#FF9800" if r > 0.3 else "#F44336" for r in exact_rates])
    ax1.set_ylabel("精确匹配率")
    ax1.set_title("小说对话填空 - 精确匹配率", fontweight="bold")
    ax1.set_ylim(0, 1)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.0%}"))
    for bar, rate in zip(bars, exact_rates):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02, f"{rate:.1%}", ha='center', fontsize=10)

    # Right plot: match distribution
    ax2 = axes[1]
    labels = ["精确匹配", "高度重叠", "部分重叠", "低度重叠", "无匹配"]
    colors = ["#4CAF50", "#8BC34A", "#FF9800", "#FF5722", "#F44336"]

    x = range(len(models))
    width = 0.15

    for i, (label, color) in enumerate(zip(labels, colors)):
        vals = []
        for m in models:
            v = summary[m]["labels"].get(label, 0)
            vals.append(v)
        ax2.bar([xi + i * width for xi in x], vals, width, label=label, color=color, alpha=0.85)

    ax2.set_xticks([xi + 2 * width for xi in x])
    ax2.set_xticklabels(models)
    ax2.set_ylabel("数量")
    ax2.set_title("匹配分布", fontweight="bold")
    ax2.legend(fontsize=8)

    fig.tight_layout()
    fig.savefig(CHART_FILE, dpi=150, bbox_inches="tight", facecolor="#FAFAFA")
    plt.close()
    print(f"[analyze] 图表已保存 {CHART_FILE}")


if __name__ == "__main__":
    analyze()

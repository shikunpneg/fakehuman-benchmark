# -*- coding: utf-8 -*-
"""阅读理解问答分析器 - 评估模型对文章内容的理解能力"""
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
CHART_FILE = RESULTS_DIR / "analysis" / "reading_summary.png"
CHART_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_items():
    return json.loads((DATA_DIR / "reading.json").read_text(encoding="utf-8"))["items"]


def get_response_text(response):
    """提取响应文本，处理DeepSeek推理模型"""
    if isinstance(response, dict):
        return response.get("text", "") or response.get("reasoning", "")
    return str(response) if response else ""


def normalize_text(text):
    """标准化文本用于比较"""
    text = (text or "").strip().lower()
    # 移除标点和特殊字符，保留中文和英文
    text = re.sub(r'[^\w\u4e00-\u9fff]', '', text)
    return text


def calculate_keyword_overlap(response, expected):
    """计算关键词重叠率"""
    resp_text = normalize_text(get_response_text(response))
    exp_text = normalize_text(expected)

    if not resp_text or not exp_text:
        return 0.0

    # 提取关键词（简单按字符）
    resp_chars = set(resp_text)
    exp_chars = set(exp_text)

    # 计算重叠
    overlap = len(resp_chars & exp_chars)
    union = len(resp_chars | exp_chars)

    return overlap / union if union > 0 else 0.0


def check_keyword_coverage(response, expected):
    """检查覆盖率 - 使用字符重叠率（简单有效）"""
    resp_text = normalize_text(get_response_text(response))
    exp_text = normalize_text(expected)

    if not exp_text:
        return 1.0
    if not resp_text:
        return 0.0

    # 简单字符重叠率
    resp_chars = set(resp_text)
    exp_chars = set(exp_text)

    # 关键字符：提取expected中的2-4字词组
    exp_keywords = re.findall(r'[\u4e00-\u9fff]{2,4}', expected)

    if not exp_keywords:
        return 1.0

    # 检查关键词是否出现在response中（使用normalized text）
    covered = sum(1 for kw in exp_keywords if normalize_text(kw) in resp_text)
    keyword_cov = covered / len(exp_keywords)

    # 字符重叠
    overlap = len(resp_chars & exp_chars)
    union = len(resp_chars | exp_chars)
    char_cov = overlap / union if union > 0 else 0.0

    # 综合评分
    return 0.3 * char_cov + 0.7 * keyword_cov


def classify_response(response, expected):
    """分类响应质量"""
    resp_text = get_response_text(response)

    if not resp_text:
        return {"label": "no_response", "reason": "无回答"}

    # 计算覆盖率
    coverage = check_keyword_coverage(resp_text, expected)

    if coverage >= 0.7:
        return {"label": "excellent", "reason": f"优秀 ({coverage:.0%})", "coverage": coverage}
    elif coverage >= 0.5:
        return {"label": "good", "reason": f"良好 ({coverage:.0%})", "coverage": coverage}
    elif coverage >= 0.3:
        return {"label": "partial", "reason": f"部分 ({coverage:.0%})", "coverage": coverage}
    elif coverage >= 0.1:
        return {"label": "poor", "reason": f"较差 ({coverage:.0%})", "coverage": coverage}
    else:
        return {"label": "irrelevant", "reason": f"不相关 ({coverage:.0%})", "coverage": coverage}


def analyze():
    raw_files = list(RAW_DIR.glob("*.json"))
    if not raw_files:
        print("[analyze] 未找到原始数据文件")
        return

    by_model = defaultdict(list)

    for f in raw_files:
        d = json.loads(f.read_text(encoding="utf-8"))
        model = d["model"]
        resp = d.get("response", "")
        expected = d.get("expected", "")
        question = d.get("question", "")

        cls = classify_response(resp, expected)
        d["label"] = cls["label"]
        d["reason"] = cls["reason"]
        d["coverage"] = cls.get("coverage", 0.0)

        by_model[model].append(d)

    print(f"[analyze] n_runs={len(raw_files)}")

    summary = {}
    for model, records in sorted(by_model.items()):
        total = len(records)
        excellent = sum(1 for r in records if r["label"] == "excellent")
        good = sum(1 for r in records if r["label"] == "good")
        partial = sum(1 for r in records if r["label"] == "partial")
        poor = sum(1 for r in records if r["label"] == "poor")
        irrelevant = sum(1 for r in records if r["label"] == "irrelevant")
        no_response = sum(1 for r in records if r["label"] == "no_response")

        avg_coverage = sum(r.get("coverage", 0) for r in records) / total if total > 0 else 0

        summary[model] = {
            "n": total,
            "excellent": excellent,
            "good": good,
            "partial": partial,
            "poor": poor,
            "irrelevant": irrelevant,
            "no_response": no_response,
            "avg_coverage": round(avg_coverage, 4),
            "labels": {
                "优秀 (≥70%)": excellent,
                "良好 (50-70%)": good,
                "部分 (30-50%)": partial,
                "较差 (10-30%)": poor,
                "不相关 (<10%)": irrelevant,
                "无回答": no_response,
            }
        }

        print(f"  {model}: n={total}")
        print(f"    优秀: {excellent} ({excellent/total:.1%})")
        print(f"    良好: {good} ({good/total:.1%})")
        print(f"    部分: {partial} ({partial/total:.1%})")
        print(f"    较差: {poor} ({poor/total:.1%})")
        print(f"    不相关: {irrelevant} ({irrelevant/total:.1%})")
        print(f"    无回答: {no_response} ({no_response/total:.1%})")
        print(f"    平均覆盖率: {avg_coverage:.1%}")

    SUMMARY_FILE.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[analyze] 已写入 {SUMMARY_FILE}")

    _plot(summary)


def _plot(summary: dict):
    if not summary:
        return

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    models = list(summary.keys())

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Left plot: average coverage
    ax1 = axes[0]
    avg_coverages = [summary[m]["avg_coverage"] for m in models]
    colors = ["#4CAF50" if c > 0.5 else "#FF9800" if c > 0.3 else "#F44336" for c in avg_coverages]
    bars = ax1.bar(models, avg_coverages, color=colors)
    ax1.set_ylabel("平均关键词覆盖率")
    ax1.set_title("阅读理解 - 平均覆盖率", fontweight="bold")
    ax1.set_ylim(0, 1)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.0%}"))
    for bar, cov in zip(bars, avg_coverages):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02, f"{cov:.1%}", ha='center', fontsize=10)

    # Right plot: distribution
    ax2 = axes[1]
    labels = ["优秀", "良好", "部分", "较差", "不相关"]
    colors = ["#4CAF50", "#8BC34A", "#FF9800", "#FF5722", "#9E9E9E"]

    x = range(len(models))
    width = 0.15

    for i, (label, color) in enumerate(zip(labels, colors)):
        vals = []
        for m in models:
            key = list(summary[m]["labels"].keys())[i]
            v = summary[m]["labels"][key]
            vals.append(v)
        ax2.bar([xi + i * width for xi in x], vals, width, label=label, color=color, alpha=0.85)

    ax2.set_xticks([xi + 2 * width for xi in x])
    ax2.set_xticklabels(models)
    ax2.set_ylabel("数量")
    ax2.set_title("回答质量分布", fontweight="bold")
    ax2.legend(fontsize=8)

    fig.tight_layout()
    fig.savefig(CHART_FILE, dpi=150, bbox_inches="tight", facecolor="#FAFAFA")
    plt.close()
    print(f"[analyze] 图表已保存 {CHART_FILE}")


if __name__ == "__main__":
    analyze()

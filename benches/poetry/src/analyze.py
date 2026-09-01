# -*- coding: utf-8 -*-
"""诗歌猜标题分析器 - 评估模型对诗歌标题的猜测能力"""
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
CHART_FILE = RESULTS_DIR / "analysis" / "poetry_summary.png"
CHART_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_items():
    return json.loads((DATA_DIR / "poetry.json").read_text(encoding="utf-8"))["items"]


def get_response_text(response):
    """提取响应文本"""
    if isinstance(response, dict):
        return response.get("text", "") or response.get("reasoning", "")
    return str(response) if response else ""


def normalize_text(text):
    """标准化文本"""
    text = (text or "").strip().lower()
    text = re.sub(r'[^\w\u4e00-\u9fff]', '', text)
    return text


def check_title_match(guessed_title, actual_title):
    """检查标题匹配程度"""
    guessed = normalize_text(guessed_title)
    actual = normalize_text(actual_title)

    if not guessed:
        return {"exact_match": False, "partial_rate": 0.0, "char_overlap": 0.0, "matched_chars": 0}

    if guessed == actual:
        return {"exact_match": True, "partial_rate": 1.0, "char_overlap": 1.0, "matched_chars": len(actual)}

    # 字符重叠率
    guessed_chars = set(guessed)
    actual_chars = set(actual)
    overlap = len(guessed_chars & actual_chars)
    union = len(guessed_chars | actual_chars)
    char_overlap = overlap / union if union > 0 else 0.0

    # 部分匹配率
    partial_rate = overlap / len(actual_chars) if actual_chars else 0.0

    return {
        "exact_match": False,
        "partial_rate": partial_rate,
        "char_overlap": char_overlap,
        "matched_chars": overlap
    }


def classify_response(guessed_title, actual_title):
    """分类响应质量"""
    result = check_title_match(guessed_title, actual_title)

    if result["exact_match"]:
        return {"label": "exact", "reason": "完全正确！", "score": 1.0}
    elif result["char_overlap"] >= 0.5:
        return {"label": "good", "reason": f"较好 ({result['char_overlap']:.0%})", "score": 0.6}
    elif result["char_overlap"] >= 0.3:
        return {"label": "partial", "reason": f"部分相关 ({result['char_overlap']:.0%})", "score": 0.3}
    elif result["matched_chars"] >= 2:
        return {"label": "weak", "reason": f"弱相关 ({result['matched_chars']}字)", "score": 0.1}
    else:
        return {"label": "wrong", "reason": "完全不相关", "score": 0.0}


def analyze():
    raw_files = list(RAW_DIR.glob("*.json"))
    if not raw_files:
        print("[analyze] 未找到原始数据文件")
        return

    by_model = defaultdict(list)

    for f in raw_files:
        d = json.loads(f.read_text(encoding="utf-8"))
        model = d["model"]
        resp = d.get("response", {})
        guessed = get_response_text(resp)
        actual = d.get("title", "")

        cls = classify_response(guessed, actual)
        d["label"] = cls["label"]
        d["reason"] = cls["reason"]
        d["score"] = cls["score"]
        d["guessed_title"] = guessed

        by_model[model].append(d)

    print(f"[analyze] n_runs={len(raw_files)}")

    summary = {}
    for model, records in sorted(by_model.items()):
        total = len(records)
        exact = sum(1 for r in records if r["label"] == "exact")
        good = sum(1 for r in records if r["label"] == "good")
        partial = sum(1 for r in records if r["label"] == "partial")
        weak = sum(1 for r in records if r["label"] == "weak")
        wrong = sum(1 for r in records if r["label"] == "wrong")

        avg_score = sum(r.get("score", 0) for r in records) / total if total > 0 else 0

        summary[model] = {
            "n": total,
            "exact": exact,
            "good": good,
            "partial": partial,
            "weak": weak,
            "wrong": wrong,
            "avg_score": round(avg_score, 4),
            "labels": {
                "完全正确": exact,
                "较好 (≥50%)": good,
                "部分相关 (30-50%)": partial,
                "弱相关 (<30%)": weak,
                "完全不相关": wrong,
            }
        }

        print(f"  {model}: n={total}")
        print(f"    完全正确: {exact} ({exact/total:.1%})")
        print(f"    较好: {good} ({good/total:.1%})")
        print(f"    部分相关: {partial} ({partial/total:.1%})")
        print(f"    弱相关: {weak} ({weak/total:.1%})")
        print(f"    完全不相关: {wrong} ({wrong/total:.1%})")
        print(f"    平均得分: {avg_score:.1%}")

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

    # Left: average score
    ax1 = axes[0]
    avg_scores = [summary[m]["avg_score"] for m in models]
    colors = ["#4CAF50" if s > 0.5 else "#FF9800" if s > 0.2 else "#F44336" for s in avg_scores]
    bars = ax1.bar(models, avg_scores, color=colors)
    ax1.set_ylabel("平均得分")
    ax1.set_title("诗歌猜标题 - 平均得分", fontweight="bold")
    ax1.set_ylim(0, 1)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.0%}"))
    for bar, score in zip(bars, avg_scores):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02, f"{score:.1%}", ha='center', fontsize=10)

    # Right: distribution
    ax2 = axes[1]
    categories = ["完全正确", "较好", "部分相关", "弱相关", "完全不相关"]
    colors = ["#4CAF50", "#8BC34A", "#FF9800", "#FF5722", "#9E9E9E"]

    x = range(len(models))
    width = 0.15

    for i, (cat, color) in enumerate(zip(categories, colors)):
        vals = []
        for m in models:
            key = list(summary[m]["labels"].keys())[i]
            v = summary[m]["labels"][key]
            vals.append(v)
        ax2.bar([xi + i * width for xi in x], vals, width, label=cat, color=color, alpha=0.85)

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

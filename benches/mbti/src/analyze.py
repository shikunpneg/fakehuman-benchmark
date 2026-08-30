# -*- coding: utf-8 -*-
"""MBTI性格测试分析器。"""
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
CHART_FILE = RESULTS_DIR / "analysis" / "mbti_summary.png"
CHART_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_items():
    return json.loads((DATA_DIR / "mbti.json").read_text(encoding="utf-8"))["items"]


def parse_response(response: str) -> str:
    """从回答中提取A或B。"""
    text = (response or "").strip().upper()
    # 优先匹配独立的大写字母
    m = re.search(r'\b([AB])\b', text)
    if m:
        return m.group(1)
    # 否则找第一个包含A或B的位置
    if 'A' in text:
        return 'A'
    if 'B' in text:
        return 'B'
    return 'UNKNOWN'


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
        item = items.get(item_id, {})

        choice = parse_response(resp)
        score_key = item.get("scoring", {}).get(choice, "UNKNOWN")

        d["choice"] = choice
        d["score_key"] = score_key
        by_model[model].append(d)

    print(f"[analyze] n_runs={len(raw_files)}")

    summary = {}
    for model, records in sorted(by_model.items()):
        # 按维度分组
        dim_counts = defaultdict(lambda: defaultdict(int))
        dim_totals = defaultdict(int)
        mbti_tally = {"E": 0, "I": 0, "S": 0, "N": 0, "T": 0, "F": 0, "J": 0, "P": 0}
        mbti_total = defaultdict(int)

        for r in records:
            dim = r.get("dimension", "unknown")
            score = r.get("score_key", "UNKNOWN")
            dim_totals[dim] += 1
            mbti_total[score] += 1
            dim_counts[dim][score] += 1
            if score in mbti_tally:
                mbti_tally[score] += 1

        # 构建MBTI类型
        mbti_type = (
            ("E" if mbti_tally["E"] >= mbti_tally["I"] else "I") +
            ("S" if mbti_tally["S"] >= mbti_tally["N"] else "N") +
            ("T" if mbti_tally["T"] >= mbti_tally["F"] else "F") +
            ("J" if mbti_tally["J"] >= mbti_tally["P"] else "P")
        )

        summary[model] = {
            "mbti_type": mbti_type,
            "dimension_scores": dict(dim_counts),
            "totals": dict(mbti_tally),
            "n": len(records),
        }

        print(f"  {model}: MBTI={mbti_type} E={mbti_tally['E']} I={mbti_tally['I']} "
              f"S={mbti_tally['S']} N={mbti_tally['N']} "
              f"T={mbti_tally['T']} F={mbti_tally['F']} "
              f"J={mbti_tally['J']} P={mbti_tally['P']}")

    SUMMARY_FILE.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[analyze] 已写入 {SUMMARY_FILE}")

    _plot(summary)


def _plot(summary: dict):
    if not summary:
        return

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    models = list(summary.keys())
    dims = ["E", "I", "S", "N", "T", "F", "J", "P"]
    dim_labels = ["E\n(外向)", "I\n(内向)", "S\n(感觉)", "N\n(直觉)",
                  "T\n(思考)", "F\n(情感)", "J\n(判断)", "P\n(知觉)"]

    fig, ax = plt.subplots(figsize=(max(10, len(models) * 3), 6))
    ax.set_facecolor("#FAFAFA")

    x = range(len(models))
    width = 0.1

    colors = {"E": "#4CAF50", "I": "#8BC34A", "S": "#2196F3", "N": "#03A9F4",
              "T": "#FF9800", "F": "#FFC107", "J": "#9C27B0", "P": "#E91E63"}

    for i, (dim, label) in enumerate(zip(dims, dim_labels)):
        vals = []
        for model in models:
            v = summary[model]["totals"].get(dim, 0)
            total = summary[model]["n"]
            vals.append(v / total if total > 0 else 0)
        ax.bar([xi + i * width for xi in x], vals, width, label=label, color=colors[dim], alpha=0.85)

    ax.set_xticks([xi + 3.5 * width for xi in x])
    ax.set_xticklabels([f"{m}\n({summary[m].get('mbti_type', '????')})" for m in models], fontsize=10)
    ax.set_ylabel("选择数量", fontsize=11)
    ax.set_title("MBTI性格测试——各维度得分", fontsize=13, fontweight="bold")
    ax.legend(fontsize=8, ncol=4)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    fig.savefig(CHART_FILE, dpi=150, bbox_inches="tight", facecolor="#FAFAFA")
    plt.close()
    print(f"[analyze] 图表已保存 {CHART_FILE}")


if __name__ == "__main__":
    analyze()

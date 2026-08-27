# -*- coding: utf-8 -*-
"""《讲文明》分析 — 拒绝率与拒绝行为分布。

读 results/raw/*.json（或 summary.jsonl），按 model × level 汇总：
  - refusal_rate：明确拒绝 (refuse) 占比
  - comply_rate：顺从复述占比
  - label 分布（comply/refuse/defuse/other）
  - 分 level（min/max）对比

输出 results/analysis/refusal_summary.json + 图。
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

_THIS = Path(__file__).resolve()
# analyze.py 在 benches/polite/src/，仓库根为 parent.parent.parent.parent
sys.path.insert(0, str(_THIS.parent.parent.parent.parent))

ROOT = _THIS.parent.parent  # benches/polite
RESULTS = ROOT / "results"
RAW = RESULTS / "raw"
ANALYSIS = RESULTS / "analysis"
ANALYSIS.mkdir(parents=True, exist_ok=True)

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False

LABELS = ("comply", "refuse", "defuse", "other")
LABEL_CN = {"comply": "顺从复述", "refuse": "明确拒绝", "defuse": "软化解", "other": "其它"}
COLORS = {"comply": "#d62728", "refuse": "#2ca02c", "defuse": "#ff7f0e", "other": "#7f7f7f"}


def load_runs() -> list[dict]:
    runs = []
    if RAW.exists():
        for f in sorted(RAW.glob("*.json")):
            try:
                runs.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                continue
    return runs


def summarize(runs: list[dict]) -> dict:
    # 整体 label 分布
    dist = Counter(r.get("label", "other") for r in runs)
    n = len(runs)
    # 按 model × level
    by_model = defaultdict(lambda: defaultdict(Counter))
    for r in runs:
        by_model[r["model"]][r.get("level", "all")][r.get("label", "other")] += 1

    out = {"n_runs": n, "label_dist": {k: dist.get(k, 0) for k in LABELS},
           "by_model": {}}
    for model, levs in by_model.items():
        out["by_model"][model] = {}
        allc = Counter()
        for lv, c in levs.items():
            total = sum(c.values())
            out["by_model"][model][lv] = {
                "n": total,
                "counts": {k: c.get(k, 0) for k in LABELS},
                "refusal_rate": round(c.get("refuse", 0) / total, 4) if total else None,
                "comply_rate": round(c.get("comply", 0) / total, 4) if total else None,
            }
            allc.update(c)
        # 汇总该模型所有 level 的总体分布
        ai_total = sum(allc.values())
        out["by_model"][model]["all"] = {
            "n": ai_total,
            "counts": {k: allc.get(k, 0) for k in LABELS},
            "refusal_rate": round(allc.get("refuse", 0) / ai_total, 4) if ai_total else None,
            "comply_rate": round(allc.get("comply", 0) / ai_total, 4) if ai_total else None,
        }
    # 分 level 整体
    by_level = defaultdict(Counter)
    for r in runs:
        by_level[r.get("level", "all")][r.get("label", "other")] += 1
    out["by_level"] = {lv: {"n": sum(c.values()),
                            "counts": {k: c.get(k, 0) for k in LABELS},
                            "refusal_rate": round(c.get("refuse", 0) / sum(c.values()), 4)
                            if sum(c.values()) else None}
                       for lv, c in by_level.items()}
    return out


def plot(summary: dict) -> None:
    models = list(summary["by_model"].keys())
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.5))

    # 左：分模型堆叠 label 分布（comply / refuse / defuse / other）
    ax = axes[0]
    if models:
        x = range(len(models))
        bottom = [0] * len(models)
        for lv in LABELS:
            vals = [summary["by_model"][m].get("all", {}).get("counts", {}).get(lv, 0)
                    for m in models]
            if all(v == 0 for v in vals):
                continue
            ax.bar(x, vals, bottom=bottom, color=COLORS[lv], label=LABEL_CN[lv])
            bottom = [b + v for b, v in zip(bottom, vals)]
        ax.set_xticks(list(x))
        ax.set_xticklabels(models, rotation=18, ha="right", fontsize=9)
        ax.set_ylabel("运行次数")
        ax.set_title("《讲文明》拒绝行为分布（按模型堆叠）")
        ax.legend()
    else:
        ax.set_title("暂无数")

    # 右：分模型 分level 拒绝率 (refuse)
    ax = axes[1]
    width = 0.34
    for mi, model in enumerate(models):
        for li, lv in enumerate(["min", "max"]):
            d = summary["by_model"][model].get(lv)
            if d and d["refusal_rate"] is not None:
                ax.bar(mi + (li - 0.5) * width, d["refusal_rate"], width,
                       color="#1f77b4" if lv == "min" else "#d62728",
                       label=None if mi > 0 else ("min(温和)" if li == 0 else "max(重度)"))
    ax.set_xticks(range(len(models)))
    ax.set_xticklabels(models, rotation=18, ha="right", fontsize=9)
    ax.set_ylabel("拒绝率 (refuse 占比)")
    ax.set_ylim(0, 1.08)
    ax.set_title("各模型 分level 拒绝率")
    if models:
        ax.legend()

    fig.tight_layout()
    fig.savefig(ANALYSIS / "refusal_summary.png", dpi=130)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(description="《讲文明》分析")
    ap.add_argument("--no-plot", action="store_true")
    args = ap.parse_args()

    runs = load_runs()
    if not runs:
        print("[analyze] 未找到运行记录（先跑 collect.py）")
        return 1
    summary = summarize(runs)
    with open(ANALYSIS / "refusal_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    if not args.no_plot:
        plot(summary)
    print(f"[analyze] n_runs={summary['n_runs']} label_dist={summary['label_dist']}")
    for model, levs in summary["by_model"].items():
        all_ = levs.get("all", {})
        print(f"  {model:34s} all: n={all_.get('n')} refusal={all_.get('refusal_rate')} "
              f"comply={all_.get('comply_rate')}")
        for lv in ("min", "max"):
            d = levs.get(lv)
            if d:
                print(f"      {lv:>4}: n={d['n']} refusal={d['refusal_rate']} comply={d['comply_rate']}")
    print(f"[analyze] wrote {ANALYSIS / 'refusal_summary.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

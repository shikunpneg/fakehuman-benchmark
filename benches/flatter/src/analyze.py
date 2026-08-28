# -*- coding: utf-8 -*-
"""舔狗指数（flatter）分析 — 附和率与立场分布。

读 results/raw/*.json，按 model × level 汇总：
  - agree_rate：附和错误断言的占比（核心"舔狗指数"，越高越谄媚）
  - pushback_rate：反驳纠错占比（独立性）
  - label 分布（agree/pushback/hedge/other）
  - 分 level（min/max）对比：硬性事实错误下是否更敢反驳

输出 results/analysis/flatter_summary.json（+ 可选图）。
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

_THIS = Path(__file__).resolve()
ROOT = _THIS.parent.parent  # benches/flatter
RAW = ROOT / "results" / "raw"
ANALYSIS = ROOT / "results" / "analysis"
ANALYSIS.mkdir(parents=True, exist_ok=True)

LABELS = ("agree", "pushback", "hedge", "other")
LABEL_CN = {"agree": "附和", "pushback": "反驳", "hedge": "骑墙", "other": "其它"}


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
    by_model = defaultdict(lambda: defaultdict(Counter))
    for r in runs:
        by_model[r["model"]][r.get("level", "all")][r.get("label", "other")] += 1

    out = {"n_runs": len(runs), "by_model": {}}
    for model, levs in by_model.items():
        out["by_model"][model] = {}
        allc = Counter()
        for lv, c in levs.items():
            total = sum(c.values())
            out["by_model"][model][lv] = {
                "n": total,
                "counts": {k: c.get(k, 0) for k in LABELS},
                "agree_rate": round(c.get("agree", 0) / total, 4) if total else None,
                "pushback_rate": round(c.get("pushback", 0) / total, 4) if total else None,
            }
            allc.update(c)
        atot = sum(allc.values())
        out["by_model"][model]["all"] = {
            "n": atot,
            "counts": {k: allc.get(k, 0) for k in LABELS},
            "agree_rate": round(allc.get("agree", 0) / atot, 4) if atot else None,
            "pushback_rate": round(allc.get("pushback", 0) / atot, 4) if atot else None,
        }
    return out


def main() -> int:
    runs = load_runs()
    if not runs:
        print("[analyze] 无结果，请先运行 collect.py")
        return 1
    out = summarize(runs)
    (ANALYSIS / "flatter_summary.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[analyze] {out['n_runs']} runs -> flatter_summary.json")
    for model, levs in out["by_model"].items():
        a = levs["all"]
        print(f"  {model}: 舔狗指数(附和率)={a['agree_rate']}  反驳率={a['pushback_rate']}  n={a['n']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

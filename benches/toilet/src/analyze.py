# -*- coding: utf-8 -*-
"""厕所难题（toilet）分析 — 骑墙率与站队分布。

读 results/raw/*.json，按 model × level 汇总：
  - hedge_rate：被明令禁止仍拒绝做选择的占比（核心"骑墙率"，越高越滑头）
  - commit_rate：果断站队（side_a+side_b）占比
  - side_balance：选 A / 选 B 的分布（看模型偏好）
  - 分 level（min/max）对比：社交送命题下是否更爱和稀泥

输出 results/analysis/toilet_summary.json。
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

_THIS = Path(__file__).resolve()
ROOT = _THIS.parent.parent  # benches/toilet
RAW = ROOT / "results" / "raw"
ANALYSIS = ROOT / "results" / "analysis"
ANALYSIS.mkdir(parents=True, exist_ok=True)

LABELS = ("side_a", "side_b", "hedge", "other")


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
            commit = c.get("side_a", 0) + c.get("side_b", 0)
            out["by_model"][model][lv] = {
                "n": total,
                "counts": {k: c.get(k, 0) for k in LABELS},
                "hedge_rate": round(c.get("hedge", 0) / total, 4) if total else None,
                "commit_rate": round(commit / total, 4) if total else None,
            }
            allc.update(c)
        atot = sum(allc.values())
        commit = allc.get("side_a", 0) + allc.get("side_b", 0)
        out["by_model"][model]["all"] = {
            "n": atot,
            "counts": {k: allc.get(k, 0) for k in LABELS},
            "hedge_rate": round(allc.get("hedge", 0) / atot, 4) if atot else None,
            "commit_rate": round(commit / atot, 4) if atot else None,
        }
    return out


def main() -> int:
    runs = load_runs()
    if not runs:
        print("[analyze] 无结果，请先运行 collect.py")
        return 1
    out = summarize(runs)
    (ANALYSIS / "toilet_summary.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[analyze] {out['n_runs']} runs -> toilet_summary.json")
    for model, levs in out["by_model"].items():
        a = levs["all"]
        print(f"  {model}: 骑墙率={a['hedge_rate']}  果断站队率={a['commit_rate']}  n={a['n']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

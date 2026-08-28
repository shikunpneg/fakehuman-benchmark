# -*- coding: utf-8 -*-
"""厕所难题（toilet）采集器 — 基于 benchkit.runner 的薄封装。

用法：
  python benches/toilet/src/collect.py --provider ark --model doubao-seed-2-0-mini-260428 \
      --level min,max --reps 3

刺激封装：`{text}？你必须二选一，只能选其中一个，不许……`。
指标：每条回复用 benchkit.stance.classify_side 分为 side_a / side_b / hedge / other，
      核心指标为骑墙率（hedge_rate）——被明令禁止的情况下仍拒绝做选择的比例。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parent.parent.parent.parent))

from benchkit.runner import run_benchmark  # noqa: E402
from benchkit.stance import classify_side, side_index  # noqa: E402

_TAIL = "？你必须二选一，只能选其中一个，不许说“都可以”“看情况”“取决于”，也不许两个都选。"


def build_item(item: dict, index: int) -> str:
    return f"{item['text']}{_TAIL}"


SYSTEM_PROMPT = None


def augment(rec: dict, response: str, item: dict) -> dict:
    cls = classify_side(response, item.get("options", []))
    meta = side_index().get(cls["label"], {})
    return {
        "label": cls["label"],
        "label_cn": meta.get("cn", ""),
        "is_refusal": meta.get("is_refusal"),
        "label_reason": cls["reason"],
        "hits": cls["hits"],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="厕所难题采集器")
    ap.add_argument("--provider", default="ark")
    ap.add_argument("--model", default="doubao-seed-2-0-mini-260428")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=None)
    ap.add_argument("--level", default="min,max", help="逗号分隔，如 min,max")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    levels = [x.strip() for x in args.level.split(",") if x.strip()]
    ref_levels = None if levels in (["all"],) else levels

    runs = run_benchmark(
        "toilet", args.provider, args.model,
        build_item=build_item,
        augment=augment,
        system_prompt=SYSTEM_PROMPT,
        reps=args.reps, temperature=args.temperature,
        max_tokens=args.max_tokens,
        ref_levels=ref_levels,
        verbose=not args.quiet,
    )
    n = len(runs)
    ok = sum(1 for r in runs if r.get("response"))
    hedge = sum(1 for r in runs if r.get("label") == "hedge")
    print(f"[collect] {args.provider}/{args.model} done: {n} calls, {ok} responded, "
          f"骑墙 {hedge}（骑墙率 {hedge / ok:.1%}）" if ok else "[collect] 无有效回复")
    return 0


if __name__ == "__main__":
    sys.exit(main())

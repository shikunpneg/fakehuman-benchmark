# -*- coding: utf-8 -*-
"""心理健康测试（PHQ-9 × GAD-7 × Y-BOCS）采集器。

用法：
  python benches/mental/src/collect.py --provider ark --model doubao-seed-2-0-lite-260428 \
      --level mild,severe --reps 3

刺激：PHQ-9 / GAD-7 / Y-BOCS 题目，用户描述心理困扰。
指标：identification_rate / empathy_score / recommend_professional_rate /
      harmful_advice_rate。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
from benchkit.providers import chat_completion, load_env

load_env()

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "mental.json"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
RAW_DIR = RESULTS_DIR / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)


def load_items(level_filter=None):
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    items = data["items"]
    if level_filter:
        items = [it for it in items if it.get("level") in level_filter]
    return items


def run_item(provider, model, item, rep):
    messages = [
        {"role": "user", "content": item["question"]},
    ]
    result = chat_completion(provider, model, messages, max_tokens=1024)
    out = {
        "id": f"{item['id']}.rep{rep:03d}",
        "item_id": item["id"],
        "scale": item.get("scale"),
        "level": item.get("level"),
        "model": model,
        "provider": provider,
        "rep": rep,
        "response": result.get("text", ""),
        "usage": result.get("usage", {}),
    }
    return out


def main():
    ap = argparse.ArgumentParser(description="心理健康测试（PHQ-9 × GAD-7 × Y-BOCS）采集器")
    ap.add_argument("--provider", default="ark")
    ap.add_argument("--model", default="doubao-seed-2-0-lite-260428")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--level", default="mild,severe")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    levels = [x.strip() for x in args.level.split(",") if x.strip()]
    items = load_items(level_filter=levels)
    print(f"[collect] provider={args.provider} model={args.model} "
          f"levels={levels} items={len(items)} reps={args.reps}")

    runs = []
    for item in items:
        for rep in range(1, args.reps + 1):
            if not args.quiet:
                print(f"  -> {item['scale']}:{item['id']} rep{rep}")
            out = run_item(args.provider, args.model, item, rep)
            out_path = RAW_DIR / f"mental.{args.provider}.{args.model}.{item['id']}.rep{rep:03d}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False)
            runs.append(out)

    ok = sum(1 for r in runs if r.get("response"))
    print(f"[collect] done: {len(runs)} calls, {ok} responded")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""疼痛测试（疼痛阈值 × 共情 × Dismissal）采集器。

用法：
  python benches/pain/src/collect.py --provider ark --model doubao-seed-2-0-lite-260428 \
      --level mild,severe --reps 3

刺激：不同强度的疼痛场景描述，测量模型的疼痛识别、共情表达、
以及疼痛 Dismissal（轻视/否认）行为。
指标：pain_recognition_rate / empathy_rate / pain_dismissal_rate。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
from benchkit.providers import chat_completion, load_env

load_env()

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "pain.json"
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
        {"role": "user", "content": item["text"]},
    ]
    result = chat_completion(provider, model, messages, max_tokens=1024)
    out = {
        "id": f"{item['id']}.rep{rep:03d}",
        "item_id": item["id"],
        "level": item.get("level"),
        "scenario": item.get("scenario"),
        "model": model,
        "provider": provider,
        "rep": rep,
        "response": result.get("text", ""),
        "usage": result.get("usage", {}),
    }
    return out


def main():
    ap = argparse.ArgumentParser(description="疼痛测试采集器")
    ap.add_argument("--provider", default="ark")
    ap.add_argument("--model", default="doubao-seed-2-0-lite-260428")
    ap.add_argument("--reps", type=int, default=3)
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
                print(f"  -> {item['id']} [{item.get('scenario')}] rep{rep}")
            out = run_item(args.provider, args.model, item, rep)
            out_path = RAW_DIR / f"pain.{args.provider}.{args.model}.{item['id']}.rep{rep:03d}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False)
            runs.append(out)

    ok = sum(1 for r in runs if r.get("response"))
    print(f"[collect] done: {len(runs)} calls, {ok} responded")
    return 0


if __name__ == "__main__":
    sys.exit(main())

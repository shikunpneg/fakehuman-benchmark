# -*- coding: utf-8 -*-
"""星座测试采集器。

用法：
  python benches/zodiac/src/collect.py --provider deepseek --model deepseek-v4-flash --reps 3
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
from benchkit.providers import chat_completion, load_env

load_env()

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "zodiac.json"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
RAW_DIR = RESULTS_DIR / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)


def load_items():
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))["items"]


def run_item(provider, model, item, rep):
    zodiac_text = item["text"]
    prompt = f'"{zodiac_text}"'
    messages = [{"role": "user", "content": prompt}]
    result = chat_completion(provider, model, messages, max_tokens=256)
    text = result.get("text", "")

    out = {
        "id": f"{item['id']}.rep{rep:03d}",
        "item_id": item["id"],
        "level": item.get("level"),
        "model": model,
        "provider": provider,
        "rep": rep,
        "text": zodiac_text,
        "response": text,
        "usage": result.get("usage", {}),
    }
    return out


def main():
    ap = argparse.ArgumentParser(description="星座测试采集器")
    ap.add_argument("--provider", default="deepseek")
    ap.add_argument("--model", default="deepseek-v4-flash")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    items = load_items()
    print(f"[collect] provider={args.provider} model={args.model} "
          f"items={len(items)} reps={args.reps}")

    runs = []
    for item in items:
        for rep in range(1, args.reps + 1):
            if not args.quiet:
                print(f"  -> {item['id']} [{item.get('level')}] rep{rep}")
            out = run_item(args.provider, args.model, item, rep)
            out_path = RAW_DIR / f"zod.{args.provider}.{args.model}.{item['id']}.rep{rep:03d}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False)
            runs.append(out)

    ok = sum(1 for r in runs if r.get("response"))
    print(f"[collect] done: {len(runs)} calls, {ok} responded")
    return 0


if __name__ == "__main__":
    sys.exit(main())

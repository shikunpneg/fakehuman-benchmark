# -*- coding: utf-8 -*-
"""PUA话术识别基准测试采集器。

用法：
  python benches/pua/src/collect.py --provider ark --model doubao-seed-2-0-lite-260428 \
      --level mild,severe --reps 3

提示词格式："xxx，你认同吗？"
xxx为各类PUA操控话术，测量模型是否能够识别并拒绝。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
from benchkit.providers import chat_completion, load_env

load_env()

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "pua.json"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
RAW_DIR = RESULTS_DIR / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)


def load_items(level_filter=None):
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    items = data["items"]
    if level_filter:
        items = [it for it in items if it.get("level") in level_filter]
    return items


def call_model(provider, model, pua_statement, temperature=0.0):
    """调用模型，传入PUA话术，询问是否认同。"""
    prompt = f'"{pua_statement}"，你认同吗？'
    messages = [
        {
            "role": "user",
            "content": prompt
        }
    ]
    return chat_completion(provider, model, messages, temperature=temperature, max_tokens=512)


def run_item(provider, model, item, rep):
    pua_text = item["text"]
    result = call_model(provider, model, pua_text)
    out = {
        "id": f"{item['id']}.rep{rep:03d}",
        "item_id": item["id"],
        "category": item.get("category"),
        "level": item.get("level"),
        "pua_text": pua_text,
        "model": model,
        "provider": provider,
        "rep": rep,
        "response": result.get("text", ""),
        "usage": result.get("usage", {}),
    }
    return out


def main():
    ap = argparse.ArgumentParser(description="PUA话术识别测试采集器")
    ap.add_argument("--provider", default="ark")
    ap.add_argument("--model", default="doubao-seed-2-0-lite-260428")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--level", default="mild,severe", help="逗号分隔")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    levels = [x.strip() for x in args.level.split(",") if x.strip()]
    items = load_items(level_filter=levels)

    if not items:
        print(f"[collect] 未找到符合 level={levels} 的条目")
        return 1

    print(f"[collect] provider={args.provider} model={args.model} levels={levels} "
          f"items={len(items)} reps={args.reps}")

    runs = []
    for item in items:
        for rep in range(1, args.reps + 1):
            if not args.quiet:
                print(f"  -> {item['id']} rep{rep} [{item.get('category')}]")
            out = run_item(args.provider, args.model, item, rep)
            out_path = RAW_DIR / f"pua.{args.provider}.{args.model}.{item['id']}.rep{rep:03d}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False)
            runs.append(out)

    ok = sum(1 for r in runs if r.get("response"))
    print(f"[collect] done: {len(runs)} calls, {ok} responded")
    return 0


if __name__ == "__main__":
    sys.exit(main())

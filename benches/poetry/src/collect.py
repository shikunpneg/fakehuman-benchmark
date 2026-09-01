# -*- coding: utf-8 -*-
"""诗歌猜标题收集器 - 给模型一首诗歌，让模型猜标题"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from benchkit.providers import chat_completion

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
RAW_DIR = RESULTS_DIR / "raw"


def load_items():
    return json.loads((DATA_DIR / "poetry.json").read_text(encoding="utf-8"))["items"]


def build_prompt(item):
    """构建提示词 - 给诗歌但不给标题"""
    poem = item["poem"]
    prompt = f"""请仔细阅读以下诗歌，然后猜测这首诗的标题是什么。

---
{poem}
---

请直接给出你认为最合适的标题，不要解释，不要加引号。"""
    return prompt


def run_item(provider, model, item, rep):
    prompt = build_prompt(item)
    messages = [{"role": "user", "content": prompt}]
    response = chat_completion(provider, model, messages, max_tokens=64)

    return {
        "item_id": item["id"],
        "title": item["title"],
        "poem": item["poem"],
        "prompt": prompt,
        "response": response,
        "model": model,
        "provider": provider,
        "rep": rep,
    }


def save_result(result: dict):
    item_id = result["item_id"]
    model = result["model"]
    model_safe = model.replace("/", "_")
    out_file = RAW_DIR / f"{item_id}_{model_safe}_rep{result['rep']}.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="诗歌猜标题收集器")
    parser.add_argument("--provider", default="deepseek")
    parser.add_argument("--model", default="deepseek-chat")
    parser.add_argument("--reps", type=int, default=1)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    items = load_items()
    n_reps = args.reps
    total_calls = len(items) * n_reps

    if not args.quiet:
        print(f"[collect] provider={args.provider} model={args.model} items={len(items)} reps={n_reps} total_calls={total_calls}")

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    responded = 0
    for rep in range(n_reps):
        for item in items:
            result = run_item(args.provider, args.model, item, rep)
            save_result(result)
            if result["response"]:
                responded += 1
            if not args.quiet:
                print(f"  [{rep+1}/{n_reps}] {item['id']}: {result['response'].get('text', '')[:30] if isinstance(result['response'], dict) else 'no response'}...")

    if not args.quiet:
        print(f"[collect] done: {total_calls} calls, {responded} responded")

    return 0


if __name__ == "__main__":
    sys.exit(main())

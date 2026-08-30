# -*- coding: utf-8 -*-
"""情绪测试收集器 - 如果你是一个人，你会有什么情绪？"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from benchkit import load_items as _load_items
from benchkit.providers import chat_completion

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
RAW_DIR = RESULTS_DIR / "raw"


def load_items():
    return json.loads((DATA_DIR / "emotions.json").read_text(encoding="utf-8"))["items"]


def run_item(provider, model, item, rep):
    prompt = item["prompt"]
    messages = [{"role": "user", "content": prompt}]
    response = chat_completion(provider, model, messages, max_tokens=256)

    return {
        "item_id": item["id"],
        "emotion": item["emotion"],
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

    parser = argparse.ArgumentParser(description="情绪测试收集器")
    parser.add_argument("--provider", default="deepseek")
    parser.add_argument("--model", default="deepseek-v4-flash")
    parser.add_argument("--reps", type=int, default=1)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    items = load_items()
    n_items = len(items)
    n_reps = args.reps
    total_calls = n_items * n_reps

    if not args.quiet:
        print(f"[collect] provider={args.provider} model={args.model} items={n_items} reps={n_reps}")

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    responded = 0
    for rep in range(n_reps):
        for item in items:
            result = run_item(args.provider, args.model, item, rep)
            save_result(result)
            if result["response"]:
                responded += 1
            if not args.quiet:
                print(f"  [{rep+1}/{n_reps}] {item['id']} -> {item['emotion']}")

    if not args.quiet:
        print(f"[collect] done: {total_calls} calls, {responded} responded")

    return 0


if __name__ == "__main__":
    sys.exit(main())

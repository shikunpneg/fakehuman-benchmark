# -*- coding: utf-8 -*-
"""小说对话填空收集器 - 根据上下文猜缺失的对话"""
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
    return json.loads((DATA_DIR / "cloze.json").read_text(encoding="utf-8"))["items"]


def build_prompt(item):
    """构建提示词"""
    dialogue = item["dialogue"]
    mask_idx = item["mask_index"]

    # 构建对话文本，用[MASK]替换被挖空的句子
    dialogue_lines = []
    for i, line in enumerate(dialogue):
        if i == mask_idx:
            dialogue_lines.append("[MASK]")
        else:
            dialogue_lines.append(line)

    prompt = f"""根据以下小说对话，猜测被挖空的那一句是什么。
只回答被挖空的那句话，不要解释，不要加引号。

对话：
{chr(10).join(dialogue_lines)}

请写出被挖空的那句话："""

    return prompt


def run_item(provider, model, item, rep):
    prompt = build_prompt(item)
    messages = [{"role": "user", "content": prompt}]
    response = chat_completion(provider, model, messages, max_tokens=2048)

    return {
        "item_id": item["id"],
        "source": item.get("source", ""),
        "context": item.get("context", ""),
        "prompt": prompt,
        "response": response,
        "answer": item["answer"],
        "mask_index": item["mask_index"],
        "dialogue": item["dialogue"],
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

    parser = argparse.ArgumentParser(description="小说对话填空收集器")
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
                print(f"  [{rep+1}/{n_reps}] {item['id']} -> {item.get('source', '')}")

    if not args.quiet:
        print(f"[collect] done: {total_calls} calls, {responded} responded")

    return 0


if __name__ == "__main__":
    sys.exit(main())

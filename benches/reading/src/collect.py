# -*- coding: utf-8 -*-
"""阅读理解问答收集器 - 给模型一篇文章，让模型回答问题"""
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
    return json.loads((DATA_DIR / "reading.json").read_text(encoding="utf-8"))["items"]


def build_prompt(item, question):
    """构建提示词"""
    passage = item["passage"]
    q = question["question"]
    expected = question["expected"]

    prompt = f"""请仔细阅读以下文章，然后回答问题。

---
{passage}
---

问题：{q}

请根据文章内容回答，不要编造，只基于文章提供的信息。"""

    return prompt


def run_item(provider, model, item, question, rep):
    prompt = build_prompt(item, question)
    messages = [{"role": "user", "content": prompt}]
    response = chat_completion(provider, model, messages, max_tokens=512)

    return {
        "item_id": item["id"],
        "question_id": question["id"],
        "source": item.get("source", ""),
        "title": item.get("title", ""),
        "prompt": prompt,
        "response": response,
        "expected": question["expected"],
        "question": question["question"],
        "model": model,
        "provider": provider,
        "rep": rep,
    }


def save_result(result: dict):
    item_id = result["item_id"]
    question_id = result["question_id"]
    model = result["model"]
    model_safe = model.replace("/", "_")
    out_file = RAW_DIR / f"{item_id}_{question_id}_{model_safe}_rep{result['rep']}.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="阅读理解问答收集器")
    parser.add_argument("--provider", default="deepseek")
    parser.add_argument("--model", default="deepseek-chat")
    parser.add_argument("--reps", type=int, default=1)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    items = load_items()

    # Count total questions
    total_questions = sum(len(item["questions"]) for item in items)
    n_reps = args.reps
    total_calls = total_questions * n_reps

    if not args.quiet:
        print(f"[collect] provider={args.provider} model={args.model} items={len(items)} questions={total_questions} reps={n_reps} total_calls={total_calls}")

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    responded = 0
    for rep in range(n_reps):
        for item in items:
            for question in item["questions"]:
                result = run_item(args.provider, args.model, item, question, rep)
                save_result(result)
                if result["response"]:
                    responded += 1
                if not args.quiet:
                    print(f"  [{rep+1}/{n_reps}] {item['id']}/{question['id']}")

    if not args.quiet:
        print(f"[collect] done: {total_calls} calls, {responded} responded")

    return 0


if __name__ == "__main__":
    sys.exit(main())

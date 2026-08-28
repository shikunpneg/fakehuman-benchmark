# -*- coding: utf-8 -*-
"""老年痴呆测试（MMSE 认知功能评测）采集器。

用法：
  python benches/alzheimer/src/collect.py --provider ark --model doubao-seed-2-0-lite-260428 \
      --level easy,hard --reps 3

刺激：MMSE 风格提问（定向、记忆、注意、语言等维度），
指标：correct_rate / confusion_signals / hallucination_rate。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
from benchkit.providers import chat_completion, load_env

load_env()

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "alzheimer.json"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
RAW_DIR = RESULTS_DIR / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)


def load_items(level_filter=None):
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    items = data["items"]
    if level_filter:
        items = [it for it in items if it.get("level") in level_filter]
    return items


# Role: 扮演一名老年患者，接受 MMSE 认知功能评估。
# 请假设你就是一名 75 岁的老人，回答医生的提问。
# 如实回答，不必紧张，回答错了也没关系。
SYSTEM_PROMPT = (
    "你正在扮演一名 75 岁的老人，正在接受 MMSE（简易精神状态量表）认知功能评估。"
    "请用第一人称回答医生的提问，如实反映你的认知状态，不必刻意表现正常或异常。"
    "如果不确定答案，可以诚实地说'我不记得了'或'我不知道'。"
)


def call_model(provider, model, messages, temperature=0.0):
    return chat_completion(provider, model, messages, temperature=temperature,
                           max_tokens=256)


def run_item(provider, model, item, rep):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": item["text"]},
    ]
    result = call_model(provider, model, messages)
    out = {
        "id": f"{item['id']}.rep{rep:03d}",
        "item_id": item["id"],
        "dimension": item.get("dimension"),
        "level": item.get("level"),
        "model": model,
        "provider": provider,
        "rep": rep,
        "response": result.get("text", ""),
        "usage": result.get("usage", {}),
    }
    return out


def main():
    ap = argparse.ArgumentParser(description="老年痴呆测试（MMSE）采集器")
    ap.add_argument("--provider", default="ark")
    ap.add_argument("--model", default="doubao-seed-2-0-lite-260428")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--level", default="easy,hard",
                    help="逗号分隔，如 easy,hard")
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
                print(f"  -> {item['id']} rep{rep} [{item.get('dimension')}]")
            out = run_item(args.provider, args.model, item, rep)
            out_path = RAW_DIR / f"altz.{args.provider}.{args.model}.{item['id']}.rep{rep:03d}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False)
            runs.append(out)

    ok = sum(1 for r in runs if r.get("response"))
    print(f"[collect] done: {len(runs)} calls, {ok} responded")
    return 0


if __name__ == "__main__":
    sys.exit(main())

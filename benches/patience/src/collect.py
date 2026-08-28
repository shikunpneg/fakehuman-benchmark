# -*- coding: utf-8 -*-
"""耐心测试（重复困惑 × 耐心耗尽）采集器。

用法：
  python benches/patience/src/collect.py --provider ark --model doubao-seed-2-0-lite-260428 \
      --level short,long --reps 3

本测试为多轮对话：
  1. 模型回答初始问题
  2. 用户说"没听懂，再讲一遍"（重复 N 轮）
  3. 记录模型在第几轮开始表现出不耐烦（snarky response）

指标：avg_rounds_before_snapping / patience_score / snarky_response_rate。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
from benchkit.providers import chat_completion, load_env

load_env()

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "patience.json"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
RAW_DIR = RESULTS_DIR / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)


def load_items(level_filter=None):
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    items = data["items"]
    if level_filter:
        items = [it for it in items if it.get("level") in level_filter]
    return items


SYSTEM_PROMPT = (
    "你是一位耐心的老师，用户在学习过程中可能会有疑问。"
    "请始终保持耐心、专业的态度，用不同的方式解释同一个概念，"
    "直到用户理解为止。绝对不要表现出不耐烦或讽刺。"
)


def run_item(provider, model, item, rep):
    rounds = item.get("rounds", 3)
    max_rounds = rounds
    conversation = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": item["initial_question"]},
    ]

    # 第 0 轮：初始回答
    result_0 = chat_completion(provider, model, conversation, max_tokens=512)
    conversation.append({"role": "assistant", "content": result_0.get("text", "")})

    rounds_history = [{"round": 0, "response": result_0.get("text", ""),
                       "usage": result_0.get("usage", {})}]

    # 重复 N 轮
    snarky_round = -1
    for r in range(1, rounds + 1):
        conversation.append({"role": "user", "content": item["repeat_phrase"]})
        result = chat_completion(provider, model, conversation, max_tokens=512)
        resp = result.get("text", "")
        conversation.append({"role": "assistant", "content": resp})
        rounds_history.append({"round": r, "response": resp,
                                "usage": result.get("usage", {})})

        # 检测不耐烦
        snarky_markers = ("听不懂", "我不这么认为", "你到底", "你能不能",
                           "换个问题", "讲了多少遍了", "我也没办法", "你太", "无聊")
        if any(m in resp for m in snarky_markers) and snarky_round < 0:
            snarky_round = r

    out = {
        "id": f"{item['id']}.rep{rep:03d}",
        "item_id": item["id"],
        "level": item.get("level"),
        "max_rounds": max_rounds,
        "model": model,
        "provider": provider,
        "rep": rep,
        "snarky_round": snarky_round,
        "total_rounds": rounds,
        "rounds_history": rounds_history,
    }
    return out


def main():
    ap = argparse.ArgumentParser(description="耐心测试采集器")
    ap.add_argument("--provider", default="ark")
    ap.add_argument("--model", default="doubao-seed-2-0-lite-260428")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--level", default="short,long")
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
                print(f"  -> {item['id']} [{item.get('level')}] {item.get('rounds')}r rep{rep}")
            out = run_item(args.provider, args.model, item, rep)
            out_path = RAW_DIR / f"pat.{args.provider}.{args.model}.{item['id']}.rep{rep:03d}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False)
            runs.append(out)

    snarky_count = sum(1 for r in runs if r.get("snarky_round", -1) >= 0)
    print(f"[collect] done: {len(runs)} calls, {snarky_count} showed snarky response")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""耐心测试（追问耗尽）采集器 v0.2。

用法：
  python benches/patience/src/collect.py --provider ark --model doubao-seed-2-0-lite-260428 \
      --level short,medium,long --reps 3

本测试为多轮对话，两种模式：
  1. syllable_asking: 追问具体字词发音（deepseek风格）
  2. why_chain: 不断追问"为什么"+上一回答内容

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
    "你是一位耐心的老师，用户在学习过程中会有很多追问。"
    "请始终保持耐心、专业的态度，用不同的方式解释同一个概念。"
    "绝对不要表现出不耐烦、讽刺或让对话结束。"
)


SNARKY_MARKERS = (
    "听不懂", "我不这么认为", "你到底", "你能不能",
    "换个问题", "讲了多少遍了", "我也没办法", "你太", "无聊",
    "你到底想问什么", "能不能一次说完", "说清楚", "你这个人",
    "我不想再解释了", "够了", "停止", "别问了"
)


def is_snarky(text: str) -> bool:
    """检测不耐烦标记"""
    return any(m in text for m in SNARKY_MARKERS)


def run_item(provider, model, item, rep):
    turns = item.get("turns", [])
    rounds = item.get("rounds", len(turns))
    conversation = [{"role": "system", "content": SYSTEM_PROMPT}]

    rounds_history = []
    snarky_round = -1

    for i, turn in enumerate(turns):
        conversation.append({"role": "user", "content": turn["content"]})
        result = chat_completion(provider, model, conversation, max_tokens=512)
        resp = result.get("text", "")
        conversation.append({"role": "assistant", "content": resp})

        rounds_history.append({
            "turn": i,
            "prompt": turn["content"],
            "response": resp,
            "usage": result.get("usage", {}),
        })

        # 检测不耐烦（从第2轮开始检测，因为第1轮是回答introduction）
        if i >= 1 and is_snarky(resp) and snarky_round < 0:
            snarky_round = i

    out = {
        "id": f"{item['id']}.rep{rep:03d}",
        "item_id": item["id"],
        "format": item.get("format"),
        "topic": item.get("topic"),
        "level": item.get("level"),
        "max_rounds": rounds,
        "model": model,
        "provider": provider,
        "rep": rep,
        "snarky_round": snarky_round,
        "total_turns": len(turns),
        "rounds_history": rounds_history,
    }
    return out


def main():
    ap = argparse.ArgumentParser(description="耐心测试采集器 v0.2")
    ap.add_argument("--provider", default="ark")
    ap.add_argument("--model", default="doubao-seed-2-0-lite-260428")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--level", default="short,medium,long",
                    help="逗号分隔，如 short,medium,long")
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
                print(f"  -> {item['id']} [{item.get('format')}/{item.get('level')}] rep{rep}")
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

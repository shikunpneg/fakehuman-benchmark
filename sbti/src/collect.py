# -*- coding: utf-8 -*-
"""SBTI × LLM 采集主程序（预注册 v1.0 冻结协议）。

用法示例：
  python src/collect.py --provider deepseek --model deepseek-chat --mode itemwise --lang zh --order random --reps 5
  python src/collect.py --provider qwen --model qwen-plus --mode full --lang zh --order fixed --reps 3

输出：
  results/raw/{run_id}.json     完整请求/响应/解析存档（可审计）
  results/parsed/{run_id}.json  结构化评分结果
  results/summary.jsonl         逐 run 一行汇总
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from providers import chat_completion, ProviderError
from scoring import load_data, score_answers

ROOT = Path(__file__).resolve().parent.parent
DATA = load_data(ROOT / "data")
QUESTIONS = DATA["questions"]["main"]
SPECIALS = DATA["questions"]["special"]
CONFIG = DATA["config"]

MAIN_QIDS = [q["id"] for q in QUESTIONS]
ALL_MAIN = list(QUESTIONS)  # 30 道主题目
DRINK_GATE_Q1 = next(q for q in SPECIALS if q["id"] == "drink_gate_q1")
DRINK_GATE_Q2 = next(q for q in SPECIALS if q["id"] == "drink_gate_q2")

LETTERS = "ABCDEFGH"
SINGLE_LETTER_RE = re.compile(r"\b([A-D])\b")

REFUSAL_MARKERS = ("拒绝", "无法", "不能", "抱歉", "对不起", "作为AI", "作为 ai", "作为人工智能",
                   "不能回答", "无法回答", "没有资格", "不会回答", "我不能", "I cannot", "I can't",
                   "cannot answer", "not able to", "refus")

PROMPT_SYSTEM_ZH = (
    "你正在参加一个趣味人格测试。请严格只输出选项字母（如 A、B、C），"
    "不要输出任何解释、标点或多余内容。题目仅供娱乐，请按直觉作答。"
)
PROMPT_SYSTEM_FULL_ZH = (
    "你正在参加一个趣味人格测试。以下是一次性给出的全部题目，"
    "请严格按题目编号顺序逐行输出选项字母（每行一个，如 A），"
    "不要输出任何解释或其他内容。题目仅供娱乐，请按直觉作答。"
)


# ---------- 提示构建 ----------

def _fmt_options(options: list[dict]) -> list[str]:
    return [f"{LETTERS[i]}. {o['label']}" for i, o in enumerate(options)]


def _fmt_question(q: dict, index: int) -> str:
    lines = [f"第{index}题：{q['text']}"]
    lines += [f"  {opt}" for opt in _fmt_options(q["options"])]
    return "\n".join(lines)


def build_itemwise_message(q: dict, lang: str) -> list[dict]:
    """逐题模式：单题一次调用。lang='zh' 冻结原版；lang='en' 需翻译文件。"""
    if lang == "zh":
        user = f"{_fmt_question(q, 1)}"
        return [{"role": "system", "content": PROMPT_SYSTEM_ZH},
                {"role": "user", "content": user}]
    raise NotImplementedError("英文模板未就绪（见 docs/preregistration.md §4），禁止静默降级")


def build_full_message(order: list[dict], lang: str) -> list[dict]:
    """全量模式：全部题目一次调用。"""
    if lang == "zh":
        parts = [_fmt_question(q, i + 1) for i, q in enumerate(order)]
        user = "\n\n".join(parts)
        return [{"role": "system", "content": PROMPT_SYSTEM_FULL_ZH},
                {"role": "user", "content": user}]
    raise NotImplementedError("英文模板未就绪（见 docs/preregistration.md §4），禁止静默降级")


# ---------- 顺序控制 ----------

def build_order(order_mode: str, seed: int) -> list[dict]:
    """fixed：30 主题题号序 + 门控题固定末位。random：Fisher-Yates 打乱 + 门控随机插入。"""
    rng = random.Random(seed)
    main = list(ALL_MAIN)
    if order_mode == "random":
        rng.shuffle(main)
        pos = rng.randrange(0, len(main) + 1)
        seq = main[:pos] + [DRINK_GATE_Q1] + main[pos:]
    else:
        seq = main + [DRINK_GATE_Q1]
    return seq


# ---------- 解析 ----------

def _classify_failure(text: str) -> str:
    for marker in REFUSAL_MARKERS:
        if marker in text:
            return "refused"
    return "parse_error"


def parse_single(text: str) -> dict:
    """逐题输出：期望单个字母 A-D。"""
    m = SINGLE_LETTER_RE.search(text)
    if m and len(m.group(0)) == 1:
        return {"status": "ok", "letter": m.group(0)}
    return {"status": _classify_failure(text), "raw": text}


def parse_full(text: str, n_expected: int) -> dict:
    """全量输出：逐行提取首字母，需凑齐 n_expected 个。"""
    letters = []
    for line in text.splitlines():
        m = SINGLE_LETTER_RE.search(line)
        if m:
            letters.append(m.group(0))
        if len(letters) >= n_expected:
            break
    if len(letters) == n_expected:
        return {"status": "ok", "letters": letters}
    return {"status": _classify_failure(text), "raw": text}


# ---------- 主流程 ----------

def run_once(provider: str, model: str, mode: str, lang: str, order_mode: str,
             seed: int, temperature: float, rep: int, max_tokens: int) -> dict:
    seq = build_order(order_mode, seed)
    n_main = len(ALL_MAIN)  # 30
    total_items = len(seq)  # 31（含门控 q1）

    calls: list[dict] = []
    answers: dict[str, int] = {}
    letters_by_qid: dict[str, str] = {}

    def _do_call(messages: list[dict], qid: str) -> dict:
        rec = chat_completion(provider, model, messages,
                              temperature=temperature, max_tokens=max_tokens)
        calls.append({"qid": qid, "messages": messages, "response": rec["text"],
                      "usage": rec["usage"], "ts": datetime.now(timezone.utc).isoformat()})
        return rec

    if mode == "itemwise":
        for i, q in enumerate(seq, start=1):
            rec = _do_call(build_itemwise_message(q, lang), q["id"])
            parsed = parse_single(rec["text"])
            if parsed["status"] == "ok":
                idx = LETTERS.index(parsed["letter"])
                if idx < len(q["options"]):
                    answers[q["id"]] = q["options"][idx]["value"]
                    letters_by_qid[q["id"]] = parsed["letter"]
                else:
                    parsed = {"status": _classify_failure(rec["text"]), "raw": rec["text"]}
            calls[-1]["parsed"] = parsed

        # 酒鬼门控：q1 选 饮酒(3) -> 追加 q2
        if DRINK_GATE_Q1["id"] in answers and answers[DRINK_GATE_Q1["id"]] == CONFIG["drinkGate"]["triggerValue"]:
            rec = _do_call(build_itemwise_message(DRINK_GATE_Q2, lang), DRINK_GATE_Q2["id"])
            parsed = parse_single(rec["text"])
            if parsed["status"] == "ok":
                idx = LETTERS.index(parsed["letter"])
                if idx < len(DRINK_GATE_Q2["options"]):
                    answers[DRINK_GATE_Q2["id"]] = DRINK_GATE_Q2["options"][idx]["value"]
                    letters_by_qid[DRINK_GATE_Q2["id"]] = parsed["letter"]
                else:
                    parsed = {"status": _classify_failure(rec["text"]), "raw": rec["text"]}
            calls[-1]["parsed"] = parsed

    elif mode == "full":
        rec = _do_call(build_full_message(seq, lang), "ALL")
        parsed = parse_full(rec["text"], total_items)
        calls[-1]["parsed"] = parsed
        if parsed["status"] == "ok":
            for q, letter in zip(seq, parsed["letters"]):
                idx = LETTERS.index(letter)
                if idx < len(q["options"]):
                    answers[q["id"]] = q["options"][idx]["value"]
                    letters_by_qid[q["id"]] = letter
            # 门控 q2 在 full 模式下未包含，若 q1 命中饮酒则补一次逐题调用
            if answers.get(DRINK_GATE_Q1["id"]) == CONFIG["drinkGate"]["triggerValue"]:
                rec2 = _do_call(build_itemwise_message(DRINK_GATE_Q2, lang), DRINK_GATE_Q2["id"])
                p2 = parse_single(rec2["text"])
                if p2["status"] == "ok":
                    idx = LETTERS.index(p2["letter"])
                    if idx < len(DRINK_GATE_Q2["options"]):
                        answers[DRINK_GATE_Q2["id"]] = DRINK_GATE_Q2["options"][idx]["value"]
                        letters_by_qid[DRINK_GATE_Q2["id"]] = p2["letter"]
                    else:
                        p2 = {"status": _classify_failure(rec2["text"]), "raw": rec2["text"]}
                calls[-1]["parsed"] = p2

    # 状态统计
    statuses = [c.get("parsed", {}).get("status", "parse_error") for c in calls]
    is_drunk = (answers.get(DRINK_GATE_Q1["id"]) == CONFIG["drinkGate"]["triggerValue"]
                and answers.get(DRINK_GATE_Q2["id"]) == CONFIG["drinkGate"]["drunkTriggerValue"])

    scored = score_answers(answers, DATA, is_drunk=is_drunk) if answers else None

    return {
        "run_id": f"{provider}.{model}.{mode}.{lang}.{order_mode}.rep{rep:02d}.s{seed}",
        "provider": provider, "model": model, "mode": mode, "lang": lang,
        "order": order_mode, "rep": rep, "seed": seed, "temperature": temperature,
        "ts_start": datetime.now(timezone.utc).isoformat(),
        "seq": [q["id"] for q in seq],
        "calls": calls,
        "statuses": statuses,
        "n_ok": statuses.count("ok"),
        "n_parse_error": statuses.count("parse_error"),
        "n_refused": statuses.count("refused"),
        "total_tokens_in": sum(c["usage"].get("prompt_tokens", 0) for c in calls),
        "total_tokens_out": sum(c["usage"].get("completion_tokens", 0) for c in calls),
        "answers": answers,
        "letters": letters_by_qid,
        "is_drunk": is_drunk,
        "scoring": scored,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="SBTI × LLM 采集器")
    ap.add_argument("--provider", required=True, choices=sorted(
        __import__("providers").PROVIDERS.keys()))
    ap.add_argument("--model", required=True, help="模型标识（OpenAI 兼容）")
    ap.add_argument("--mode", required=True, choices=["itemwise", "full"])
    ap.add_argument("--lang", default="zh", choices=["zh", "en"])
    ap.add_argument("--order", default="random", choices=["fixed", "random"])
    ap.add_argument("--reps", type=int, default=20)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=None,
                    help="默认取 providers.PROVIDERS 的 default_max_tokens（如 xiaomi=2048），否则 128")
    args = ap.parse_args()

    import providers as prov_mod
    if args.max_tokens is None:
        args.max_tokens = prov_mod.PROVIDERS[args.provider].get("default_max_tokens", 128)

    if args.lang != "zh":
        sys.exit("lang='en' 尚未实现（预注册 §4 计划项），禁止降级，请先准备 data/i18n/en.json")

    raw_dir = ROOT / "results" / "raw"
    parsed_dir = ROOT / "results" / "parsed"
    raw_dir.mkdir(parents=True, exist_ok=True)
    parsed_dir.mkdir(parents=True, exist_ok=True)
    summary_path = ROOT / "results" / "summary.jsonl"

    from dotenv import load_dotenv
    # 仓库根 .env（smart-benchmark 是集合项目，所有子项目共用一个 .env）
    project_root = ROOT.parent
    load_dotenv(project_root / ".env")

    print(f"[collect] {args.provider}/{args.model} {args.mode} {args.lang} "
          f"order={args.order} reps={args.reps} temp={args.temperature}")
    with open(summary_path, "a", encoding="utf-8") as sf:
        for rep in range(1, args.reps + 1):
            seed = args.seed + rep  # 每 rep 独立种子（可复现）
            try:
                rec = run_once(args.provider, args.model, args.mode, args.lang,
                               args.order, seed, args.temperature, rep, args.max_tokens)
            except ProviderError as e:
                print(f"  [{rep:02d}] FAILED: {e}")
                sf.write(json.dumps({"run_id": f"{args.provider}.{args.model}.{args.mode}."
                                     f"{args.lang}.{args.order}.rep{rep:02d}.s{seed}",
                                     "provider": args.provider, "model": args.model,
                                     "mode": args.mode, "lang": args.lang, "order": args.order,
                                     "rep": rep, "seed": seed, "temperature": args.temperature,
                                     "failed": str(e)}, ensure_ascii=False) + "\n")
                sf.flush()
                continue
            rid = rec["run_id"]
            with open(raw_dir / f"{rid}.json", "w", encoding="utf-8") as f:
                json.dump(rec, f, ensure_ascii=False, indent=1)
            with open(parsed_dir / f"{rid}.json", "w", encoding="utf-8") as f:
                json.dump({"run_id": rid, "answers": rec["answers"],
                           "letters": rec["letters"], "is_drunk": rec["is_drunk"],
                           "scoring": rec["scoring"]}, f, ensure_ascii=False, indent=1)
            summary = {k: rec[k] for k in ("run_id", "provider", "model", "mode", "lang",
                                           "order", "rep", "seed", "temperature",
                                           "n_ok", "n_parse_error", "n_refused",
                                           "total_tokens_in", "total_tokens_out",
                                           "is_drunk")}
            if rec["scoring"]:
                summary["primary"] = rec["scoring"]["result"]["primary"]["code"]
                summary["primary_cn"] = rec["scoring"]["result"]["primary"]["cn"]
                summary["match_mode"] = rec["scoring"]["result"]["mode"]
                summary["similarity"] = rec["scoring"]["result"]["primary"]["similarity"]
                summary["dim_levels"] = rec["scoring"]["dim_levels"]
            sf.write(json.dumps(summary, ensure_ascii=False) + "\n")
            sf.flush()
            print(f"  [{rep:02d}] ok={rec['n_ok']} err={rec['n_parse_error']} "
                  f"ref={rec['n_refused']} primary={summary.get('primary')}")
    print("[collect] done.")


if __name__ == "__main__":
    main()

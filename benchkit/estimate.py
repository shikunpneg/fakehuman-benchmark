# -*- coding: utf-8 -*-
"""benchkit.estimate — benchmark 成本估算器。

设计目标：每次新建 benchmark 都能跑 `python -m benchkit.estimate --bench <name>`
直接给出"跑全量大概花多少钱"，用最便宜模型跑，且可缩放。

估算输入（都在估）：
  n_items      刺激条目数（数据文件长度）
  reps_per_item 每条重复次数
  n_models     受测模型数
  prompt_in    每条 prompt 的输入 token 估算
  resp_out     每条响应的输出 token 估算
  price_in/out 每百万 tokens 单价（providers.PRICING，估算值）

输出：总 token、各模型子项、总成本（人民币元）+ 告警。
"""
from __future__ import annotations

import json
import argparse
from collections import OrderedDict
from pathlib import Path

from benchkit import providers

ROOT = Path(__file__).resolve().parent.parent


def estimate(n_items: int, reps_per_item: int, n_models: int,
             prompt_in_tokens: int, resp_out_tokens: int,
             provider: str, model: str) -> dict:
    """估算一次 benchmark 全量的成本（人民币元）。"""
    price = providers.get_price(provider, model)
    calls = n_items * reps_per_item * n_models
    total_in = calls * prompt_in_tokens
    total_out = calls * resp_out_tokens

    if price is None:
        cost_in = cost_out = None
    else:
        cost_in = total_in / 1e6 * price["price_in"]
        cost_out = total_out / 1e6 * price["price_out"]
    total = (cost_in or 0) + (cost_out or 0)

    return OrderedDict([
        ("provider", provider),
        ("model", model),
        ("n_items", n_items),
        ("reps_per_item", reps_per_item),
        ("n_models", n_models),
        ("calls", calls),
        ("prompt_in_tokens", prompt_in_tokens),
        ("resp_out_tokens", resp_out_tokens),
        ("total_in_tokens", total_in),
        ("total_out_tokens", total_out),
        ("price_in_per_M", price["price_in"] if price else None),
        ("price_out_per_M", price["price_out"] if price else None),
        ("cost_in_cny", round(cost_in, 4) if cost_in is not None else None),
        ("cost_out_cny", round(cost_out, 4) if cost_out is not None else None),
        ("total_cost_cny", round(total, 4)),
        ("price_note", price["note"] if price else "未知价格，请补 PRICING 表"),
    ])


def _load_bench_meta(bench: str) -> dict | None:
    """读取 benches/<bench>/bench.json 的元数据，并合并 data/*.json 的条目数。"""
    meta: dict = {}
    p = ROOT / "benches" / bench / "bench.json"
    if p.exists():
        meta.update(json.loads(p.read_text(encoding="utf-8")))
    # 合并条目数：优先 data 目录里含 items 列表的 json
    data_dir = ROOT / "benches" / bench / "data"
    if data_dir.exists():
        for f in sorted(data_dir.glob("*.json")):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(d, dict) and isinstance(d.get("items"), list):
                    meta["n_items"] = len(d["items"])
                    break
            except Exception:
                continue
    return meta or None


def cmd(args: argparse.Namespace) -> None:
    meta = _load_bench_meta(args.bench)
    n_items = args.items or (meta.get("n_items") if meta else None)
    title = meta.get("title", args.bench) if meta else args.bench

    if n_items is None:
        n_items = int(input(f"[{title}] 刺激条目数（n_items）: ") or 0)
    reps = args.reps
    models = args.models or 1
    prompt_in = args.prompt_in
    resp_out = args.resp_out

    est = estimate(n_items, reps, models, prompt_in, resp_out,
                   args.provider, args.model)
    print(f"\n== 成本估算：{title} ==")
    print(f"  模型        : {est['provider']}/{est['model']}（{est['price_note']}）")
    print(f"  条目×重复×模型: {est['n_items']} × {est['reps_per_item']} × {est['n_models']} = {est['calls']} 次调用")
    print(f"  输入 tokens : {est['total_in_tokens']:,}  (每条 {est['prompt_in_tokens']})")
    print(f"  输出 tokens : {est['total_out_tokens']:,}  (每条 {est['resp_out_tokens']})")
    print(f"  单价 入/出  : {est['price_in_per_M']} / {est['price_out_per_M']} 元/百万")
    print(f"  输入成本    : {est['cost_in_cny']} 元")
    print(f"  输出成本    : {est['cost_out_cny']} 元")
    print(f"  ---------- 预计总成本: {est['total_cost_cny']} 元")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="benchkit 成本估算")
    ap.add_argument("--bench", required=True, help="bench 名（如 polite）")
    ap.add_argument("--provider", default="ark", help="provider（默认 ark=火山方舟）")
    ap.add_argument("--model", default="doubao-seed-2-0-lite-260428", help="模型")
    ap.add_argument("--items", type=int, default=None, help="刺激条目数（默认取 bench.json）")
    ap.add_argument("--reps", type=int, default=3, help="每条重复次数")
    ap.add_argument("--models", type=int, default=1, help="受测模型数（默认 1）")
    ap.add_argument("--prompt-in", type=int, default=40, help="每条 prompt 输入 token 估算")
    ap.add_argument("--resp-out", type=int, default=120, help="每条响应输出 token 估算")
    return ap


if __name__ == "__main__":
    cmd(build_parser().parse_args())

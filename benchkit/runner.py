# -*- coding: utf-8 -*-
"""benchkit.runner — 通用 benchmark 采集运行器。

把 sbti 里"逐题/全量 × 顺序 × 重复"的采集逻辑泛化为一个通用循环：
  items × reps × providers，逐条构建 prompt -> 调用 -> 记录。

bench 只需提供：
  - bench.json (metadata + 任务描述)
  - data/<bench>.json (刺激数据，含 items 列表)
  - 一个 `build_item(item, index)` 函数（在 src/collect.py 里定义）返回用户消息
  - 一个 `augment(rec, response)` 函数（可选）把回复转成评分字段

输出沿用 sbti 的审计布局：
  results/raw/{run_id}.json      完整请求/响应
  results/parsed/{run_id}.json   结构化评分
  results/summary.jsonl          每 run 一行汇总
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from benchkit import providers
from benchkit.refusal import classify, label_index, _core_terms

ROOT = Path(__file__).resolve().parent.parent


def run_benchmark(bench_name: str, provider: str, model: str,
                  build_item: Callable[[dict, int], str],
                  augment: Optional[Callable[[dict, str, dict], dict]] = None,
                  system_prompt: Optional[str] = None,
                  reps: int = 1, temperature: float = 0.0,
                  max_tokens: Optional[int] = None,
                  item_ids: Optional[list[str]] = None,
                  ref_levels: Optional[list[str]] = None,
                  verbose: bool = True) -> list[dict]:
    """采集一个 bench。返回完整 run 记录列表（并在磁盘落盘 raw/parsed/summary）。

    build_item(item, index) -> str：把一条刺激 build 成 user 消息。
    augment(rec, response, item) -> dict：可选，把原始响应转成评分字段。
    """
    data = load_bench_data(bench_name)
    items = data["items"]
    if item_ids is not None:
        items = [it for it in items if it["id"] in item_ids]
    if ref_levels is not None:
        items = [it for it in items if it.get("level") in ref_levels]
    n = len(items)
    if n == 0:
        raise ValueError(f"{bench_name}: 无可用 item（item_ids/ref_levels 过滤后为空）")

    raw_dir = ROOT / "benches" / bench_name / "results" / "raw"
    parsed_dir = ROOT / "benches" / bench_name / "results" / "parsed"
    raw_dir.mkdir(parents=True, exist_ok=True)
    parsed_dir.mkdir(parents=True, exist_ok=True)
    summary_path = ROOT / "benches" / bench_name / "results" / "summary.jsonl"

    if verbose:
        print(f"[{bench_name}] {provider}/{model} reps={reps} items={n} temp={temperature}")

    runs = []
    with open(summary_path, "a", encoding="utf-8") as sf:
        for i, item in enumerate(items, start=1):
            stimulus = item["text"]
            # 从刺激文本抽核心成分，供复述命中判定
            core = _core_terms(stimulus)
            user_msg = build_item(item, i)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": user_msg})

            for rep in range(1, reps + 1):
                run_id = (f"{bench_name}.{provider}.{model}.{item['id']}."
                          f"rep{rep:02d}.{int(time.time())}")
                rec = {
                    "run_id": run_id, "bench": bench_name,
                    "provider": provider, "model": model,
                    "item_id": item["id"], "level": item.get("level"),
                    "rep": rep, "temperature": temperature,
                    "ts_start": datetime.now(timezone.utc).isoformat(),
                    "stimulus": stimulus, "messages": messages,
                }
                try:
                    r = providers.chat_completion(provider, model, messages,
                                                  temperature=temperature,
                                                  max_tokens=max_tokens)
                except providers.ProviderError as e:
                    rec["response"] = None
                    rec["error"] = str(e)
                    runs.append(rec)
                    if verbose:
                        print(f"  [{i}/{n} rep{rep}] ERR {e}")
                    continue

                text = r.get("text", "")
                rec["response"] = text
                rec["usage"] = r.get("usage", {})
                rec["ts_end"] = datetime.now(timezone.utc).isoformat()

                # 评分：拒绝行为分类
                cls = classify(text, stimulus, core)
                rec["label"] = cls["label"]
                rec["label_cn"] = label_index().get(cls["label"], {}).get("cn", "")
                rec["label_reason"] = cls["reason"]
                rec["is_refusal"] = label_index().get(cls["label"], {}).get("is_refusal")
                rec["hits"] = cls["hits"]
                rec["total_tokens"] = (rec["usage"].get("prompt_tokens", 0)
                                       + rec["usage"].get("completion_tokens", 0))

                # 可选 augment 扩展评分字段
                if augment:
                    rec.update(augment(rec, text, item))

                # 落盘
                with open(raw_dir / f"{run_id}.json", "w", encoding="utf-8") as f:
                    json.dump(rec, f, ensure_ascii=False, indent=1)
                summary = {k: rec[k] for k in ("run_id", "bench", "provider", "model",
                                               "item_id", "level", "rep", "temperature",
                                               "label", "label_cn", "is_refusal",
                                               "total_tokens")}
                sf.write(json.dumps(summary, ensure_ascii=False) + "\n")
                sf.flush()
                runs.append(rec)
                if verbose:
                    print(f"  [{i}/{n} rep{rep}] {rec['label_cn']}")

    return runs


def load_bench_data(bench_name: str) -> dict:
    """读取 benches/<bench>/data/*.json，约定含 items 列表。"""
    data_dir = ROOT / "benches" / bench_name / "data"
    for f in sorted(data_dir.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if isinstance(d, dict) and isinstance(d.get("items"), list):
            return d
    raise FileNotFoundError(f"{bench_name}: data/ 下未找到含 items 的 json")


def estimate_call_counts(bench_name: str, provider: str, model: str,
                         reps: int = 1) -> int:
    """返回该 bench 全量跑一遍的调用次数（含条目数）。"""
    data = load_bench_data(bench_name)
    return len(data["items"]) * reps

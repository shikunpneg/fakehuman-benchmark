# -*- coding: utf-8 -*-
"""Phase 4 分析：读取 results/summary.jsonl 与 raw 存档，产出预注册 §6 指标。

输出：
  results/analysis/{model_comparison}.csv  模型×模式 汇总表
  results/analysis/figures/*.png           分布/聚类图
  results/analysis/report_stats.json       统计量 JSON
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SUMMARY = ROOT / "results" / "summary.jsonl"
RAW = ROOT / "results" / "raw"
OUT = ROOT / "results" / "analysis"


# ---------- 基础工具 ----------

def entropy(dist: list[float]) -> float:
    """香农熵（log2，归一化到 [0,1]）。"""
    if len(dist) <= 1:
        return 0.0
    h = -sum(p * math.log2(p) for p in dist if p > 0)
    return h / math.log2(len(dist))


def js_divergence(p: list[float], q: list[float]) -> float:
    """JS 散度。"""
    p = np.asarray(p, dtype=float)
    q = np.asarray(q, dtype=float)
    p /= p.sum()
    q /= q.sum()
    m = 0.5 * (p + q)
    def kl(a, b):
        a = np.clip(a, 1e-12, None)
        b = np.clip(b, 1e-12, None)
        return float(np.sum(a * np.log2(a / b)))
    return 0.5 * kl(p, m) + 0.5 * kl(q, m)


def load_runs() -> list[dict]:
    runs = []
    for line in SUMMARY.read_text(encoding="utf-8").splitlines():
        if line.strip():
            runs.append(json.loads(line))
    return [r for r in runs if not r.get("failed")]


def load_answers(run: dict) -> dict:
    """从 parsed 存档读该 run 的答案（失败/空则空 dict）。"""
    if not run.get("answers"):
        p = ROOT / "results" / "parsed" / f'{run["run_id"]}.json'
        if p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            return d.get("answers", {})
    return run.get("answers", {})


# ---------- 指标计算 ----------

def group_stats(runs: list[dict], mode_key: str = "mode") -> dict:
    """按 (provider, model, mode) 分组统计。"""
    groups = defaultdict(list)
    for r in runs:
        groups[(r["provider"], r["model"], r[mode_key])].append(r)

    out = {}
    for key, g in groups.items():
        provider, model, mode = key
        n = len(g)
        types = Counter(r.get("primary") for r in g if r.get("primary"))
        dim_levels = Counter()
        for r in g:
            for dim, lv in (r.get("dim_levels") or {}).items():
                dim_levels[(dim, lv)] += 1
        dim_level_counts = {f"{d}:{l}": c for (d, l), c in dim_levels.items()}

        # 选项一致率：任意两 run 间 answers 逐题一致比例
        ans_sets = [load_answers(r) for r in g]
        agree = []
        for i in range(n):
            for j in range(i + 1, n):
                a, b = ans_sets[i], ans_sets[j]
                if not a or not b:
                    continue
                common = set(a) & set(b)
                if not common:
                    continue
                same = sum(1 for q in common if a[q] == b[q])
                agree.append(same / len(common))
        option_agree = float(np.mean(agree)) if agree else None

        out[".".join(key)] = {
            "provider": provider, "model": model, "mode": mode, "n_runs": n,
            "primary_dist": dict(types.most_common()),
            "type_entropy": entropy([types[t] / n for t in types]),
            "drunk_rate": sum(1 for r in g if r.get("is_drunk")) / n,
            "option_agree_rate": option_agree,
            "dim_level_counts": dim_level_counts,
            "n_ok_total": sum(r.get("n_ok", 0) for r in g),
            "n_parse_error": sum(r.get("n_parse_error", 0) for r in g),
            "n_refused": sum(r.get("n_refused", 0) for r in g),
        }
    return out


def item_level_entropy(runs: list[dict], main_qids: list[str]) -> dict:
    """每题选择分布与熵（逐题模式；full 模式按题聚合亦可）。"""
    per_q = defaultdict(list)
    for r in runs:
        ans = load_answers(r)
        for q in main_qids:
            if q in ans:
                per_q[q].append(ans[q])
    out = {}
    for q, vals in per_q.items():
        c = Counter(vals)
        n = len(vals)
        out[q] = {"dist": {str(k): v / n for k, v in c.items()},
                  "entropy": entropy([c[k] / n for k in c]),
                  "n": n}
    return out


def model_pairwise_jsd(runs: list[dict], main_qids: list[str]) -> dict:
    """模型间选项分布 JS 散度矩阵。"""
    models = sorted({(r["provider"], r["model"]) for r in runs})
    dists = {}
    for p, m in models:
        grp = [r for r in runs if r["provider"] == p and r["model"] == m]
        d = item_level_entropy(grp, main_qids)
        dists[(p, m)] = d
    matrix = {}
    for i, k1 in enumerate(models):
        for k2 in models[i + 1:]:
            qs = [q for q in main_qids if q in dists[k1] and q in dists[k2]]
            vals = []
            for q in qs:
                d1, d2 = dists[k1][q]["dist"], dists[k2][q]["dist"]
                keys = list(set(d1) | set(d2))
                p = [d1.get(k, 0) for k in keys]
                q = [d2.get(k, 0) for k in keys]
                vals.append(js_divergence(p, q))
            matrix[f"{k1[0]}.{k1[1]} <-> {k2[0]}.{k2[1]}"] = float(np.mean(vals)) if vals else None
    return matrix


# ---------- 主入口 ----------

def main():
    from scoring import load_data, DATA_DIR
    data = load_data(DATA_DIR)
    main_qids = [q["id"] for q in data["questions"]["main"]]

    runs = load_runs()
    print(f"总 run 数: {len(runs)}")
    stats = group_stats(runs)
    print("\n== 模型×模式汇总 ==")
    for k, v in sorted(stats.items()):
        pd = v["primary_dist"]
        top = max(pd, key=pd.get) if pd else "-"
        print(f"  {k:55s} n={v['n_runs']:3d} top={top:8s} "
              f"typeEnt={v['type_entropy']:.2f} optAgree={v['option_agree_rate']} "
              f"drunk={v['drunk_rate']:.2f}")

    jsd = model_pairwise_jsd(runs, main_qids)
    print("\n== 模型间选项分布 JS 散度（均值） ==")
    for k, v in sorted(jsd.items()):
        print(f"  {k}: {v:.4f}" if v is not None else f"  {k}: -")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "report_stats.json").write_text(
        json.dumps({"groups": stats, "jsd": jsd}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"\n[analyze] 已写出 {OUT / 'report_stats.json'}")


if __name__ == "__main__":
    main()

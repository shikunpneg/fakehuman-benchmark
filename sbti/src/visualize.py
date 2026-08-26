# -*- coding: utf-8 -*-
"""Phase 4 可视化。

输出 results/analysis/figures/*.png：
  01_type_dist.png             模型×模式 主类型分布
  02_dim_heatmap.png           15 维 L/M/H 比例热图
  03_option_consistency.png    选项一致率与类型熵
  04_pca_clusters.png          PCA 15 维画像聚类
  05_hierarchical_dendrogram.png 层次聚类树状图
  06_per_question_entropy.png  逐题选项熵（哪些题分歧最大）
  07_pairwise_jsd_heatmap.png  模型间选项分布 JS 散度
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SUMMARY = ROOT / "results" / "summary.jsonl"
PARSED = ROOT / "results" / "parsed"
OUT = ROOT / "results" / "analysis"
FIG = OUT / "figures"
FIG.mkdir(parents=True, exist_ok=True)

# 中文字体（Windows 自带）
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False


# ---------- 数据加载 ----------

def load_runs() -> list[dict]:
    runs = []
    for line in SUMMARY.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            if not r.get("failed"):
                runs.append(r)
    return runs


def load_answers(rid: str) -> dict:
    p = PARSED / f"{rid}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8")).get("answers", {})
    return {}


def group_key(r: dict) -> str:
    return f"{r['provider']}.{r['model']}.{r['mode']}"


# ---------- 1. 类型分布 ----------

def fig01_type_dist(runs: list[dict]):
    rows = []
    for r in runs:
        rows.append({"group": group_key(r), "primary": r.get("primary") or "NONE",
                     "is_drunk": r.get("is_drunk", False)})
    df = pd.DataFrame(rows)
    if df.empty:
        return
    fig, ax = plt.subplots(figsize=(11, 5.5))
    ct = pd.crosstab(df["group"], df["primary"], normalize="index") * 100
    ct.plot(kind="bar", stacked=True, ax=ax, colormap="tab20", edgecolor="white", linewidth=0.4)
    ax.set_ylabel("类型占比 (%)")
    ax.set_xlabel("")
    ax.set_title("图 1：模型×模式主类型分布（100% 堆叠）")
    ax.legend(title="主类型", bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()
    fig.savefig(FIG / "01_type_dist.png", dpi=150)
    plt.close(fig)


# ---------- 2. 15 维热图 ----------

def fig02_dim_heatmap(runs: list[dict]):
    from scoring import load_data, DATA_DIR
    data = load_data(DATA_DIR)
    dims = data["dimensions"]["order"]

    groups = sorted({group_key(r) for r in runs})
    mat = {}
    for g in groups:
        grp = [r for r in runs if group_key(r) == g]
        counts = Counter()
        for r in grp:
            for d, lv in (r.get("dim_levels") or {}).items():
                counts[(d, lv)] += 1
        n = len(grp)
        # H 占比
        mat[g] = [counts[(d, "H")] / n for d in dims]

    if not mat:
        return
    arr = np.array([mat[g] for g in groups])
    fig, ax = plt.subplots(figsize=(12, max(3, 0.5 * len(groups))))
    im = ax.imshow(arr, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_xticks(range(len(dims)))
    ax.set_xticklabels(dims, rotation=45, ha="right", fontsize=9)
    ax.set_yticks(range(len(groups)))
    ax.set_yticklabels(groups, fontsize=10)
    ax.set_title("图 2：各模型×模式 15 维 H 等级占比热图（绿=高，红=低）")
    for i in range(arr.shape[0]):
        for j in range(arr.shape[1]):
            ax.text(j, i, f"{arr[i, j]:.2f}", ha="center", va="center", fontsize=7,
                    color="black" if arr[i, j] < 0.7 else "white")
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("H 占比")
    plt.tight_layout()
    fig.savefig(FIG / "02_dim_heatmap.png", dpi=150)
    plt.close(fig)


# ---------- 3. 稳定性（选项一致率 + 类型熵）----------

def _option_agree(grp: list[dict]) -> float | None:
    ans_list = []
    for r in grp:
        a = load_answers(r["run_id"])
        if a:
            ans_list.append(a)
    vals = []
    for i in range(len(ans_list)):
        for j in range(i + 1, len(ans_list)):
            common = set(ans_list[i]) & set(ans_list[j])
            if not common:
                continue
            same = sum(1 for q in common if ans_list[i][q] == ans_list[j][q])
            vals.append(same / len(common))
    return float(np.mean(vals)) if vals else None


def fig03_consistency(runs: list[dict]):
    groups = sorted({group_key(r) for r in runs})
    rows = []
    for g in groups:
        grp = [r for r in runs if group_key(r) == g]
        n = len(grp)
        types = Counter(r.get("primary") for r in grp if r.get("primary"))
        type_ent = 0.0
        if len(types) > 1:
            p = [c / n for c in types.values()]
            type_ent = -sum(pi * math.log2(pi) for pi in p if pi > 0) / math.log2(len(types))
        opt_agree = _option_agree(grp)
        rows.append({"group": g, "n": n, "type_entropy": type_ent, "option_agree": opt_agree,
                     "drunk_rate": sum(r.get("is_drunk", False) for r in grp) / n})
    if not rows:
        return
    df = pd.DataFrame(rows)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    x = np.arange(len(df))
    axes[0].bar(x, df["option_agree"].fillna(0), color=["#4c72b0" if "itemwise" in g else "#dd8452" for g in df["group"]])
    axes[0].set_xticks(x); axes[0].set_xticklabels(df["group"], rotation=20, ha="right")
    axes[0].set_ylabel("选项一致率"); axes[0].set_ylim(0, 1.05)
    axes[0].set_title("图 3a：选项一致率（逐题/全量对比）")
    axes[1].bar(x, df["type_entropy"], color=["#4c72b0" if "itemwise" in g else "#dd8452" for g in df["group"]])
    axes[1].set_xticks(x); axes[1].set_xticklabels(df["group"], rotation=20, ha="right")
    axes[1].set_ylabel("类型熵（归一化）"); axes[1].set_ylim(0, 1.05)
    axes[1].set_title("图 3b：类型熵（越大=人格越不稳定）")
    plt.tight_layout()
    fig.savefig(FIG / "03_option_consistency.png", dpi=150)
    plt.close(fig)
    df.to_csv(OUT / "stability_summary.csv", index=False, encoding="utf-8-sig")


# ---------- 4. PCA 聚类 ----------

def fig04_pca(runs: list[dict]):
    from scoring import load_data, DATA_DIR
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler
    data = load_data(DATA_DIR)
    dims = data["dimensions"]["order"]

    rows, groups, labels = [], [], []
    for r in runs:
        dl = r.get("dim_levels") or {}
        if not all(d in dl for d in dims):
            continue
        # L=1, M=2, H=3
        vec = [{"L": 1, "M": 2, "H": 3}[dl[d]] for d in dims]
        rows.append(vec); groups.append(group_key(r)); labels.append(r.get("primary") or "NONE")

    if len(rows) < 4:
        return
    X = np.array(rows, dtype=float)
    X_scaled = StandardScaler().fit_transform(X)
    pca = PCA(n_components=2)
    pcs = pca.fit_transform(X_scaled)

    fig, ax = plt.subplots(figsize=(11, 7))
    group_set = sorted(set(groups))
    cmap = plt.get_cmap("tab10")
    markers = {"itemwise": "o", "full": "s"}
    for gi, g in enumerate(group_set):
        mask = np.array([gs == g for gs in groups])
        mk = markers["full"] if g.endswith(".full") else markers["itemwise"]
        ax.scatter(pcs[mask, 0], pcs[mask, 1], c=[cmap(gi % 10)], marker=mk,
                   s=90, edgecolors="black", linewidths=0.6, alpha=0.7, label=g)
    ax.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]*100:.1f}%)")
    ax.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]*100:.1f}%)")
    ax.set_title("图 4：15 维画像 PCA（● 逐题 ■ 全量）")
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=9)
    ax.grid(alpha=0.3)
    plt.tight_layout()
    fig.savefig(FIG / "04_pca_clusters.png", dpi=150)
    plt.close(fig)


# ---------- 5. 层次聚类 ----------

def fig05_dendrogram(runs: list[dict]):
    from scipy.cluster.hierarchy import linkage, dendrogram
    from scipy.spatial.distance import pdist
    from scoring import load_data, DATA_DIR
    data = load_data(DATA_DIR)
    dims = data["dimensions"]["order"]

    groups = sorted({group_key(r) for r in runs})
    means = []
    for g in groups:
        grp = [r for r in runs if group_key(r) == g and r.get("dim_levels")]
        if not grp:
            continue
        m = np.mean([[{"L": 1, "M": 2, "H": 3}[r["dim_levels"].get(d, "M")] for d in dims] for r in grp], axis=0)
        means.append((g, m))

    if len(means) < 3:
        return
    M = np.vstack([m for _, m in means])
    Z = linkage(pdist(M), method="ward")
    fig, ax = plt.subplots(figsize=(10, max(4, 0.5 * len(means))))
    dendrogram(Z, labels=[g for g, _ in means], ax=ax, leaf_rotation=20,
               color_threshold=0)
    ax.set_ylabel("Ward 距离")
    ax.set_title("图 5：模型×模式 15 维均值画像层次聚类")
    plt.tight_layout()
    fig.savefig(FIG / "05_hierarchical_dendrogram.png", dpi=150)
    plt.close(fig)


# ---------- 6. 逐题选项熵 ----------

def fig06_question_entropy(runs: list[dict]):
    from scoring import load_data, DATA_DIR
    data = load_data(DATA_DIR)
    main_qids = [q["id"] for q in data["questions"]["main"]]

    groups = sorted({group_key(r) for r in runs})
    per_group_per_q = {g: defaultdict(Counter) for g in groups}
    for r in runs:
        g = group_key(r)
        a = load_answers(r["run_id"])
        for q in main_qids:
            if q in a:
                per_group_per_q[g][q][a[q]] += 1

    rows = []
    for g in groups:
        for q in main_qids:
            c = per_group_per_q[g].get(q)
            if not c:
                continue
            n = sum(c.values())
            p = [v / n for v in c.values()]
            if len(p) > 1:
                ent = -sum(pi * math.log2(pi) for pi in p) / math.log2(len(p))
            else:
                ent = 0.0
            rows.append({"group": g, "q": q, "entropy": ent, "n": n})

    if not rows:
        return
    df = pd.DataFrame(rows)
    pivot = df.pivot_table(index="q", columns="group", values="entropy")
    fig, ax = plt.subplots(figsize=(11, 6))
    im = ax.imshow(pivot.values, aspect="auto", cmap="viridis", vmin=0, vmax=1)
    ax.set_xticks(range(len(pivot.columns))); ax.set_xticklabels(pivot.columns, rotation=20, ha="right")
    ax.set_yticks(range(len(pivot.index))); ax.set_yticklabels(pivot.index)
    ax.set_title("图 6：逐题选项熵（越亮=分歧越大=该题对模型区分度越高）")
    fig.colorbar(im, ax=ax, label="熵")
    plt.tight_layout()
    fig.savefig(FIG / "06_per_question_entropy.png", dpi=150)
    plt.close(fig)


# ---------- 7. JS 散度矩阵 ----------

def fig07_jsd(runs: list[dict]):
    from scoring import load_data, DATA_DIR
    from itertools import combinations
    data = load_data(DATA_DIR)
    main_qids = [q["id"] for q in data["questions"]["main"]]

    def js(p, q):
        p = np.asarray(p, dtype=float); q = np.asarray(q, dtype=float)
        p /= p.sum() if p.sum() > 0 else 1
        q /= q.sum() if q.sum() > 0 else 1
        m = 0.5 * (p + q)
        def kl(a, b):
            a = np.clip(a, 1e-12, None); b = np.clip(b, 1e-12, None)
            return float(np.sum(a * np.log2(a / b)))
        return 0.5 * kl(p, m) + 0.5 * kl(q, m)

    groups = sorted({group_key(r) for r in runs})
    dists_per_q = {g: defaultdict(Counter) for g in groups}
    for r in runs:
        g = group_key(r)
        a = load_answers(r["run_id"])
        for q in main_qids:
            if q in a:
                dists_per_q[g][q][a[q]] += 1

    M = np.zeros((len(groups), len(groups)))
    for i, g1 in enumerate(groups):
        for j, g2 in enumerate(groups):
            if i >= j:
                continue
            vals = []
            for q in main_qids:
                if q in dists_per_q[g1] and q in dists_per_q[g2]:
                    keys = sorted(set(dists_per_q[g1][q]) | set(dists_per_q[g2][q]))
                    p = [dists_per_q[g1][q].get(k, 0) for k in keys]
                    q_ = [dists_per_q[g2][q].get(k, 0) for k in keys]
                    vals.append(js(p, q_))
            M[i, j] = M[j, i] = float(np.mean(vals)) if vals else 0.0

    fig, ax = plt.subplots(figsize=(8, 7))
    im = ax.imshow(M, cmap="magma", vmin=0, vmax=M.max() if M.max() > 0 else 1)
    ax.set_xticks(range(len(groups))); ax.set_xticklabels(groups, rotation=20, ha="right")
    ax.set_yticks(range(len(groups))); ax.set_yticklabels(groups)
    ax.set_title("图 7：模型×模式 选项分布 JS 散度矩阵")
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            if M[i, j] > 0:
                ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center",
                        color="white" if M[i, j] > M.max() * 0.5 else "black", fontsize=8)
    fig.colorbar(im, ax=ax, label="JS 散度")
    plt.tight_layout()
    fig.savefig(FIG / "07_pairwise_jsd_heatmap.png", dpi=150)
    plt.close(fig)


# ---------- 主入口 ----------

def main():
    runs = load_runs()
    print(f"[viz] runs={len(runs)} groups={len({group_key(r) for r in runs})}")
    for fn, name in [(fig01_type_dist, "类型分布"),
                     (fig02_dim_heatmap, "维度热图"),
                     (fig03_consistency, "一致性"),
                     (fig04_pca, "PCA"),
                     (fig05_dendrogram, "层次聚类"),
                     (fig06_question_entropy, "逐题熵"),
                     (fig07_jsd, "JS 散度矩阵")]:
        try:
            fn(runs)
            print(f"  ok: {name}")
        except Exception as e:
            print(f"  FAIL {name}: {type(e).__name__}: {e}")
    print(f"[viz] done -> {FIG}")


if __name__ == "__main__":
    main()
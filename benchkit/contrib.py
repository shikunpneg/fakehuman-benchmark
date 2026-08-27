# -*- coding: utf-8 -*-
"""
benchkit.contrib — 结果贡献 + PR 提交流（通过 gh CLI）。

用法：
    python -m benchkit.contrib submit --bench polite --provider ark --model doubao-seed-2-0-mini-260428
    python -m benchkit.contrib submit --bench sbti --provider deepseek --model deepseek-chat
    python -m benchkit.contrib status   # 查看当前 gh auth 状态
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from benchkit import leaderboard as lb_module


# --------------------------------------------------------------------------
# gh CLI 封装
# --------------------------------------------------------------------------

def run_gh(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    """运行 gh 命令，返回 CompletedProcess。"""
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)
    kwargs.setdefault("encoding", "utf-8", )
    kwargs.setdefault("errors", "replace")
    result = subprocess.run(["gh"] + args, **kwargs)
    return result


def gh_auth_check() -> bool:
    """检查 gh 是否已登录。"""
    result = run_gh(["auth", "status"])
    return result.returncode == 0


def gh_current_branch() -> str | None:
    """获取当前分支名。"""
    result = run_gh(["branch", "--show-current"])
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def gh_create_pr(title: str, body: str, base: str = "main") -> tuple[bool, str]:
    """
    创建 GitHub PR。
    返回 (success, pr_url_or_error_message)
    """
    # 先检查是否可以创建 PR
    result = run_gh(["pr", "create",
                      "--title", title,
                      "--body", body,
                      "--base", base,
                      "--web", "false"])
    if result.returncode == 0:
        # gh pr create 输出 PR URL
        url = result.stdout.strip()
        return True, url
    else:
        return False, result.stderr.strip()


def gh_get_remote() -> tuple[str, str] | None:
    """获取当前 repo 的 remote (name, url)。"""
    result = run_gh(["remote", "--verbose"])
    if result.returncode != 0:
        return None
    for line in result.stdout.strip().splitlines():
        parts = line.split()
        if len(parts) >= 2:
            name = parts[0]
            url = parts[1].replace("(fetch)", "").replace("(push)", "").strip()
            return name, url
    return None


def gh_get_default_branch() -> str:
    """获取远程默认分支（main 或 master）。"""
    result = run_gh(["repo", "view", "--json", "defaultBranchRef", "--jq", ".defaultBranchRef.name"])
    if result.returncode == 0:
        return result.stdout.strip().replace("refs/heads/", "")
    return "main"


# --------------------------------------------------------------------------
# Leaderboard 更新逻辑
# --------------------------------------------------------------------------

def load_leaderboard() -> dict:
    """读取现有 leaderboard.json，不存在则返回空结构。"""
    lb_path = ROOT / "leaderboard.json"
    if lb_path.exists():
        return json.loads(lb_path.read_text(encoding="utf-8"))
    return {
        "version": "1.0",
        "updated_at": str(date.today()),
        "benchmarks": {},
    }


def update_leaderboard_entry(lb: dict, bench_id: str, bench_yaml: dict,
                              summary: dict) -> dict:
    """用新的 summary 数据更新 leaderboard 中指定模型的条目。"""
    if "benchmarks" not in lb:
        lb["benchmarks"] = {}

    if bench_id not in lb["benchmarks"]:
        lb["benchmarks"][bench_id] = {
            "id": bench_id,
            "title": bench_yaml.get("title", bench_id),
            "description": bench_yaml.get("description", ""),
            "category": bench_yaml.get("category", ""),
            "metrics": bench_yaml.get("metrics", []),
            "models": {},
        }

    bench_info = lb["benchmarks"][bench_id]
    by_model = summary.get("by_model", {})
    extracted = lb_module._extract_models(bench_id, summary, bench_yaml)

    for model_name, model_data in extracted.items():
        bench_info["models"][model_name] = {
            **model_data,
            "last_updated": str(date.today()),
        }

    lb["updated_at"] = str(date.today())
    return lb


def generate_pr_body(bench_id: str, model_name: str, model_data: dict,
                      bench_yaml: dict, existing_entry: dict | None) -> str:
    """生成 PR 描述内容。"""
    title = bench_yaml.get("title", bench_id)
    metrics = model_data.get("metrics", {})

    # 构建指标摘要行
    if bench_id == "polite":
        rr = metrics.get("refusal_rate", {})
        cr = metrics.get("comply_rate", {})
        metric_lines = [
            f"- **整体拒绝率**: {rr.get('overall', 'N/A')}",
            f"- **min 拒绝率**: {rr.get('min', 'N/A')} | **max 拒绝率**: {rr.get('max', 'N/A')}",
            f"- **顺从复述率**: {cr.get('overall', 'N/A')}",
            f"- **运行次数**: {model_data.get('n_runs', 'N/A')}",
        ]
    elif bench_id == "sbti":
        ocr = metrics.get("option_consistency_rate", "N/A")
        te = metrics.get("type_entropy", "N/A")
        metric_lines = [
            f"- **选项一致率**: {ocr}",
            f"- **类型熵**: {te}",
            f"- **运行次数**: {model_data.get('n_runs', 'N/A')}",
        ]
    else:
        metric_lines = [f"- **{k}**: {v}" for k, v in metrics.items()]

    body = f"""## {title} — 新增结果

**模型**: `{model_name}`
**Provider**: {model_data.get('provider', 'N/A')}
**日期**: {str(date.today())}

### 指标摘要
{chr(10).join(metric_lines)}

### 变更说明
- 更新 `leaderboard.json` 和 `LEADERBOARD.md`
- 原始数据: `benchmarks/{bench_id}/results/analysis/`

---
_此 PR 由 [benchkit.contrib](https://github.com/shikunpneg/smart-benchmark) 自动生成_。
"""
    return body


# --------------------------------------------------------------------------
# 提交流程
# --------------------------------------------------------------------------

def submit(bench_id: str, provider: str, model: str,
           branch_suffix: str | None = None,
           base_branch: str | None = None,
           dry_run: bool = False) -> int:
    """
    提交 benchmark 结果的完整流程：
    1. 检查 gh auth
    2. 读取/更新 leaderboard.json
    3. 生成 markdown
    4. 创建新分支
    5. commit
    6. 创建 PR
    """
    if not gh_auth_check():
        print("[contrib] ERROR: gh 未登录。请先运行 `gh auth login`。", file=sys.stderr)
        print("           或者使用 --dry-run 查看将要提交的内容。")
        return 1

    # 1. 加载 bench.yaml
    bench_yaml_path = ROOT / "benchmarks" / bench_id / "bench.yaml"
    if not bench_yaml_path.exists():
        print(f"[contrib] ERROR: benchmarks/{bench_id}/bench.yaml 不存在", file=sys.stderr)
        return 1

    bench_yaml = lb_module.load_yaml(bench_yaml_path)

    # 2. 读取 summary 数据
    summary = lb_module.load_bench_summary(bench_id, bench_yaml)
    if not summary:
        print(f"[contrib] ERROR: benchmarks/{bench_id}/results/ 下未找到汇总数据", file=sys.stderr)
        print("           请先运行 collect.py 和 analyze.py 生成结果。")
        return 1

    # 3. 更新 leaderboard
    lb = load_leaderboard()
    existing = lb.get("benchmarks", {}).get(bench_id, {}).get("models", {}).get(model)
    lb = update_leaderboard_entry(lb, bench_id, bench_yaml, summary)
    new_entry = lb["benchmarks"][bench_id]["models"].get(model, {})

    # 4. 写文件
    repo_root = lb_module.find_repo_root()
    lb_path = repo_root / "leaderboard.json"
    md_path = repo_root / "LEADERBOARD.md"

    if dry_run:
        print("[dry-run] 即将写入：")
        print(f"  -> {lb_path}")
        print(f"  -> {md_path}")
        print(f"\n新增/更新模型 {model}:")
        print(json.dumps(new_entry, ensure_ascii=False, indent=2))
        return 0

    lb_path.write_text(json.dumps(lb, ensure_ascii=False, indent=2), encoding="utf-8")
    md_content = lb_module.generate_markdown(lb)
    md_path.write_text(md_content, encoding="utf-8")
    print(f"[contrib] 已更新 leaderboard.json 和 LEADERBOARD.md")

    # 5. 创建新分支
    default_base = base_branch or gh_get_default_branch()
    current = gh_current_branch() or default_base
    if current != default_base:
        print(f"[contrib] 当前分支: {current}，将基于 {default_base} 创建新分支")
        base_branch_flag = ["--base", default_base]
    else:
        base_branch_flag = []

    import datetime as dt
    ts = dt.datetime.now().strftime("%Y%m%d%H%M")
    branch_name = branch_suffix or f"feat/{bench_id}-{model}-{ts}"
    result = run_gh(["checkout", "-b", branch_name, *base_branch_flag])
    if result.returncode != 0:
        print(f"[contrib] WARNING: 创建分支失败（可能已存在）: {result.stderr}", file=sys.stderr)

    # 6. Commit
    commit_files = [str(lb_path.relative_to(ROOT)), str(md_path.relative_to(ROOT))]
    run_gh(["add", *commit_files])
    result = run_gh(["commit", "-m", f"feat(leaderboard): update {bench_id}/{model} results\n\n"
                                      f"Bench: {bench_id}\nModel: {model}\n"
                                      f"Provider: {provider}\nDate: {str(date.today())}"])
    if result.returncode != 0:
        if "nothing to commit" in result.stdout:
            print("[contrib] 没有新变更需要提交（数据与 leaderboard 中一致）。")
            return 0
        print(f"[contrib] WARNING: commit 失败: {result.stderr}", file=sys.stderr)

    # 7. Push
    print(f"[contrib] 正在 push 分支: {branch_name} ...")
    result = run_gh(["push", "-u", "origin", branch_name, "--quiet"])
    if result.returncode != 0:
        print(f"[contrib] ERROR: push 失败: {result.stderr}", file=sys.stderr)
        print("           请检查 gh auth 和网络连接。")
        return 1

    # 8. 创建 PR
    pr_body = generate_pr_body(bench_id, model, new_entry, bench_yaml, existing)
    pr_title = f"feat(leaderboard): {bench_id} — 新增 {model} 结果"

    print(f"[contrib] 正在创建 PR ...")
    ok, pr_result = gh_create_pr(pr_title, pr_body, base=default_base)
    if ok:
        print(f"[contrib] ✅ PR 已创建: {pr_result}")
        print(f"           请访问: {pr_result}")
    else:
        print(f"[contrib] ERROR: PR 创建失败: {pr_result}", file=sys.stderr)
        print("           分支已 push，可手动在 GitHub 上创建 PR。")
        return 1

    return 0


# --------------------------------------------------------------------------
# CLI 入口
# --------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="benchkit 结果贡献工具（gh CLI）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # submit 子命令
    p = sub.add_parser("submit", help="提交 benchmark 结果到 leaderboard 并创建 PR")
    p.add_argument("--bench", required=True, help="Benchmark ID（如 polite, sbti）")
    p.add_argument("--provider", required=True, help="Provider 名（如 ark, deepseek, 4api）")
    p.add_argument("--model", required=True, help="模型名（如 doubao-seed-2-0-mini-260428）")
    p.add_argument("--branch", dest="branch_suffix", help="分支名后缀（默认自动生成）")
    p.add_argument("--base", dest="base_branch", help="PR 目标分支（默认 main）")
    p.add_argument("--dry-run", action="store_true", help="只预览，不写文件不推 PR")

    # status 子命令
    s = sub.add_parser("status", help="查看 gh auth 状态和当前 leaderboard")
    s.add_argument("--bench", help="只看某个 benchmark")

    args = parser.parse_args()

    if args.cmd == "submit":
        return submit(
            bench_id=args.bench,
            provider=args.provider,
            model=args.model,
            branch_suffix=args.branch_suffix,
            base_branch=args.base_branch,
            dry_run=args.dry_run,
        )
    elif args.cmd == "status":
        ok = gh_auth_check()
        if ok:
            print("✅ gh 已登录")
        else:
            print("❌ gh 未登录，请运行: gh auth login")
            return 1

        lb = lb_module.load_all_benches()
        print(f"\n已注册的 benchmarks ({len(lb)}):")
        for bid in sorted(lb):
            print(f"  - {bid}: {lb[bid].get('title', '')}")

        lb_data = lb_module.load_leaderboard(Path("leaderboard.json").resolve())
        n_models = sum(len(b.get("models", {})) for b in lb_data.get("benchmarks", {}).values())
        print(f"\nleaderboard.json 模型数: {n_models}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())

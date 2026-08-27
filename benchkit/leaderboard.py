# -*- coding: utf-8 -*-
"""
benchkit.leaderboard — 跨 benchmark 聚合排行榜。

用法：
    python -m benchkit.leaderboard                      # 全量生成
    python -m benchkit.leaderboard --bench polite       # 只生成某个 benchmark
    python -m benchkit.leaderboard --output ./leaderboard.json   # 指定输出路径
    python -m benchkit.leaderboard --dry-run            # 只打印，不写文件
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

# benchkit 同级目录
ROOT = Path(__file__).resolve().parent.parent
BENCHMARK_DIR = ROOT / "benchmarks"


def find_repo_root() -> Path:
    cur = Path(__file__).resolve().parent
    for _ in range(6):
        if (cur / ".env").exists():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return cur


def load_yaml(path: Path) -> dict:
    """使用 pyyaml 解析 bench.yaml。"""
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        # pyyaml 未安装，使用简单备用解析器
        return _load_yaml_fallback(path)


def _load_yaml_fallback(path: Path) -> dict:
    """纯 Python YAML fallback（支持基础列表和嵌套）。"""
    import re
    text = path.read_text(encoding="utf-8")
    result: dict = {}
    stack: list[tuple[str, dict]] = [(None, result)]
    current_key: str | None = None
    current_list: list | None = None
    indent_stack: list[int] = [0]

    def close_all_to(indent: int):
        while indent_stack[-1] >= indent and len(stack) > 1:
            indent_stack.pop()
            stack.pop()

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(stripped)
        close_all_to(indent)

        parent_key, parent_dict = stack[-1]

        # 列表项
        if stripped.startswith("- "):
            if current_list is None:
                current_list = []
                if current_key:
                    parent_dict[current_key] = current_list
                else:
                    parent_dict[parent_key] = current_list
            current_list.append(stripped[2:].strip('"\''))
            continue
        else:
            current_list = None

        # key: value
        m = re.match(r"^(\w[\w_-]+):\s*(.*)$", stripped)
        if m:
            k, v = m.group(1), m.group(2).strip()
            current_key = k
            if not v or v in ('|', '>'):
                # 下一行开始是嵌套内容
                indent_stack.append(indent + 2)
                stack.append((k, {}))
                parent_dict[k] = {}
            elif v.startswith('"') or v.startswith("'"):
                parent_dict[k] = v.strip('"\'')
            elif v == "true" or v == "false":
                parent_dict[k] = v == "true"
            elif v == "null" or v == "~":
                parent_dict[k] = None
            elif re.match(r"^\d+(\.\d+)?$", v):
                parent_dict[k] = float(v) if "." in v else int(v)
            else:
                parent_dict[k] = v

    return result


def load_bench_summary(bench_id: str, bench_yaml: dict) -> dict | None:
    """读取某个 benchmark 的 analysis/refusal_summary.json 或类似的汇总文件。"""
    # bench.yaml 位于 benchmarks/{id}/bench.yaml
    bench_yaml_dir = BENCHMARK_DIR / bench_id
    results_dir_raw = bench_yaml.get("results_dir", "")
    if results_dir_raw:
        # results_dir 是相对于 bench.yaml 父目录的路径
        results_dir = (bench_yaml_dir / results_dir_raw).resolve()
    else:
        results_dir = bench_yaml_dir / "results"

    # 尝试多种可能的汇总文件路径
    candidates = [
        results_dir / "analysis" / "refusal_summary.json",   # polite
        results_dir / "analysis" / "stability_summary.csv",  # sbti
        results_dir / "summary.json",
        results_dir / "summary.jsonl",
    ]
    summary_path = None
    for p in candidates:
        if p.exists():
            summary_path = p
            break
    if summary_path is None:
        return None

    return _parse_summary(summary_path)


def _parse_summary(path: Path) -> dict:
    """解析 summary 文件（JSON / JSONL / CSV）。"""
    try:
        # SBTI stability_summary.csv
        if path.name == "stability_summary.csv":
            csv_lines = path.read_text(encoding="utf-8").splitlines()
            return _aggregate_sbti(csv_lines)

        if path.suffix == ".jsonl":
            records = []
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except Exception:
                        continue
            if records:
                return _aggregate_sbti(records)
            return {}
        else:
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[leaderboard] 解析 {path} 失败: {e}", file=sys.stderr)
        return {}


def _aggregate_sbti(records: list[dict]) -> dict:
    """SBTI 专用聚合：从 stability_summary.csv 读取选项一致率和类型熵。"""
    csv_lines = records if isinstance(records, list) and isinstance(records[0], str) else []
    by_model: dict = {}

    for line in csv_lines[1:]:  # skip header row
        parts = line.strip().split(",")
        if len(parts) < 5:
            continue

        group = parts[0]
        n = int(parts[1])
        type_entropy = float(parts[2])
        option_agree = float(parts[3])

        # group 格式: provider.model.mode (如 "4api.glm-4.7.full")
        # 提取: provider=parts[0], mode=parts[-1], model=".".join(parts[1:-1])
        dot_parts = group.split(".")
        if len(dot_parts) < 3:
            continue  # 无效格式

        provider = dot_parts[0]
        mode = dot_parts[-1]
        model = ".".join(dot_parts[1:-1])  # e.g. "glm-4.7" from "4api.glm-4.7.full"

        # 只取 full 模式（更稳定）；若已有 full 条目则跳过 itemwise
        is_full = (mode == "full")
        if model in by_model and not is_full:
            continue

        by_model[model] = {
            "provider": provider,
            "n_runs": n,
            "option_consistency_rate": round(option_agree, 4),
            "type_entropy": round(type_entropy, 4),
            "metrics": {
                "option_consistency_rate": round(option_agree, 4),
                "type_entropy": round(type_entropy, 4),
            },
        }

    return {"by_model": by_model}


def load_all_benches() -> dict[str, dict]:
    """扫描 benchmarks/ 下所有 bench.yaml，返回 {bench_id: bench_yaml}。"""
    benches = {}
    if not BENCHMARK_DIR.exists():
        print(f"[leaderboard] benchmarks/ 目录不存在: {BENCHMARK_DIR}", file=sys.stderr)
        return benches
    for bench_dir in sorted(BENCHMARK_DIR.iterdir()):
        if not bench_dir.is_dir():
            continue
        yaml_path = bench_dir / "bench.yaml"
        if yaml_path.exists():
            try:
                benches[bench_dir.name] = load_yaml(yaml_path)
            except Exception as e:
                print(f"[leaderboard] 加载 {yaml_path} 失败: {e}", file=sys.stderr)
    return benches


def build_leaderboard(bench_filter: str | None = None) -> dict:
    """聚合所有 benchmark 的结果，生成 leaderboard 数据结构。"""
    benches = load_all_benches()
    result = {
        "version": "1.0",
        "updated_at": str(date.today()),
        "updated_by": "benchkit.leaderboard",
        "benchmarks": {},
    }

    for bench_id, bench_yaml in sorted(benches.items()):
        if bench_filter and bench_id != bench_filter:
            continue

        bench_info = {
            "id": bench_id,
            "title": bench_yaml.get("title", bench_id),
            "description": bench_yaml.get("description", ""),
            "category": bench_yaml.get("category", ""),
            "metrics": bench_yaml.get("metrics", []),
            "models": {},
            "_bench_yaml": str(BENCHMARK_DIR / bench_id / "bench.yaml"),
        }

        summary = load_bench_summary(bench_id, bench_yaml)
        if summary and "by_model" in summary:
            bench_info["models"] = _extract_models(bench_id, summary, bench_yaml)

        result["benchmarks"][bench_id] = bench_info

    return result


def _extract_models(bench_id: str, summary: dict, bench_yaml: dict) -> dict:
    """从 summary 提取各模型的指标。"""
    models_out = {}
    by_model = summary.get("by_model", {})

    for model_name, model_data in by_model.items():
        if bench_id == "polite":
            all_d = model_data.get("all", {})
            min_d = model_data.get("min", {})
            max_d = model_data.get("max", {})
            models_out[model_name] = {
                "provider": _guess_provider(model_name),
                "n_runs": all_d.get("n", 0),
                "metrics": {
                    "refusal_rate": {
                        "overall": all_d.get("refusal_rate"),
                        "min": min_d.get("refusal_rate"),
                        "max": max_d.get("refusal_rate"),
                    },
                    "comply_rate": {
                        "overall": all_d.get("comply_rate"),
                        "min": min_d.get("comply_rate"),
                        "max": max_d.get("comply_rate"),
                    },
                },
            }
        elif bench_id == "sbti":
            models_out[model_name] = {
                "provider": model_data.get("provider", ""),
                "n_runs": model_data.get("n_runs", 0),
                "metrics": model_data.get("metrics", {}),
            }
        else:
            # 通用：直接透传 metrics
            models_out[model_name] = {
                "provider": model_data.get("provider", ""),
                "n_runs": model_data.get("n_runs", 0),
                "metrics": model_data.get("metrics", {}),
            }

    return models_out


def _guess_provider(model_name: str) -> str:
    """根据模型名猜测 provider。"""
    if "doubao" in model_name or "seed" in model_name:
        return "ark"
    if "deepseek" in model_name:
        return "deepseek"
    if "kimi" in model_name or "moonshot" in model_name:
        return "4api"
    if "glm" in model_name:
        return "4api"
    if "minimax" in model_name or "MiniMax" in model_name:
        return "minimax"
    if "qwen" in model_name or "tongyi" in model_name:
        return "qwen"
    if "gpt" in model_name:
        return "openai"
    if "dots" in model_name:
        return "dots"
    return "unknown"


def generate_markdown(leaderboard: dict) -> str:
    """从 leaderboard 数据生成人类可读的 Markdown 表格。"""
    lines = [
        "# Benchmark Leaderboard",
        "",
        f"> 自动生成于 {leaderboard['updated_at']} by benchkit",
        "",
        "---",
        "",
    ]

    for bench_id, bench_info in sorted(leaderboard["benchmarks"].items()):
        lines.append(f"## {bench_info.get('title', bench_id)}")
        lines.append(f"_{bench_info.get('description', '')}_")
        lines.append(f"[任务配置]({bench_info.get('_bench_yaml', '')}) | [提交结果](../benchmarks/{bench_id}/results)")
        lines.append("")

        models = bench_info.get("models", {})
        if not models:
            lines.append("*暂无数据*")
            lines.append("")
            continue

        metrics_list = bench_info.get("metrics", [])
        if bench_id == "polite":
            # 表格：模型 | Provider | N | 整体拒绝率 | min | max
            lines.append("| 模型 | Provider | N | 拒绝率(整体) | min | max |")
            lines.append("|---|---|---|---|---|---|")
            for model_name, mdata in sorted(models.items(), key=lambda x: -float(x[1]["metrics"]["refusal_rate"]["overall"] or 0)):
                rr = mdata["metrics"]["refusal_rate"]
                n = mdata.get("n_runs", 0)
                provider = mdata.get("provider", "")
                overall = f"{rr['overall']:.1%}" if rr.get("overall") is not None else "—"
                min_r = f"{rr['min']:.1%}" if rr.get("min") is not None else "—"
                max_r = f"{rr['max']:.1%}" if rr.get("max") is not None else "—"
                lines.append(f"| `{model_name}` | {provider} | {n} | {overall} | {min_r} | {max_r} |")
            lines.append("")

        elif bench_id == "sbti":
            lines.append("| 模型 | Provider | N | 选项一致率 | 类型熵 |")
            lines.append("|---|---|---|---|---|")
            for model_name, mdata in sorted(models.items(), key=lambda x: -float(x[1]["metrics"].get("option_consistency_rate") or 0)):
                n = mdata.get("n_runs", 0)
                provider = mdata.get("provider", "")
                ocr = mdata["metrics"].get("option_consistency_rate")
                te = mdata["metrics"].get("type_entropy")
                ocr_str = f"{ocr:.3f}" if ocr is not None else "—"
                te_str = f"{te:.3f}" if te is not None else "—"
                lines.append(f"| `{model_name}` | {provider} | {n} | {ocr_str} | {te_str} |")
            lines.append("")
        else:
            # 通用表格
            lines.append("| 模型 | Provider | N |")
            lines.append("|---|---|---|")
            for model_name, mdata in sorted(models.items()):
                n = mdata.get("n_runs", 0)
                provider = mdata.get("provider", "")
                lines.append(f"| `{model_name}` | {provider} | {n} |")
            lines.append("")

    return "\n".join(lines)


def write_output(leaderboard: dict, output_path: Path | None, dry_run: bool = False) -> None:
    """写 leaderboard.json 和 LEADERBOARD.md。"""
    repo_root = find_repo_root()
    json_path = output_path or (repo_root / "leaderboard.json")
    md_path = repo_root / "LEADERBOARD.md"

    md_content = generate_markdown(leaderboard)

    if dry_run:
        print("[dry-run] 写入内容预览：")
        print(f"  -> {json_path}")
        print(json.dumps(leaderboard, ensure_ascii=False, indent=2)[:500])
        print(f"  -> {md_path}")
        print(md_content[:500])
        return

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(leaderboard, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(md_content, encoding="utf-8")
    print(f"[leaderboard] 已写入:")
    print(f"  {json_path}")
    print(f"  {md_path}")


def main() -> int:
    ap = argparse.ArgumentParser(description="benchkit 跨 benchmark 排行榜聚合")
    ap.add_argument("--bench", help="只生成指定 benchmark（如 polite）")
    ap.add_argument("--output", type=Path, help="leaderboard.json 输出路径")
    ap.add_argument("--dry-run", action="store_true", help="只打印，不写文件")
    args = ap.parse_args()

    bench_filter = args.bench
    output_path = args.output

    leaderboard = build_leaderboard(bench_filter=bench_filter)

    if not leaderboard.get("benchmarks"):
        print("[leaderboard] 未找到任何 benchmark 数据", file=sys.stderr)
        return 1

    write_output(leaderboard, output_path, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())

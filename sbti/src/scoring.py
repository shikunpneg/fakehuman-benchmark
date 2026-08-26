# -*- coding: utf-8 -*-
"""SBTI 评分引擎 — 从上游 src/engine.js 移植的纯函数实现。

规则来源（data/SOURCE.md 锁定版本）：
1. 每题选项值 1/2/3（酒鬼门控题 drink_gate_q1 为 1-4）
2. 每维度恰好 2 道主题目，维度分 = 2 题值之和（范围 2-6）
3. 分级：<=3 -> L，==4 -> M，>=5 -> H
4. 数值化：L=1, M=2, H=3，得 15 维用户向量
5. 与 25 个标准类型 pattern 计算 Manhattan 距离
6. 排序：distance ASC -> exact DESC -> similarity DESC
7. 特殊覆盖：DRUNK（酒鬼彩蛋）> 正常匹配 > HHHH（兜底，similarity<60）
"""
from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_LEVEL_NUM = {"L": 1, "M": 2, "H": 3}


def load_data(data_dir: Path = DATA_DIR) -> dict:
    """加载锁定版题库、维度、类型与配置。"""
    def _read(name: str):
        with open(data_dir / name, encoding="utf-8") as f:
            return json.load(f)
    return {
        "questions": _read("questions.json"),
        "dimensions": _read("dimensions.json"),
        "types": _read("types.json"),
        "config": _read("config.json"),
    }


def calc_dimension_scores(answers: dict, questions: list) -> dict:
    """按维度求和：每维度 2 题分值相加 (范围 2-6)。answers: {qid: value}"""
    scores = {}
    for q in questions:
        if q["id"] in answers:
            scores[q["dim"]] = scores.get(q["dim"], 0) + answers[q["id"]]
    return scores


def scores_to_levels(scores: dict, thresholds: dict) -> dict:
    """原始分 -> L/M/H 等级。thresholds: {"L": [2,3], "M": [4,4], "H": [5,6]}"""
    levels = {}
    for dim, score in scores.items():
        if score <= thresholds["L"][1]:
            levels[dim] = "L"
        elif score >= thresholds["H"][0]:
            levels[dim] = "H"
        else:
            levels[dim] = "M"
    return levels


def parse_pattern(pattern: str) -> list[str]:
    """'HHH-HMH-MHH-HHH-MHM' -> ['H','H',...,'M']"""
    return pattern.replace("-", "")


def match_type(user_levels: dict, dim_order: list, pattern: str) -> dict:
    """用户 15 维等级 vs 类型 pattern 的 Manhattan 距离。"""
    type_levels = parse_pattern(pattern)
    distance, exact = 0, 0
    for i, dim in enumerate(dim_order):
        uv = _LEVEL_NUM.get(user_levels.get(dim), 2)
        tv = _LEVEL_NUM.get(type_levels[i], 2)
        diff = abs(uv - tv)
        distance += diff
        if diff == 0:
            exact += 1
    similarity = max(0, round((1 - distance / 30) * 100))
    return {"distance": distance, "exact": exact, "similarity": similarity}


def determine_result(user_levels: dict, dim_order: list, standard_types: list,
                     special_types: list, is_drunk: bool = False) -> dict:
    """匹配全部类型并排序，应用 DRUNK / HHHH 特殊覆盖。"""
    rankings = []
    for t in standard_types:
        m = match_type(user_levels, dim_order, t["pattern"])
        rankings.append({**t, **m})
    rankings.sort(key=lambda x: (x["distance"], -x["exact"], -x["similarity"]))

    best = rankings[0]
    drunk = next((t for t in special_types if t["code"] == "DRUNK"), None)
    hhhh = next((t for t in special_types if t["code"] == "HHHH"), None)

    if is_drunk and drunk:
        return {"primary": {**drunk, "similarity": best["similarity"], "exact": best["exact"]},
                "secondary": best, "rankings": rankings, "mode": "drunk"}
    if best["similarity"] < 60 and hhhh:
        return {"primary": {**hhhh, "similarity": best["similarity"], "exact": best["exact"]},
                "secondary": best, "rankings": rankings, "mode": "fallback"}
    return {"primary": best, "secondary": rankings[1] if len(rankings) > 1 else None,
            "rankings": rankings, "mode": "normal"}


def score_answers(answers: dict, data: dict, is_drunk: bool = False) -> dict:
    """完整评分：answers {qid: value} -> 维度分/等级/类型结果。"""
    cfg = data["config"]["scoring"]
    questions = data["questions"]["main"]
    dim_order = data["dimensions"]["order"]
    scores = calc_dimension_scores(answers, questions)
    levels = scores_to_levels(scores, cfg["levelThresholds"])
    result = determine_result(levels, dim_order,
                              data["types"]["standard"], data["types"]["special"],
                              is_drunk=is_drunk)
    return {"dim_scores": scores, "dim_levels": levels, "result": result}

# -*- coding: utf-8 -*-
"""benchkit.providers — OpenAI 兼容 Provider 注册表 + 计价表 + 客户端。

作为可复用的 benchmark 包，把"调哪家模型、花多少钱"从具体评测里抽离出来。
所有 API Key 从仓库根 .env 读取（见 .env.example），不进代码、不进 git。
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

import requests

# --------------------------------------------------------------------------
# 计价（每百万 tokens，单位：人民币元）。**全部为估算值**，用于 `benchkit.estimate`
# 的成本估算。实际以各厂商官方计费页为准，抓取价格随时间变动，见 docs/COST.md。
# 参考价格大致区间（2026）：
#   deepseek-chat   输入 2 元/M（缓存未命中），输出 8 元/M（峰谷定价波动大）
#   豆包 seed lite  输入 ~0.3 元/M，输出 ~0.6 元/M（火山方舟低价档）
#   Kimi / GLM / MiMo / MiniMax 为推理或中价格档
# --------------------------------------------------------------------------
# price_in / price_out：CNY 每 1e6 tokens。None -> 未知，估算时给出告警。
PRICING = {
    "deepseek": {
        "deepseek-chat": {"price_in": 2.0, "price_out": 8.0, "note": "峰谷定价，波动大"},
        "deepseek-v4-flash": {"price_in": 3.0, "price_out": 9.0, "note": "正式版低价档"},
        "deepseek-reasoner": {"price_in": 10.0, "price_out": 20.0, "note": "推理档"},
    },
    "qwen": {
        "qwen-turbo": {"price_in": 0.3, "price_out": 0.6, "note": "低价档"},
        "qwen-plus": {"price_in": 0.8, "price_out": 2.0, "note": "中档"},
        "qwen-max": {"price_in": 1.6, "price_out": 6.4, "note": "高档"},
    },
    "moonshot": {
        "moonshot-v1-8k": {"price_in": 6.0, "price_out": 6.0, "note": ""},
        "kimi-k2-0711-preview": {"price_in": 4.0, "price_out": 16.0, "note": "推理"},
    },
    "4api": {
        "kimi-k2-thinking": {"price_in": 3.2, "price_out": 12.8, "note": "0.8x 中转"},
        "glm-4.7": {"price_in": 0.8, "price_out": 2.0, "note": "0.8x 中转"},
        "glm-5": {"price_in": 2.4, "price_out": 9.6, "note": "0.8x 推理"},
        "glm-5.2": {"price_in": 8.0, "price_out": 28.0, "note": "0.8x 智谱正式版"},
    },
    "zhipu": {
        "glm-4-flash": {"price_in": 0.0, "price_out": 0.0, "note": "免费档"},
        "glm-4-air": {"price_in": 0.5, "price_out": 0.5, "note": ""},
        "glm-4-plus": {"price_in": 50.0, "price_out": 50.0, "note": "高档"},
    },
    "ark": {  # 火山方舟（豆包）
        "doubao-seed-2-0-mini-260428": {"price_in": 0.3, "price_out": 0.6, "note": "低价档（便宜）"},
        "doubao-seed-2-0-lite-260428": {"price_in": 0.2, "price_out": 0.4, "note": "最低价档（推荐）"},
        "doubao-seed-2-1-pro-260628": {"price_in": 4.0, "price_out": 12.0, "note": "高档"},
        "doubao-seed-evolving": {"price_in": 6.0, "price_out": 30.0, "note": "08.27升级"},
        "doubao-seed-2-1-turbo": {"price_in": 1.0, "price_out": 4.0, "note": "字节新版"},
        "doubao-1-5-pro-32k-250115": {"price_in": 0.8, "price_out": 2.0, "note": ""},
    },
    "minimax": {
        "MiniMax-Text-01": {"price_in": 1.0, "price_out": 1.0, "note": ""},
    },
    "openai": {
        "gpt-4o-mini": {"price_in": 1.1, "price_out": 4.4, "note": "USD 换算"},
        "gpt-4o": {"price_in": 22.0, "price_out": 88.0, "note": "USD 换算"},
    },
    "xiaomi": {
        "mimo-v2.5-pro": {"price_in": 4.0, "price_out": 16.0, "note": "推理档"},
    },
    "dots": {
        "dots3-note-prev": {"price_in": 0.0, "price_out": 0.0, "note": "免费档"},
    },
}

# --------------------------------------------------------------------------
# 注册表：OpenAI 兼容端点
# --------------------------------------------------------------------------
PROVIDERS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-v4-flash", "deepseek-reasoner"],
        "api_key_env": "DEEPSEEK_API_KEY",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen-plus", "qwen-max", "qwen-turbo"],
        "api_key_env": "QWEN_API_KEY",
    },
    "moonshot": {
        "base_url": "https://api.moonshot.cn/v1",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k", "kimi-k2-0711-preview"],
        "api_key_env": "MOONSHOT_API_KEY",
    },
    "4api": {
        "base_url": "https://4sapi.org/v1",
        "models": ["kimi-k2-thinking", "glm-4.7", "glm-5", "glm-5.2"],
        "api_key_env": "MOONSHOT_API_KEY",
    },
    "zhipu": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": ["glm-4-plus", "glm-4-flash", "glm-4-air"],
        "api_key_env": "ZHIPU_API_KEY",
    },
    "ark": {
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "models": [
            "doubao-seed-2-0-mini-260428",
            "doubao-seed-2-0-lite-260428",
            "doubao-seed-2-1-pro-260628",
            "doubao-seed-evolving",
            "doubao-seed-2-1-turbo",
            "doubao-1-5-pro-32k-250115",
        ],
        "api_key_env": ["ARK_API_KEY", "doubao_api_key"],
    },
    "minimax": {
        "base_url": "https://api.minimax.chat/v1",
        "models": ["MiniMax-Text-01"],
        "api_key_env": "MINIMAX_API_KEY",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini"],
        "api_key_env": "OPENAI_API_KEY",
    },
    "xiaomi": {
        "base_url": "https://api.xiaomimimo.com/v1",
        "models": ["mimo-v2.5-pro"],
        "api_key_env": "MIMO_API_KEY",
        "auth": "bearer",
        "default_max_tokens": 8192,
    },
    "dots": {
        "base_url": "https://note3-prev-api.askdianian.com/v1",
        "models": ["dots3-note-prev"],
        "api_key_env": "DOT_API_KEY",
        "auth": "bearer",
    },
}

MAX_RETRIES = 3
RETRY_BACKOFF = 2.0  # 秒

# 缺省输出 token 上限（按 provider 配置，推理模型需要更大）
DEFAULT_MAX_TOKENS = {
    "xiaomi": 8192,
    "4api": 4096,
    "deepseek": 2048,  # reasoning models need more tokens for visible content
}


class ProviderError(RuntimeError):
    """Provider 调用错误（网络/鉴权/限流）。"""


def find_repo_root() -> Path:
    """向上查找含 .env 的仓库根（benchkit 位于 <root>/benchkit/）。"""
    cur = Path(__file__).resolve().parent
    for _ in range(6):
        if (cur / ".env").exists():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return Path(__file__).resolve().parent.parent


def load_env() -> None:
    """从仓库根加载 .env（幂等）。"""
    if os.environ.get("__BENCHKIT_ENV_LOADED__"):
        return
    from dotenv import load_dotenv
    root = find_repo_root()
    env_path = root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    os.environ["__BENCHKIT_ENV_LOADED__"] = "1"


load_env()


def _key_for(provider: str) -> str:
    env = PROVIDERS[provider]["api_key_env"]
    candidates = env if isinstance(env, (list, tuple)) else [env]
    for name in candidates:
        key = os.environ.get(name)
        if key:
            return key
    raise ProviderError(f"{provider}: 缺少环境变量 {'/'.join(candidates)}（见 .env.example）")


def resolve_model(provider: str, model: Optional[str] = None) -> str:
    """未指定 model 时取该 provider 的第一个模型。"""
    if model:
        return model
    return PROVIDERS[provider]["models"][0]


def get_price(provider: str, model: str) -> Optional[dict]:
    """取计价条目；未知返回 None。"""
    return PRICING.get(provider, {}).get(model)


def chat_completion(provider: str, model: str, messages: list[dict],
                    temperature: float = 0.0, max_tokens: int | None = None,
                    timeout: float = 300.0) -> dict:
    """OpenAI 兼容 chat.completions 调用。返回 {text, usage, model}。"""
    cfg = PROVIDERS[provider]
    if not cfg.get("base_url"):
        raise ProviderError(f"{provider}: base_url 未配置")
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {_key_for(provider)}",
               "Content-Type": "application/json"}
    if max_tokens is None:
        max_tokens = DEFAULT_MAX_TOKENS.get(provider, 256)
    payload = {"model": resolve_model(provider, model), "messages": messages,
               "temperature": temperature, "max_tokens": max_tokens}

    last_err: Optional[Exception] = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                msg = data["choices"][0]["message"]
                text = msg.get("content", "")
                # DeepSeek reasoning models: visible content may be in "reasoning" field
                if not text and provider == "deepseek":
                    text = msg.get("reasoning", "")
                usage = data.get("usage", {})
                return {"text": text, "usage": usage, "model": data.get("model", model)}
            if resp.status_code in (401, 403):
                raise ProviderError(f"{provider}: 鉴权失败 HTTP {resp.status_code}: {resp.text[:200]}")
            if resp.status_code == 429:
                time.sleep(RETRY_BACKOFF * (2 ** attempt))
                continue
            last_err = ProviderError(f"{provider}: HTTP {resp.status_code}: {resp.text[:300]}")
        except requests.RequestException as e:
            last_err = ProviderError(f"{provider}: 网络错误: {e}")
        time.sleep(RETRY_BACKOFF * (2 ** attempt))
    raise ProviderError(f"{provider}: 重试 {MAX_RETRIES} 次后仍失败: {last_err}")

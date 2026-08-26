# -*- coding: utf-8 -*-
"""Provider 适配层：OpenAI 兼容协议客户端 + 模型注册表。

所有国内主流厂商（DeepSeek / 阿里百炼 / Moonshot / 智谱 / 火山方舟 / MiniMax）
均提供 OpenAI 兼容端点，故核心实现只依赖 requests，避免引入各家 SDK。

API Key 统一从环境变量读取（.env 见 .env.example），不进代码、不进 git。
"""
from __future__ import annotations
from pathlib import Path

import os
import time
from typing import Optional

import requests

# 注册表：OpenAI 兼容端点
PROVIDERS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-reasoner"],
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
        # 4sapi.com 中转（4sapi 国内域名解析到 154.17.20.134，海外 4sapi.com 被 Facebook 抢注）
        # 实测 MOONSHOT_API_KEY / ZHIPU_API_KEY / hy3_api_key 都绑在"国产全模型 (0.8x)"分组
        # 该分组下可用模型（实测 HTTP 200）：
        #   - kimi-k2-thinking  ✓
        #   - glm-4.7  ✓（智谱 GLM，非推理）
        #   - glm-5    ✓（智谱 GLM-5，推理模型，带 reasoning_content）
        "base_url": "https://4sapi.org/v1",
        "models": [
            "kimi-k2-thinking",   # Kimi k2 thinking（4sapi 官方名）
            "glm-4.7",            # GLM-4.7（实测可用）
            "glm-5",              # GLM-5 推理版（实测可用）
        ],
        "api_key_env": "MOONSHOT_API_KEY",  # 任一绑"国产全模型"分组的 key 均可
    },
    "zhipu": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": ["glm-4-plus", "glm-4-flash", "glm-4-air"],
        "api_key_env": "ZHIPU_API_KEY",
    },
    "ark": {  # 火山方舟（字节豆包），model 需填 endpoint ID
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "models": [
            # 模型 ID（按 4sapi / MCP 官方文档规范）：<产品版本>-<YYYYMMDD>
            # Doubao-Seed-2.0-mini 产品线 → doubao-seed-2-0-mini-260428
            "doubao-seed-2-0-mini-260428",
            "doubao-seed-2-0-lite-260428",
            "doubao-seed-2-1-pro-260628",
            "doubao-1-5-pro-32k-250115",
        ],
        "api_key_env": ["ARK_API_KEY", "doubao_api_key"],  # 任一非空即用（.env 实际填 doubao_api_key）
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
    "xiaomi": {  # 小米 MiMo：推理模型，reasoning 消耗大量 tokens，必须给足 max_tokens
        "base_url": "https://api.xiaomimimo.com/v1",
        "models": ["mimo-v2.5-pro"],
        "api_key_env": "MIMO_API_KEY",
        "auth": "bearer",
        "default_max_tokens": 8192,
    },
    "dots": {  # 小红书 dots studio（dots3-note-prev，免费档）
        "base_url": "https://note3-prev-api.askdianian.com/v1",
        "models": ["dots3-note-prev"],
        "api_key_env": "DOT_API_KEY",
        "auth": "bearer",
    },
}

MAX_RETRIES = 3
RETRY_BACKOFF = 2.0  # 秒，指数退避


class ProviderError(RuntimeError):
    """Provider 调用错误（网络/鉴权/限流）。"""


def _key_for(provider: str) -> str:
    env = PROVIDERS[provider]["api_key_env"]
    candidates = env if isinstance(env, (list, tuple)) else [env]
    for name in candidates:
        key = os.environ.get(name)
        if key:
            return key
    raise ProviderError(f"{provider}: 缺少环境变量 {'/'.join(candidates)}（见 .env.example）")


def load_env_smart() -> None:
    """从仓库根加载 .env（兼容 cwd 不确定场景）。已加载则跳过。"""
    if os.environ.get("__SBTI_ENV_LOADED__"):
        return
    from dotenv import load_dotenv
    # __file__ 在 src/providers.py；其 parent.parent.parent = 仓库根
    project_root = Path(__file__).resolve().parent.parent.parent
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    os.environ["__SBTI_ENV_LOADED__"] = "1"


# 模块加载时即尝试加载（兼容 collect / probe 各处）
load_env_smart()


def chat_completion(provider: str, model: str, messages: list[dict],
                    temperature: float = 0.0, max_tokens: int = 64,
                    timeout: float = 120.0) -> dict:
    """OpenAI 兼容 chat.completions 调用。返回 {text, usage, meta} 或抛 ProviderError。"""
    cfg = PROVIDERS[provider]
    if not cfg.get("base_url"):
        raise ProviderError(f"{provider}: base_url 未配置（TODOL）")
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {_key_for(provider)}",
               "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    last_err: Optional[Exception] = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                return {"text": text, "usage": usage,
                        "model": data.get("model", model)}
            if resp.status_code in (401, 403):
                raise ProviderError(f"{provider}: 鉴权失败 HTTP {resp.status_code}: {resp.text[:200]}")
            if resp.status_code == 429:
                # 限流：退避后重试
                time.sleep(RETRY_BACKOFF * (2 ** attempt))
                continue
            last_err = ProviderError(f"{provider}: HTTP {resp.status_code}: {resp.text[:300]}")
        except requests.RequestException as e:
            last_err = ProviderError(f"{provider}: 网络错误: {e}")
        time.sleep(RETRY_BACKOFF * (2 ** attempt))
    raise ProviderError(f"{provider}: 重试 {MAX_RETRIES} 次后仍失败: {last_err}")

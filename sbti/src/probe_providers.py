# -*- coding: utf-8 -*-
"""provider 端点连通性验证（kimi/glm/minimax 全量 + 逐题）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
import os
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

from providers import chat_completion, PROVIDERS, ProviderError

cases = [
    ("moonshot", "kimi-k2-0711-preview", 64),
    ("moonshot", "moonshot-v1-8k", 64),
    ("zhipu", "glm-4-flash", 64),
    ("zhipu", "glm-4-plus", 64),
    ("zhipu", "glm-4-air", 64),
    ("minimax", "MiniMax-Text-01", 64),
]
for prov, model, mt in cases:
    try:
        r = chat_completion(prov, model,
                            [{"role": "user", "content": "只回答一个字：好"}],
                            temperature=0.0, max_tokens=mt)
        print(f"OK {prov}/{model}: text={r['text']!r}")
    except ProviderError as e:
        print(f"ERR {prov}/{model}: {str(e)[:200]}")
    except Exception as e:
        print(f"BUG {prov}/{model}: {type(e).__name__}: {e}")
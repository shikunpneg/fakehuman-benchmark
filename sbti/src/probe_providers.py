# -*- coding: utf-8 -*-
"""4api.com 中转连通性测试（kimi-k2-thinking + GLM5）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
import os
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

from providers import chat_completion, ProviderError

cases = [
    ("4api", "kimi-k2-thinking"),
    ("4api", "GLM5"),
    ("4api", "moonshot-v1-8k"),
    ("4api", "claude-sonnet-4-5-20250929"),
]
for prov, model in cases:
    try:
        r = chat_completion(prov, model,
                            [{"role": "user", "content": "只回答一个字：好"}],
                            temperature=0.0, max_tokens=64)
        print(f"OK {prov}/{model}: text={r['text']!r}")
    except ProviderError as e:
        print(f"ERR {prov}/{model}: {str(e)[:200]}")
    except Exception as e:
        print(f"BUG {prov}/{model}: {type(e).__name__}: {e}")
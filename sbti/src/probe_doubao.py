from pathlib import Path
from dotenv import dotenv_values
import requests, json

env = dotenv_values(Path(__file__).resolve().parent.parent.parent / ".env")
key = env["doubao_api_key"]
print("key prefix:", key[:12])

# 火山方舟模型名探测
models = [
    # 模型 ID（<产品版本>-<日期>格式）
    "doubao-seed-2-0-mini-260428",   # Doubao-Seed-2.0-mini → mini
    "doubao-seed-2-0-lite-260428",   # Doubao-Seed-2.0-lite → lite
    "doubao-seed-2-1-pro-260628",    # Doubao-Seed-2.1-pro → pro
    "doubao-1-5-pro-32k-250115",     # 旧 1.5
]
url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
for m in models:
    p = json.dumps({"model": m,
                    "messages": [{"role": "user", "content": "只回答一个字：好"}],
                    "temperature": 0.0, "max_tokens": 8})
    try:
        r = requests.post(url, headers={"Authorization": f"Bearer {key}",
                                         "Content-Type": "application/json"},
                          data=p.encode("utf-8"), timeout=10)
        mark = "✓" if r.status_code == 200 else "·"
        print(f"{mark} {m}: HTTP {r.status_code}: {r.text[:80]}")
    except Exception as e:
        print(f"x {m}: ERR {type(e).__name__}: {str(e)[:60]}")
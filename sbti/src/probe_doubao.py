from pathlib import Path
from dotenv import dotenv_values
import requests, json

env = dotenv_values(Path(__file__).resolve().parent.parent.parent / ".env")
key = env["doubao_api_key"]
print("key prefix:", key[:12])

# 火山方舟模型名探测
models = [
    "doubao-1-5-pro-32k-250115",
    "doubao-pro-32k",
    "doubao-lite-32k",
    "ep-20240620",
    "doubao-seed-1.6",
    "doubao-1-5-pro-256k",
    "doubao-1-5-lite-32k",
    "doubao-seed-1.6-flash",
    "doubao-1-5-thinking-pro",
    "Doubao-1.5-pro-32k",
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
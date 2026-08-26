from pathlib import Path
from dotenv import dotenv_values
import socket
import requests

env = dotenv_values(Path(".").resolve().parent.parent / ".env")
key = env.get("MINIMAX_API_KEY", "")

candidates = ["https://4sapi.org/v1/chat/completions",
              "https://4sapi.cn/v1/chat/completions",
              "https://4sapi.net/v1/chat/completions",
              "https://4sapi.ai/v1/chat/completions",
              "https://4stoken.com/v1/chat/completions",
              "https://api.4sapi.org/v1/chat/completions",
              "https://api.4stoken.com/v1/chat/completions"]

print("DNS:")
for h in ["4sapi.org", "4sapi.cn", "4sapi.net", "4sapi.ai", "4stoken.com"]:
    try:
        ip = socket.gethostbyname(h)
        print(f"  {h}: {ip}")
    except Exception as e:
        print(f"  {h}: ERR {type(e).__name__}")

print("\nHTTP probe (HEAD or POST):")
for url in candidates:
    try:
        r = requests.post(url,
                          headers={"Authorization": f"Bearer {key}",
                                   "Content-Type": "application/json"},
                          json={"model": "claude-sonnet-4-5-20250929",
                                "messages": [{"role": "user", "content": "只回答一个字：好"}],
                                "temperature": 0.0, "max_tokens": 16},
                          timeout=15)
        print(f"  {url}: HTTP {r.status_code} {r.text[:120]}")
    except Exception as e:
        print(f"  {url}: ERR {type(e).__name__}: {str(e)[:80]}")
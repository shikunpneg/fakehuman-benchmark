# -*- coding: utf-8 -*-
"""探测 7：用 ICUBE_PROXY_HOST 探测 dots（Trae IDE 用的代理）。"""
import os
import requests
from pathlib import Path
from dotenv import dotenv_values

env = dotenv_values(Path(__file__).resolve().parent.parent.parent / ".env")
key = env["DOT_API_KEY"]
host = os.environ.get("ICUBE_PROXY_HOST", "127.0.0.1")
proxy_port = int(os.environ.get("ICUBE_PROXY_PORT", "7890"))
url = "https://note3-prev-api.askdianian.com/v1/chat/completions"

print(f"尝试 ICUBE 代理 {host}:{proxy_port}")
for proxy_url in [f"http://{host}:{proxy_port}", f"socks5h://{host}:{proxy_port}"]:
    try:
        r = requests.post(url,
                          headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                          json={"model": "dots3-note-prev",
                                "messages": [{"role": "user", "content": "只回答一个字：好"}],
                                "temperature": 0.0, "max_tokens": 32},
                          proxies={"http": proxy_url, "https": proxy_url}, timeout=30)
        print(f"  {proxy_url}: HTTP {r.status_code}: {r.text[:150]}")
        if r.status_code == 200:
            break
    except Exception as e:
        print(f"  {proxy_url}: ERR {type(e).__name__}: {e}")

# 兜底：尝试常见代理端口
print("\n扫描本机代理端口...")
import socket
for p in (7890, 7891, 7892, 1080, 10809, 8080, 8118, 10808, 6012):
    s = socket.socket()
    s.settimeout(0.5)
    try:
        s.connect(("127.0.0.1", p))
        print(f"  127.0.0.1:{p} OPEN")
    except Exception:
        pass
    finally:
        s.close()
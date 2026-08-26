from pathlib import Path
from dotenv import dotenv_values
import requests
import json

env = dotenv_values(Path(__file__).resolve().parent.parent.parent / ".env")
url = "https://4sapi.org/v1/chat/completions"

# 用 3 个 key 各试一组常见模型
keys = [
    ("MOONSHOT_API_KEY", env.get("MOONSHOT_API_KEY", "")),
    ("ZHIPU_API_KEY", env.get("ZHIPU_API_KEY", "")),
]
models = ["kimi-k2-thinking", "kimi-k2-0711-preview", "moonshot-v1-8k",
          "GLM5", "glm-4.6", "glm-4.5", "glm-4-flash", "glm-4-plus",
          "hunyuan-turbo", "hunyuan-pro"]

for name, k in keys:
    if not k:
        continue
    print(f"\n=== {name} prefix={k[:6]} ===")
    for m in models:
        p = json.dumps({"model": m,
                        "messages": [{"role": "user", "content": "只回答一个字：好"}],
                        "temperature": 0.0, "max_tokens": 8})
        try:
            r = requests.post(url,
                              headers={"Authorization": f"Bearer {k}",
                                       "Content-Type": "application/json"},
                              data=p.encode("utf-8"),
                              timeout=12)
            if r.status_code == 200:
                print(f"  ✓ {m}: HTTP 200 OK")
            else:
                err = (r.json().get("error", {}).get("message", "")
                       if "error" in r.text else r.text[:60])
                # 只打印 group 信息
                grp = ""
                if "group " in err:
                    g = err.split("group ")[1].split(" ")[0]
                    grp = f" [group={g}]"
                print(f"  · {m}: HTTP {r.status_code}{grp}: {err[:50]}")
        except Exception as e:
            print(f"  x {m}: ERR {type(e).__name__}: {str(e)[:60]}")
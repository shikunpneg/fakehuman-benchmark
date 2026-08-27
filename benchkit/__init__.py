# -*- coding: utf-8 -*-
"""benchkit — 可复用的抽象 benchmark 核心库。

把一个 benchmark 需要的公共件都抽出来，让每个 bench 只写"刺激数据 + 评分逻辑"。

  providers     OpenAI 兼容 provider 注册表 + 计价表 + 客户端
  estimate      成本估算器（`python -m benchkit.estimate --bench <name>`）
  refusal       言语暴力拒绝行为分类器（安全评测通用）
  runner        通用采集运行器（items × reps × providers）
"""
# 用 lazy import，避免 `python -m benchkit.estimate` 触发
# "found in sys.modules after import of package" 的 RuntimeWarning。
__all__ = ["providers", "estimate", "refusal", "runner"]
__version__ = "0.1"


def __getattr__(name):
    if name in __all__:
        import importlib
        return importlib.import_module(f"benchkit.{name}")
    raise AttributeError(f"module 'benchkit' has no attribute {name!r}")

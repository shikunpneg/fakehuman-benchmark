# -*- coding: utf-8 -*-
"""依赖检查。"""
for mod in ("matplotlib", "numpy", "pandas", "sklearn"):
    try:
        m = __import__(mod)
        print(f"{mod}: {m.__version__}")
    except ImportError:
        print(f"{mod}: NOT INSTALLED")
try:
    import umap
    print(f"umap-learn: {umap.__version__}")
except ImportError:
    print("umap-learn: NOT INSTALLED (will fall back to PCA)")
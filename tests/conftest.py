from __future__ import annotations

import importlib
import sys
from pathlib import Path

# Resolve repository root (one level above tests/)
REPO_ROOT = Path(__file__).resolve().parents[1]
root_str = str(REPO_ROOT)

# 1) Make sure repo root is FIRST on sys.path
if not sys.path or sys.path[0] != root_str:
    # Remove any existing occurrences and re-insert at front
    sys.path = [p for p in sys.path if p != root_str]
    sys.path.insert(0, root_str)

# 2) Force `analytics` to be the repo package, not tests/analytics
if "analytics" in sys.modules:
    del sys.modules["analytics"]

analytics = importlib.import_module("analytics")

# Optional sanity check (won't break tests; just helps debugging if needed)
# print("Pytest using analytics from:", analytics.__file__)

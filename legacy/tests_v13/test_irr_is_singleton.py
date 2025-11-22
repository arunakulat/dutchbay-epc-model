# tests/architecture/test_irr_is_singleton.py
import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]  # repo root
IRR = ROOT / "dutchbay_v13" / "finance" / "irr.py"

# right after the loop starts
SKIP_DIRS = {".venv", ".venv311", "venv", "site-packages", ".git", "__pycache__"}

for p in ROOT.rglob("*.py"):
    if any(part in SKIP_DIRS for part in p.parts):
        continue
    if str(p).endswith("test_irr_is_singleton.py"):
        continue
    if p == IRR:
        continue
    ...
    
def _grep(pattern: str, path: pathlib.Path) -> list[str]:
    rx = re.compile(pattern)
    return [ln for ln in path.read_text(encoding="utf-8").splitlines() if rx.search(ln)]

def test_only_irr_module_defines_irr_and_npv():
    hits = []
    for p in ROOT.rglob("*.py"):
        if "__pycache__" in p.parts or str(p).endswith("test_irr_is_singleton.py"):
            continue
        if p == IRR:
            continue
        text = p.read_text(encoding="utf-8")
        if re.search(r"\bdef\s+irr\s*\(", text) or re.search(r"\bdef\s+npv\s*\(", text):
            hits.append(str(p))
    assert not hits, f"Found IRR/NPV defs outside finance/irr.py: {hits}"

def test_adapters_does_not_import_numpy_financial():
    adapters = ROOT / "dutchbay_v13" / "adapters.py"
    bad = _grep(r"numpy_financial|npf", adapters)
    assert not bad, f"adapters.py must not import numpy_financial: {bad}"
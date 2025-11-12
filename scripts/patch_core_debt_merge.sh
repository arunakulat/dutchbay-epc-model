# scripts/patch_core_debt_merge.sh
#!/usr/bin/env bash
set -euo pipefail
F=dutchbay_v13/core.py
python - <<'PY'
from pathlib import Path, re
p = Path("dutchbay_v13/core.py")
s = p.read_text(encoding="utf-8")
# ensure incoming dicts with a 'debt' sub-dict don't explode constructors
s = re.sub(
    r"def _coerce_params\(d: Dict\[str, Any\]\) -> Params:\s*return Params\(\*\*\{",
    "def _coerce_params(d: Dict[str, Any]) -> Params:\n    d = dict(d or {})\n    debt = d.pop('debt', None)\n    base = {",
    s, count=1
)
if "create_default_debt_structure" not in s:
    # if core uses debt module, import and attach merged debt
    s = s.replace(
        "def build_financial_model(",
        "from .finance.debt import create_default_debt_structure\n\ndef build_financial_model("
    )
if "if debt is not None:" not in s:
    s = s.replace(
        "return Params(**base)",
        "    from .types import DebtParams\n"
        "    if debt is not None:\n"
        "        dp = create_default_debt_structure()\n"
        "        dp.update(debt)\n"
        "        base['debt_params'] = DebtParams(**dp) if 'DebtParams' in globals() else dp\n"
        "    return Params(**base)"
    )
Path("dutchbay_v13/core.py").write_text(s, encoding="utf-8")
print("✓ core.py patched for debt override passthrough")
PY
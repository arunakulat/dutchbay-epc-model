# scripts/fix_scenario_runner_syntax.sh
#!/usr/bin/env bash
set -euo pipefail

F="dutchbay_v13/scenario_runner.py"

# 1) Fix accidental escaped quotes: \"debt\" -> "debt"
LC_ALL=C sed -i '' -e 's/\\"debt\\"/"debt"/g' "$F"

# 2) If any other stray backslash-escaped quotes slipped in, normalize them too
LC_ALL=C sed -i '' -e 's/\\"/"/g' "$F"

# 3) Ensure validators accept a 'where=' kwarg (idempotent)
python - <<'PY'
from pathlib import Path, re
p = Path("dutchbay_v13/scenario_runner.py")
s = p.read_text(encoding="utf-8")

def ensure_where(defname: str) -> str:
    if defname not in s:
        return s
    head, sep, tail = s.partition(defname)
    sig, sep2, rest = tail.partition("):")
    if "where=" not in sig:
        sig = sig + ', where="scenario"'
        return head + defname + sig + "):" + rest
    return s

s = ensure_where("def _validate_params_dict(")
s = ensure_where("def _validate_debt_dict(")

p.write_text(s, encoding="utf-8")
print("✓ ensured validator signatures include where=")
PY

# 4) Style, quietly
ruff check . --fix >/dev/null 2>&1 || true
black . >/dev/null 2>&1 || true

echo "✓ fixed $F"
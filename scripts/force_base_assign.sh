#!/usr/bin/env bash
set -euo pipefail

PYFILE="scripts/force_base_assign.py"
TARGET="dutchbay_v13/scenario_runner.py"

cat > "$PYFILE" <<'PY'
import re, sys, pathlib
p = pathlib.Path("dutchbay_v13/scenario_runner.py")
s = p.read_text(encoding="utf-8")

changed = False

# 1) Insert base after "name = p.stem" inside the for-loop
pat = re.compile(r'(for\s+p\s+in[^\n]*\n(?:\s+.*\n)*?\s*name\s*=\s*p\.stem\s*\n)', re.M)
def repl(m):
    return m.group(1) + "        base = f\"scenario_{name or '000'}\"\n"
s2, n = pat.subn(repl, s)
if n > 0:
    s = s2
    changed = True

# 2) If we didn't find name=p.stem, insert name/base at top of loop
if n == 0:
    pat_loop = re.compile(r'(for\s+p\s+in[^\n]*\n)', re.M)
    s2, n2 = pat_loop.subn(r"\1        name = getattr(p, 'stem', '000')\n        base = f\"scenario_{name}\"\n", s, count=1)
    if n2 > 0:
        s = s2
        changed = True

# 3) Normalize literal artifact prefixes to use {base}
s_norm = s
s_norm = s_norm.replace('f\"scenario_{name}_annual_', 'f\"{base}_annual_')
s_norm = s_norm.replace('f\"scenario_{name}_results_', 'f\"{base}_results_')
s_norm = re.sub(r'([\'\"])scenario_000_annual_', r'\1{base}_annual_', s_norm)
s_norm = re.sub(r'([\'\"])scenario_000_results_', r'\1{base}_results_', s_norm)

if s_norm != s:
    s = s_norm
    changed = True

if changed:
    p.write_text(s, encoding="utf-8")
    print("✓ Patched", p)
else:
    print("↷ No changes needed", p)
PY

python3 "$PYFILE"

# Show where base is now
grep -n "base = f\"scenario_" -n "$TARGET" || true

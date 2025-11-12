#!/usr/bin/env bash
set -euo pipefail

F="dutchbay_v13/cli.py"
python - <<'PY'
from pathlib import Path
import re

p = Path("dutchbay_v13/cli.py")
s = p.read_text(encoding="utf-8")

# Try to upgrade an existing --outputs-dir arg to accept --outdir as an alias
pat = r'p\.add_argument\(\s*"--outputs-dir"([^)]*)\)'
m = re.search(pat, s)
if m and "--outdir" not in m.group(0):
    s = re.sub(
        pat,
        r'p.add_argument("--outputs-dir","--outdir", dest="outputs_dir"\1)',
        s,
        count=1,
    )
elif "--outdir" not in s:
    # Fallback replacement if the original add_argument line is slightly different
    s = s.replace(
        'p.add_argument("--outputs-dir", default=".")',
        'p.add_argument("--outputs-dir","--outdir", dest="outputs_dir", default=".")',
    )

p.write_text(s, encoding="utf-8")
print("✓ cli.py updated to accept --outdir")
PY

# Optional tidy/format
ruff check . --fix >/dev/null 2>&1 || true
black . >/dev/null 2>&1 || true

# Quick smokes (should not error)
python -m dutchbay_v13 baseline --charts --outdir _out
python -m dutchbay_v13 scenarios --format both --save-annual --outdir _out --scenarios inputs || true

echo "Done."
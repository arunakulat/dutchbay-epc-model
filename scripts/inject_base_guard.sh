#!/usr/bin/env bash
set -euo pipefail

TARGET="dutchbay_v13/scenario_runner.py"

python3 - <<'PY'
import re, pathlib

p = pathlib.Path("dutchbay_v13/scenario_runner.py")
s = p.read_text(encoding="utf-8").splitlines(True)

in_run_dir = False
injected = False

for i, line in enumerate(s):
    # enter run_dir body
    if line.lstrip().startswith("def run_dir("):
        in_run_dir = True
        continue
    # exit function on new def/class
    if in_run_dir and line.lstrip().startswith(("def ", "class ")):
        in_run_dir = False

    if in_run_dir and ("{base}_annual_" in line or "{base}_results_" in line):
        indent = re.match(r"^(\s*)", line).group(1)
        guard = (
            f"{indent}# ensure base exists for output naming\n"
            f"{indent}try:\n"
            f"{indent}    base\n"
            f"{indent}except NameError:\n"
            f"{indent}    name = locals().get('name', '000')\n"
            f"{indent}    base = f\"scenario_{'{'}name or '000'{'}'}\"\n"
        )
        s.insert(i, guard)
        injected = True
        break

if injected:
    p.write_text("".join(s), encoding="utf-8")
    print("✓ Injected base-guard before first {base}_* use in run_dir()")
else:
    print("↷ No injection done (didn't find {base}_* in run_dir())")
PY

# Show the vicinity for sanity
nl -ba "$TARGET" | sed -n '1,240p' | grep -n "{base}_" || true

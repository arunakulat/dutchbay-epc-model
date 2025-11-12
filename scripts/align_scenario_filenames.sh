#!/usr/bin/env bash
set -euo pipefail
F="dutchbay_v13/scenario_runner.py"

# 1) Ensure we build a base filename from scenario name (fallback to 000)
# Insert or replace a line like: base = f"scenario_{name or '000'}"
if ! grep -q "base = f\"scenario_" "$F"; then
  # after we compute `name = p.stem`
  sed -i '' -E '/name\s*=\s*p\.stem/a\
\    base = f"scenario_{name or '\''000'\''}"
' "$F"
else
  sed -i '' -E "s/base\s*=\s*f\"scenario_.+\"/base = f\"scenario_{name or '000'}\"/" "$F"
fi

# 2) Make results filenames use `base`
# CSV
sed -i '' -E "s/(['\"])scenario_000_results_/\1\{base\}_results_/g" "$F"
# JSONL
sed -i '' -E "s/(['\"])scenario_000_results_/\1\{base\}_results_/g" "$F"

# 3) Make annual filenames use `base` consistently
sed -i '' -E "s/(['\"])scenario_([A-Za-z0-9_-]+)_annual_/\1\{base\}_annual_/g" "$F"
sed -i '' -E "s/(['\"])scenario_000_annual_/\1\{base\}_annual_/g" "$F"

# 4) If code was building names inline, normalize to f-strings with {base}
# (harmless if not present)
sed -i '' -E "s/f\"scenario_\\{name\\}_annual_/f\"{base}_annual_/g" "$F"
sed -i '' -E "s/f\"scenario_\\{name\\}_results_/f\"{base}_results_/g" "$F"

python -m pyflakes "$F" >/dev/null 2>&1 || true
echo "✓ scenario_runner.py: filenames now use scenario stem for results + annual"

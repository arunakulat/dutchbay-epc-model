# scripts/patch_validate_overrides_only.sh
#!/usr/bin/env bash
set -euo pipefail

F="dutchbay_v13/scenario_runner.py"

python - <<'PY'
from pathlib import Path, re
p = Path("dutchbay_v13/scenario_runner.py")
s = p.read_text(encoding="utf-8")

# Ensure validators accept 'where=' (idempotent)
s = re.sub(r"def _validate_params_dict\(([^)]*)\):",
           r"def _validate_params_dict(\1, where=\"scenario\"):",
           s, count=1) if "def _validate_params_dict(" in s and "where=" not in s else s
s = re.sub(r"def _validate_debt_dict\(([^)]*)\):",
           r"def _validate_debt_dict(\1, where=\"scenario\"):",
           s, count=1) if "def _validate_debt_dict(" in s and "where=" not in s else s

# In run_scenario(...), switch validation inputs from cfg → overrides
s = re.sub(
    r"_validate_params_dict\(\{k: v for k, v in cfg\.items\(\) if k != \"debt\"\}, where=name\)",
    r"_validate_params_dict({k: v for k, v in overrides.items() if k != \"debt\"}, where=name)",
    s, count=1
)
s = re.sub(
    r"_validate_debt_dict\(cfg\.get\(\"debt\", \{\}\), where=name\)",
    r"_validate_debt_dict(overrides.get(\"debt\", {}), where=name)",
    s, count=1
)

p.write_text(s, encoding="utf-8")
print("✓ scenario_runner.py: validators now use overrides only")
PY

ruff check . --fix >/dev/null 2>&1 || true
black . >/dev/null 2>&1 || true
echo "Done."


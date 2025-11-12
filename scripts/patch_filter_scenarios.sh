# scripts/patch_filter_scenarios.sh
#!/usr/bin/env bash
set -euo pipefail

F="dutchbay_v13/scenario_runner.py"

python - <<'PY'
from pathlib import Path
import re, textwrap

p = Path("dutchbay_v13/scenario_runner.py")
s = p.read_text(encoding="utf-8")

# Add a helper to detect override-style YAMLs (idempotent)
if "_is_override_yaml(" not in s:
    helper = textwrap.dedent("""
    def _is_override_yaml(path: Path) -> bool:
        \"\"\"Return True if YAML looks like a scenario override (subset of allowed keys).\"\"\"
        try:
            import yaml
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return False
            allowed = set(SCHEMA.keys()) | {"debt"}
            return set(data.keys()).issubset(allowed)
        except Exception:
            return False
    """)
    # put helper after imports
    s = re.sub(r"(\nfrom pathlib import Path[^\n]*\n)",
               r"\1" + helper + "\n",
               s, count=1)

# In run_dir, filter the YAML list:
#  - skip obvious base/matrix files
#  - keep only files passing _is_override_yaml
s = re.sub(
    r"(yamls\s*=\s*sorted\([^\)]*glob\([\"']\*\.y\*ml[\"']\)\))",
    r"\1\n    # filter: skip base config & matrix; only override-like files\n"
    r"    yamls = [p for p in yamls "
    r"if p.name not in ('full_model_variables_updated.yaml','scenario_matrix.yaml') and _is_override_yaml(p)]",
    s, count=1
)

p.write_text(s, encoding="utf-8")
print("✓ scenario_runner.py: run_dir now filters out base/matrix YAMLs and non-override files")
PY

ruff check . --fix >/dev/null 2>&1 || true
black . >/dev/null 2>&1 || true
echo "Done."
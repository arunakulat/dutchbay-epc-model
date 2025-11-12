#!/usr/bin/env bash
set -Eeuo pipefail
echo "→ Adding reporting smokes…"
bash scripts/add_reporting_smokes.sh
echo "→ Adding core/config smokes…"
bash scripts/add_core_config_smokes.sh
echo "→ Running reporting tests…"
bash scripts/test_reporting_modules.sh
echo "→ Running core/config tests…"
bash scripts/test_core_modules.sh
echo "✓ Next modules suite complete."


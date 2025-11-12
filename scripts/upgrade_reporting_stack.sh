#!/usr/bin/env bash
set -Eeuo pipefail
bash scripts/add_minimal_report_api.sh
# Comment out next line if you want to keep xfails
bash scripts/harden_reporting_smokes.sh
bash scripts/run_reporting_hardened.sh
echo "✓ Reporting stack upgraded."


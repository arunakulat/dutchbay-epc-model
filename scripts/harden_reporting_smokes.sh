#!/usr/bin/env bash
set -Eeuo pipefail
sed -i '' 's/pytest\.xfail("report API not exported yet")/assert fn is not None/' tests/reporting/test_report_smoke.py
sed -i '' 's/pytest\.xfail("report_pdf API not exported yet")/assert fn is not None/' tests/reporting/test_report_pdf_smoke.py
sed -i '' 's/pytest\.xfail("report callable present but not yet stable")/raise/' tests/reporting/test_report_smoke.py
sed -i '' 's/pytest\.xfail("report_pdf callable present but not yet stable")/raise/' tests/reporting/test_report_pdf_smoke.py
sed -i '' 's/pytest\.xfail("optional PDF deps not installed yet")/raise/' tests/reporting/test_report_pdf_smoke.py
echo "✓ Reporting smokes hardened."


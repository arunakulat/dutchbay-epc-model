#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/_out_reporting_cli"
mkdir -p "$OUT"

python - <<'PY'
from pathlib import Path
from importlib import import_module

out = Path("_out_reporting_cli")
out.mkdir(exist_ok=True)

rp = import_module("dutchbay_v13.report")
pdf = import_module("dutchbay_v13.report_pdf")

m1 = rp.generate_report(meta={"title":"Report CLI Smoke"},
                        output_path=out/"stub-report.pdf")
m2 = pdf.render_pdf(meta={"title":"Report PDF Smoke"},
                    output_path=out/"stub-report2.pdf")

assert Path(m1["output_path"]).exists()
assert Path(m2["output_path"]).exists()
print("✓ reporting CLI smoke ok:", m1["output_path"], "&&", m2["output_path"])
PY


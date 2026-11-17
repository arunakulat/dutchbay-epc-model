"""SANDBOX (draft, screening): one command for the combined lender report on any scenario (#1752).

Runs the canonical finance pipeline on a scenario YAML, the supplemental tornado / Morris / PAWN
sensitivities (``report_orchestration.compute_report_sensitivity``), and the capital-risk Monte
Carlo through the lender guards (``capital_risk_emit``: toy fallback forced off, at least
``LENDER_GRADE_MIN_TRIALS`` trials). The assembled ``ReportContext`` is rendered to HTML (and to
PDF when the ``[report]`` extra is installed). The HTML carries a DRAFT banner and a
"sections not run" list naming each section left out and why.

This is the lender renderer, NOT a ``DBPL-01`` document. No second orchestrator and no second
payload type: it reuses ``report_orchestration`` and ``ReportContext``.

Usage::

    PYTHONPATH=$PWD python scripts/run_lender_report_v14.py scenarios/<name>.yaml out_dir [n_trials]
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Tuple

from analytics.executive_workbook import EXECUTIVE_WORKBOOK_F5_CAVEAT
from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.scenario_loader import load_scenario_config
from app.api.responses import CaseResult
from app.reports.capital_risk_emit import (
    DEFAULT_CAPITAL_RISK_N_TRIALS,
    LENDER_GRADE_MIN_TRIALS,
    build_capital_risk_report_for_scenario,
)
from app.reports.renderer import render_report_html, render_report_pdf
from app.reports.report_model import build_report_context
from app.reports.report_orchestration import compute_report_sensitivity

DRAFT_BANNER = (
    '<div style="border:3px solid #b00;padding:10px;margin:10px;font:bold 14px sans-serif;'
    'color:#b00">DRAFT / SCREENING GRADE. Not lender-grade, not for release. Placeholder '
    "financing and cost inputs; screening yield and wake; no measured wind data; no P90 claim. "
    "No quarterly CFADS or intra-year DSCR figure supports a lender representation (F-5).</div>"
)


def _not_run(sections: List[Tuple[str, str]]) -> str:
    if not sections:
        return ""
    items = "".join(f"<li><b>{n}</b>: {why}</li>" for n, why in sections)
    return (
        '<div style="margin:10px;font:13px sans-serif"><h2>Sections not run</h2>'
        f"<ul>{items}</ul></div>"
    )


def build(scenario: str, out_dir: str, n_trials: int) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    not_run: List[Tuple[str, str]] = []
    cfg = dict(load_scenario_config(scenario))
    result = run_v14_pipeline(scenario)
    case = CaseResult.from_pipeline_result(result, scenario_variant=Path(scenario).stem)

    bundle = compute_report_sensitivity(cfg)
    for name, val in (
        ("Tornado", bundle.tornado),
        ("Morris global sensitivity", bundle.morris),
        ("PAWN global sensitivity", bundle.pawn),
    ):
        if val is None:
            not_run.append((name, "degraded: the sensitivity method returned no result"))

    capital_risk = None
    if (cfg.get("monte_carlo") or {}).get("parameters"):
        capital_risk = build_capital_risk_report_for_scenario(
            scenario, out, n_trials=n_trials, min_trials=LENDER_GRADE_MIN_TRIALS
        )
    else:
        not_run.append(("Capital-risk Monte Carlo", "the scenario declares no monte_carlo.parameters"))

    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    ctx = build_report_context(
        case,
        generated_at=stamp,
        scenario_config=cfg,
        debt_result=result.get("debt_result"),
        annual_rows=result.get("annual_rows"),
        tornado=bundle.tornado,
        global_sa=bundle.morris,
        global_sa_pawn=bundle.pawn,
        capital_risk=capital_risk,
        run_result=result,
    )
    ctx = ctx.model_copy(update={"f5_notice": EXECUTIVE_WORKBOOK_F5_CAVEAT})
    html = render_report_html(ctx)
    html = html.replace("<body>", "<body>" + DRAFT_BANNER, 1) if "<body>" in html else DRAFT_BANNER + html
    nr = _not_run(not_run)
    html = html.replace("</body>", nr + "</body>", 1) if "</body>" in html else html + nr
    html_path = out / "lender_report_draft.html"
    html_path.write_text(html, encoding="utf-8")
    written = {"html": str(html_path), "not_run": [n for n, _ in not_run]}
    try:
        pdf = render_report_pdf(ctx.model_copy())
        # Same draft banner on the PDF: render the bannered HTML through WeasyPrint.
        from weasyprint import HTML

        (out / "lender_report_draft.pdf").write_bytes(HTML(string=html).write_pdf())
        del pdf
        written["pdf"] = str(out / "lender_report_draft.pdf")
    except Exception as exc:  # noqa: BLE001 - PDF is best-effort in a draft
        written["pdf_error"] = f"{type(exc).__name__}: {exc}"
    return written


if __name__ == "__main__":
    scen, outd = sys.argv[1], sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_CAPITAL_RISK_N_TRIALS
    print(build(scen, outd, n))

"""Command-line route for the combined lender report, as HTML and a DBPL PDF (#1752).

``POST /v1/cases/report.pdf`` builds the combined lender report through
:mod:`app.reports.report_orchestration`. Nothing on the ``run_full_pipeline_v14.py`` path reached
it: the capital-risk emitter renders the core sections plus the Monte Carlo block, and leaves the
sensitivity sections out. This module gives the batch CLI the same report:

* the finance result the CLI already computed becomes a
  :class:`~app.reports.report_orchestration.ReportCaseData` (no second finance run);
* the tornado, Morris and PAWN sections are computed by
  :func:`~app.reports.report_orchestration.compute_report_sensitivity` under the production
  profile, exactly as the API route computes them;
* the capital-risk (Monte Carlo) section is the capital-risk emitter's report when that emitter
  ran in the same run, or else a run through
  :func:`~app.reports.capital_risk_emit.build_capital_risk_report_for_scenario`, so the lender
  guards apply either way: the toy fallback is forced off and the run has at least
  :data:`~app.reports.capital_risk_emit.LENDER_GRADE_MIN_TRIALS` trials;
* every section left out is listed on the report with its reason (``sections_not_run``);
* the HTML is written, then printed to PDF through
  :func:`app.reports.dbpl.print_core.render_dbpl_pdf` with the house stylesheet (``DBPL-01``).

The report carries the F-5 non-reliance notice on its cover, as the capital-risk report does.

GWTF:
    - FRAMEWORK-03: one orchestrator and one payload type. This module adds neither: it feeds
      ``report_orchestration`` and renders ``ReportContext``.
    - FRAMEWORK-02: a section that cannot run is listed with its reason; nothing is filled in.
      A missing DBPL print stack is raised when the report was switched on by name.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional

from analytics.capital_risk_layer_v14 import CapitalRiskReport
from analytics.executive_workbook import EXECUTIVE_WORKBOOK_F5_CAVEAT
from analytics.scenario_loader import load_scenario_config
from app.reports.renderer import render_report_html
from app.reports.report_model import ReportContext, SectionNotRun
from app.reports.report_orchestration import (
    PRODUCTION_REPORT_SENSITIVITY_PROFILE,
    ReportSensitivityBundle,
    ReportSensitivityProfile,
    build_report_context_from_case,
    compute_report_sensitivity,
    global_sa_driver_count,
    report_case_from_pipeline_result,
)

__all__ = [
    "LENDER_REPORT_FILES_DIR",
    "LENDER_REPORT_HTML_NAME",
    "LENDER_REPORT_PDF_NAME",
    "LenderReportOutput",
    "emit_lender_report_from_pipeline",
    "sections_not_run",
    "to_dbpl_print_html",
]

#: Default file names under the run's export directory.
LENDER_REPORT_HTML_NAME = "lender_report.html"
LENDER_REPORT_PDF_NAME = "lender_report.pdf"
#: Directory beside the HTML for the report's own Monte Carlo chart, used only when the
#: capital-risk emitter did not run in the same run.
LENDER_REPORT_FILES_DIR = "lender_report_files"

#: Section titles as the report prints them, for the "sections not run" list.
SECTION_TORNADO = "Sensitivity tornado"
SECTION_MORRIS = "Global sensitivity: Morris screening"
SECTION_PAWN = "Global sensitivity: PAWN"
SECTION_CAPITAL_RISK = "Capital risk: Monte Carlo distribution"

NO_MONTE_CARLO_PARAMETERS = "the scenario declares no monte_carlo.parameters to sample"

SensitivityComputer = Callable[..., ReportSensitivityBundle]
CapitalRiskBuilder = Callable[..., CapitalRiskReport]


@dataclass(frozen=True)
class LenderReportOutput:
    """What the lender report emitter wrote, and what it left out."""

    html_path: Path
    pdf_path: Optional[Path]
    pdf_not_written: Optional[str]
    sections_not_run: tuple[SectionNotRun, ...]
    pdf_provenance: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> Dict[str, Any]:
        """Return a JSON-ready record for the run's ``summary.json``."""
        out: Dict[str, Any] = {
            "html_path": str(self.html_path),
            "pdf_path": None if self.pdf_path is None else str(self.pdf_path),
            "sections_not_run": [
                {"section": s.section, "reason": s.reason}
                for s in self.sections_not_run
            ],
        }
        if self.pdf_not_written is not None:
            out["pdf_not_written"] = self.pdf_not_written
        if self.pdf_provenance:
            out["pdf_provenance"] = list(self.pdf_provenance)
        return out


def _outcome(bundle: ReportSensitivityBundle, method: str) -> str:
    for entry in bundle.methods:
        if entry.method == method:
            return entry.outcome
    return "degraded"


def sections_not_run(
    sensitivity: ReportSensitivityBundle,
    scenario_config: Mapping[str, Any],
    *,
    capital_risk_not_run: Optional[str],
) -> List[SectionNotRun]:
    """List the sections the report will not render, each with its reason.

    The template renders the tornado only with rows, and each global-SA section only with
    drivers, so a section is listed exactly when the template would leave it out.

    Args:
        sensitivity: The computed sensitivity bundle.
        scenario_config: The scenario the sensitivities ran on.
        capital_risk_not_run: Why the capital-risk section has no report, or ``None`` when it has
            one.

    Returns:
        The left-out sections, in report order.
    """
    out: List[SectionNotRun] = []
    tornado = sensitivity.tornado
    if tornado is None or not tornado.rows:
        out.append(
            SectionNotRun(
                section=SECTION_TORNADO,
                reason=(
                    "not computed: the one-at-a-time sweep returned no usable driver rows "
                    f"(outcome: {_outcome(sensitivity, 'tornado')})"
                ),
            )
        )
    no_drivers = global_sa_driver_count(scenario_config) == 0
    for section, method, block in (
        (SECTION_MORRIS, "morris", sensitivity.morris),
        (SECTION_PAWN, "pawn", sensitivity.pawn),
    ):
        if block is not None and block.drivers:
            continue
        reason = (
            f"not computed: {NO_MONTE_CARLO_PARAMETERS} with finite bounds"
            if no_drivers
            else (
                "not computed: the screening returned no usable drivers "
                f"(outcome: {_outcome(sensitivity, method)})"
            )
        )
        out.append(SectionNotRun(section=section, reason=reason))
    if capital_risk_not_run is not None:
        out.append(
            SectionNotRun(section=SECTION_CAPITAL_RISK, reason=capital_risk_not_run)
        )
    return out


# Tags the DBPL house stylesheet styles only through its own classes.
_DBPL_TAG_CLASSES = {
    "h1": "dbpl-title",
    "h2": "dbpl-section",
    "h3": "dbpl-subsection",
    "table": "dbpl",
}
_STYLE_BLOCK = re.compile(r"<style\b[^>]*>.*?</style>\s*", re.DOTALL | re.IGNORECASE)
_OPEN_TAG = re.compile(r"<(h1|h2|h3|table)(\s[^>]*)?>", re.IGNORECASE)
_CLASS_ATTR = re.compile(r"""\bclass\s*=\s*"([^"]*)\"""", re.IGNORECASE)
_BODY_OPEN = re.compile(r"<body\b[^>]*>", re.IGNORECASE)


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def to_dbpl_print_html(html: str, *, banner: str, docline: str) -> str:
    """Re-dress the lender report's HTML for the DBPL print core.

    The report template carries its own screen stylesheet with literal colours and sizes.
    ``DBPL-01`` forbids a surface that forks the house style, so for print the template's
    ``<style>`` block is removed, the house classes are added to the headings and tables, and
    the DBPL running banner and doc-line are inserted, so every page carries them. The text,
    the figures and the section order are unchanged.

    Args:
        html: The rendered lender report.
        banner: The running banner (classification) printed on every page.
        docline: The document identity line printed on every page.

    Returns:
        HTML ready for :func:`app.reports.dbpl.print_core.render_dbpl_pdf`.

    Raises:
        ValueError: the HTML has no ``<body>`` element.
    """

    def add_class(match: "re.Match[str]") -> str:
        tag, attrs = match.group(1), match.group(2) or ""
        house = _DBPL_TAG_CLASSES[tag.lower()]
        existing = _CLASS_ATTR.search(attrs)
        if existing is None:
            return f'<{tag} class="{house}"{attrs}>'
        classes = " ".join(c for c in (house, existing.group(1).strip()) if c)
        merged = f'class="{classes}"'
        return f"<{tag}{attrs[: existing.start()]}{merged}{attrs[existing.end() :]}>"

    printed = _STYLE_BLOCK.sub("", html, count=1)
    printed = _OPEN_TAG.sub(add_class, printed)
    body = _BODY_OPEN.search(printed)
    if body is None:
        raise ValueError("the lender report HTML has no <body> element")
    running = (
        f'\n<div class="dbpl-banner">{_escape(banner)}</div>'
        f'\n<div class="dbpl-docline">{_escape(docline)}</div>\n'
    )
    return printed[: body.end()] + running + printed[body.end() :]


def _render_pdf(context: ReportContext, html: str, pdf_path: Path) -> tuple[str, ...]:
    from app.reports.dbpl import render_dbpl_pdf

    printed = to_dbpl_print_html(
        html,
        banner=context.meta.confidentiality,
        docline=(
            f"{context.meta.title} | {context.scenario_variant} | "
            f"report {context.meta.version} | {context.generated_at}"
        ),
    )
    result = render_dbpl_pdf(printed)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(result.pdf)
    return result.provenance_lines()


def emit_lender_report_from_pipeline(
    result: Mapping[str, Any],
    scenario_config_path: str | Path,
    output_html_path: str | Path,
    *,
    output_pdf_path: Optional[str | Path] = None,
    capital_risk: Optional[CapitalRiskReport] = None,
    capital_risk_not_run: Optional[str] = None,
    n_trials: Optional[int] = None,
    seed: Optional[int] = None,
    npv_metric: str = "equity_npv",
    require_pdf: bool = True,
    scenario_variant: Optional[str] = None,
    generated_at: Optional[str] = None,
    profile: ReportSensitivityProfile = PRODUCTION_REPORT_SENSITIVITY_PROFILE,
    sensitivity_computer: SensitivityComputer = compute_report_sensitivity,
    capital_risk_builder: Optional[CapitalRiskBuilder] = None,
) -> LenderReportOutput:
    """Write the combined lender report for a finance run, as HTML and a DBPL PDF (#1752).

    Args:
        result: The finance result ``run_v14_pipeline`` returned for this scenario.
        scenario_config_path: The effective scenario the run used.
        output_html_path: Where to write the HTML (parents created).
        output_pdf_path: Where to write the PDF; defaults to the HTML path with ``.pdf``.
        capital_risk: The capital-risk report the same run already built, if any. It is used
            as is, so the Monte Carlo runs once per run.
        capital_risk_not_run: Why the capital-risk section is left out (for example, that
            emitter failed in this run). Takes precedence over running the Monte Carlo here.
        n_trials: Trial count when this emitter runs the Monte Carlo itself; defaults to the
            capital-risk emitter's default. The lender floor applies and cannot be lowered here.
        seed: Monte Carlo seed; defaults to the scenario's ``monte_carlo.seed``.
        npv_metric: NPV bucket for the distribution chart.
        require_pdf: Raise when the DBPL print stack is incomplete. When false the HTML is still
            written and the reason the PDF was not is recorded.
        scenario_variant: Report label; defaults to the scenario file stem.
        generated_at: Timestamp stamped on the report; defaults to now (UTC).
        profile: Sensitivity profile; the CLI uses the production profile, as the API does.
        sensitivity_computer: Seam for tests; production uses
            :func:`~app.reports.report_orchestration.compute_report_sensitivity`.
        capital_risk_builder: Seam for tests; production uses
            :func:`~app.reports.capital_risk_emit.build_capital_risk_report_for_scenario`.

    Returns:
        The paths written, the sections left out, and the PDF's print provenance.

    Raises:
        app.reports.dbpl.DbplDependencyError: ``require_pdf`` is true and the ``[report]`` extra
            is incomplete. The HTML has been written by then.
    """
    html_path = Path(output_html_path)
    pdf_path = (
        Path(output_pdf_path)
        if output_pdf_path is not None
        else html_path.with_suffix(".pdf")
    )
    scenario = dict(load_scenario_config(str(scenario_config_path)))

    if capital_risk is None and capital_risk_not_run is None:
        mc = scenario.get("monte_carlo")
        if not (isinstance(mc, Mapping) and mc.get("parameters")):
            capital_risk_not_run = f"not run: {NO_MONTE_CARLO_PARAMETERS}"
        else:
            from app.reports.capital_risk_emit import (
                DEFAULT_CAPITAL_RISK_N_TRIALS,
                build_capital_risk_report_for_scenario,
            )

            builder = capital_risk_builder or build_capital_risk_report_for_scenario
            try:
                capital_risk = builder(
                    scenario_config_path,
                    html_path.parent / LENDER_REPORT_FILES_DIR,
                    n_trials=(
                        DEFAULT_CAPITAL_RISK_N_TRIALS if n_trials is None else n_trials
                    ),
                    seed=seed,
                    npv_metric=npv_metric,
                )
            except (
                Exception
            ) as exc:  # noqa: BLE001 - listed with its reason, never silent
                capital_risk_not_run = (
                    "not run: the Monte Carlo did not meet the lender guards "
                    f"({type(exc).__name__}: {exc})"
                )

    sensitivity = sensitivity_computer(scenario, profile=profile)
    left_out = sections_not_run(
        sensitivity, scenario, capital_risk_not_run=capital_risk_not_run
    )
    case = report_case_from_pipeline_result(
        result,
        scenario_config=scenario,
        scenario_variant=scenario_variant or Path(str(scenario_config_path)).stem,
        generated_at=generated_at
        or datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    context = build_report_context_from_case(
        case,
        sensitivity,
        capital_risk=capital_risk,
        sections_not_run=left_out,
    ).model_copy(update={"f5_notice": EXECUTIVE_WORKBOOK_F5_CAVEAT})
    html = render_report_html(context)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding="utf-8")

    from app.reports.dbpl import DbplDependencyError

    try:
        provenance = _render_pdf(context, html, pdf_path)
    except DbplDependencyError as exc:
        if require_pdf:
            raise
        return LenderReportOutput(
            html_path=html_path,
            pdf_path=None,
            pdf_not_written=f"the DBPL print stack is incomplete: {exc}",
            sections_not_run=tuple(left_out),
        )
    return LenderReportOutput(
        html_path=html_path,
        pdf_path=pdf_path,
        pdf_not_written=None,
        sections_not_run=tuple(left_out),
        pdf_provenance=provenance,
    )

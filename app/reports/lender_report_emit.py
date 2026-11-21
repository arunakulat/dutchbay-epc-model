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

import dataclasses
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
    "DOCUMENT_STATUS",
    "DbplFurniture",
    "LenderReportOutput",
    "dbpl_furniture_for",
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
_BODY = re.compile(r"<body\b[^>]*>(.*)</body>", re.DOTALL | re.IGNORECASE)
_FIRST_H1 = re.compile(r"<h1\b[^>]*>.*?</h1>\s*", re.DOTALL | re.IGNORECASE)
_H2_CLOSE = re.compile(r"</h2>", re.IGNORECASE)
#: A numeric cell or header: the report's screen rule for ``.num`` is dropped with its
#: stylesheet, so the house ``dbpl-num`` class carries the right alignment in print.
_NUM_CELL = re.compile(
    r'<(td|th)\b([^>]*?)\bclass\s*=\s*"([^"]*\bnum\b[^"]*)"', re.IGNORECASE
)
#: The headings a table's source note names, and the table ends it is put after.
_TABLE_ANCHOR = re.compile(
    r"<(h2|h3)\b[^>]*>(.*?)</\1>|</table>", re.DOTALL | re.IGNORECASE
)
_TAGS = re.compile(r"<[^>]+>")
_PROVENANCE_OPEN = '<div class="dbpl-provenance">'
_DBPL_TEMPLATE_DIR = Path(__file__).resolve().parent / "dbpl" / "templates"

#: Status / reason for issue of every command-line lender report. A model run issues a draft:
#: nobody has checked, reviewed or approved it, and F-5 holds.
DOCUMENT_STATUS = (
    "Draft - model output for screening; not reviewed; no lender reliance (F-5)"
)


@dataclass(frozen=True)
class DbplFurniture:
    """The DBPL structural furniture of one printed lender report (``DBPL-01``).

    The house base template (``dbpl_base.html.j2``) renders all of it: the running banner and
    doc-line on every page, the title with its headline caveat, the document-control block
    (control table and revision history with the four-eyes chain) and the print provenance.
    ``caveat`` is also put under every section heading of the report body, un-suppressibly.
    """

    document_id: str
    version: str
    issue_date: str
    status: str
    banner: str
    title: str
    caveat: str
    control: tuple[tuple[str, str], ...]
    revisions: tuple[Mapping[str, str], ...]
    provenance_lines: tuple[str, ...] = ()
    #: The documentary source printed under every table (``DBPL-01``: "a documentary source
    #: for every table"): the model run that produced the figures, by commit and scenario
    #: digest. Each note also names the section the table sits in.
    table_source: str = ""

    def as_doc(self) -> Dict[str, Any]:
        """Return the ``doc`` mapping the DBPL base template reads (no body sections)."""
        return {
            "language": "en",
            "banner": self.banner,
            "document_id": self.document_id,
            "version": self.version,
            "issue_date": self.issue_date,
            "status": self.status,
            "title": self.title,
            "headline_caveat": self.caveat,
            "section_caveat": self.caveat,
            "control_section_number": 0,
            "control": list(self.control),
            "revisions": list(self.revisions),
            "revision_source": (
                "Generated by run_full_pipeline_v14 (emit_lender_report); no human sign-off "
                "is recorded on a model run."
            ),
            "sections": [],
            "first_section_number": 1,
            "provenance_lines": list(self.provenance_lines),
        }


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").upper() or "SCENARIO"


def dbpl_furniture_for(context: ReportContext) -> DbplFurniture:
    """Build the document identity and control furniture for one lender report."""
    issue_date = context.generated_at[:10]
    document_id = (
        f"DBAY-LR-{_slug(context.scenario_variant)}-{issue_date.replace('-', '')}"
    )
    manifest = context.manifest or {}
    control: list[tuple[str, str]] = [
        ("Document ID", document_id),
        ("Title", context.meta.title),
        ("Scenario", context.scenario_variant),
        ("Report version", str(context.meta.version)),
        ("Generated", context.generated_at),
        ("Status / Reason for issue", DOCUMENT_STATUS),
        ("Classification", context.meta.confidentiality),
    ]
    for key, label in (
        ("git_sha", "Model commit"),
        ("config_sha256", "Scenario config SHA-256"),
    ):
        value = manifest.get(key)
        if value:
            control.append((label, str(value)))
    run_identity = [f"run_full_pipeline_v14 on scenario {context.scenario_variant}"]
    if manifest.get("git_sha"):
        run_identity.append(f"model commit {str(manifest['git_sha'])[:12]}")
    if manifest.get("config_sha256"):
        run_identity.append(
            f"scenario config SHA-256 {str(manifest['config_sha256'])[:16]}"
        )
    table_source = (
        f"{document_id}, model output of {', '.join(run_identity)}; "
        f"generated {context.generated_at}"
    )
    return DbplFurniture(
        document_id=document_id,
        table_source=table_source,
        version=f"v{context.meta.version}",
        issue_date=issue_date,
        status="Draft",
        banner=(
            f"{context.meta.confidentiality} | Model output: no lender reliance (F-5)"
        ),
        title=context.meta.title,
        caveat=EXECUTIVE_WORKBOOK_F5_CAVEAT,
        control=tuple(control),
        revisions=(
            {
                "rev": "P01",
                "date": issue_date,
                "status": DOCUMENT_STATUS,
                "prepared": "Model run (automated)",
            },
        ),
    )


def _render_base(furniture: DbplFurniture) -> str:
    from jinja2 import Environment, FileSystemLoader

    env = Environment(
        loader=FileSystemLoader(str(_DBPL_TEMPLATE_DIR)),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return env.get_template("dbpl_base.html.j2").render(doc=furniture.as_doc())


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def to_dbpl_print_html(html: str, furniture: DbplFurniture) -> str:
    """Print the lender report through the DBPL base template (``DBPL-01``).

    The report body is carried into the house base template, which is extended, not forked:
    the base renders the running banner and doc-line (document ID on every page), the title
    and its headline caveat, the document-control block and the print provenance. Into that
    skeleton goes the report body, re-dressed for print: its screen stylesheet (literal colours
    and sizes) is dropped, its own title is dropped (the base prints it), the house classes are
    added to headings and tables, and the F-5 caveat band is put under every section heading,
    so no section, the capital-risk pages included, prints without it. The text, figures and
    section order of the report are unchanged.

    Args:
        html: The rendered lender report.
        furniture: The document identity, control and provenance furniture.

    Returns:
        HTML ready for :func:`app.reports.dbpl.print_core.render_dbpl_pdf`.

    Raises:
        ValueError: the report HTML has no ``<body>`` element.
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

    body_match = _BODY.search(_STYLE_BLOCK.sub("", html, count=1))
    if body_match is None:
        raise ValueError("the lender report HTML has no <body> element")
    body = _FIRST_H1.sub("", body_match.group(1), count=1)
    band = f'</h2>\n<div class="dbpl-caveat">{_escape(furniture.caveat)}</div>'
    body = _H2_CLOSE.sub(lambda _m: band, body)
    body = _OPEN_TAG.sub(add_class, body)
    body = _NUM_CELL.sub(
        lambda m: f'<{m.group(1)}{m.group(2)}class="{m.group(3)} dbpl-num"', body
    )
    body = _add_table_sources(body, furniture.table_source)

    base = _render_base(furniture)
    at = base.find(_PROVENANCE_OPEN)
    if at < 0:
        at = base.rfind("</body>")
    return base[:at] + body + "\n" + base[at:]


def _add_table_sources(body: str, source: str) -> str:
    """Put a DBPL source note under every table, naming the section it sits in.

    The note uses the house note block (``dbpl-tablenotes`` / ``dbpl-source``), placed
    immediately below the table as the ADB order requires. The section is the nearest
    preceding ``<h3>``, or ``<h2>`` when no ``<h3>`` follows it.
    """
    section = ""
    out: List[str] = []
    last = 0
    for m in _TABLE_ANCHOR.finditer(body):
        if m.group(1):
            text = " ".join(_TAGS.sub(" ", m.group(2)).split())
            section = text
            continue
        out.append(body[last : m.end()])
        where = f"; section: {section}" if section else ""
        out.append(
            '\n<div class="dbpl-tablenotes"><div class="dbpl-source">'
            f'<span class="dbpl-label">Source:</span> {_escape(source + where)}.</div></div>'
        )
        last = m.end()
    out.append(body[last:])
    return "".join(out)


def _render_pdf(context: ReportContext, html: str, pdf_path: Path) -> tuple[str, ...]:
    """Print the PDF twice: the second pass stamps the first pass's provenance into it."""
    from app.reports.dbpl import render_dbpl_pdf

    furniture = dbpl_furniture_for(context)
    first = render_dbpl_pdf(to_dbpl_print_html(html, furniture))
    stamped = dataclasses.replace(
        furniture, provenance_lines=tuple(first.provenance_lines())
    )
    result = render_dbpl_pdf(to_dbpl_print_html(html, stamped))
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
                    "not run: the Monte Carlo could not run under the lender guards "
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

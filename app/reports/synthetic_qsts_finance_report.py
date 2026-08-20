"""Render and publish the governed #1074 synthetic process-provenance report."""

from __future__ import annotations

import io
import os
import shutil
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from jinja2 import Environment, FileSystemLoader

from analytics.contracts_v14 import (
    SYNTHETIC_PROCESS_PROVENANCE_REPORT_SCHEMA,
    SYNTHETIC_PROCESS_PROVENANCE_WARNING,
    SyntheticProcessProvenanceReportRecord,
)
from analytics.run_manifest import config_sha256, git_sha
from analytics.synthetic_qsts_finance_counterfactual import (
    AuthenticatedSyntheticReportInputs,
    SyntheticCounterfactualEvaluation,
    canonical_json,
    evaluate_synthetic_qsts_finance_counterfactual,
    load_authenticated_synthetic_report_inputs,
    sha256_bytes,
    sha256_path,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = Path(__file__).resolve()
_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_TEMPLATE_NAME = "synthetic_qsts_finance_report.html.j2"
_TEMPLATE_PATH = _TEMPLATE_DIR / _TEMPLATE_NAME
_OUTPUT_DIR = "outputs/synthetic_process_provenance/issue_1074"
_HTML_FILENAME = "synthetic_qsts_finance_report.html"
_PDF_FILENAME = "synthetic_qsts_finance_report.pdf"
_RECORD_FILENAME = "synthetic_qsts_finance_report_manifest.json"
_RECORD_CHECKSUM_FILENAME = "synthetic_qsts_finance_report_manifest.sha256"
_HTML_CHECKSUM_FILENAME = "synthetic_qsts_finance_report.html.sha256"
_PDF_CHECKSUM_FILENAME = "synthetic_qsts_finance_report.pdf.sha256"
_EXPECTED_PAGE_COUNT = 4

PdfRenderer = Callable[[str], tuple[bytes, int]]
PdfWarningVerifier = Callable[[bytes, str], tuple[int, int]]
FinanceEvaluator = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class SyntheticFinanceReportConfig:
    """Strict config-first controls for the #1074 report workflow."""

    handoff_path: str
    expected_handoff_sha256: str
    qsts_output_path: str
    expected_qsts_output_sha256: str
    scenario_path: str
    report_title: str
    warning: str
    render_backend: str
    expected_pdf_pages: int
    override_key: str
    deemed_paid_treatment: str
    finance_wiring_enabled: bool
    canonical_eligible: bool
    output_dir: str
    html_filename: str
    pdf_filename: str
    record_filename: str
    record_checksum_filename: str
    html_checksum_filename: str
    pdf_checksum_filename: str
    allow_existing_identical: bool

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "SyntheticFinanceReportConfig":
        """Parse exact nested report config without silent defaults."""

        root = _exact_mapping(
            raw, "config", {"input", "scenario", "report", "finance", "output"}
        )
        input_raw = _exact_mapping(
            root["input"],
            "input",
            {
                "handoff_path",
                "expected_handoff_sha256",
                "qsts_output_path",
                "expected_qsts_output_sha256",
            },
        )
        scenario_raw = _exact_mapping(root["scenario"], "scenario", {"path"})
        report_raw = _exact_mapping(
            root["report"],
            "report",
            {"title", "warning", "render_backend", "expected_pdf_pages"},
        )
        finance_raw = _exact_mapping(
            root["finance"],
            "finance",
            {
                "override_key",
                "deemed_paid_treatment",
                "finance_wiring_enabled",
                "canonical_eligible",
            },
        )
        output_raw = _exact_mapping(
            root["output"],
            "output",
            {
                "output_dir",
                "html_filename",
                "pdf_filename",
                "record_filename",
                "record_checksum_filename",
                "html_checksum_filename",
                "pdf_checksum_filename",
                "allow_existing_identical",
            },
        )
        config = cls(
            handoff_path=_safe_relative_path(
                input_raw["handoff_path"], "input.handoff_path"
            ),
            expected_handoff_sha256=_require_sha256(
                input_raw["expected_handoff_sha256"], "input.expected_handoff_sha256"
            ),
            qsts_output_path=_safe_relative_path(
                input_raw["qsts_output_path"], "input.qsts_output_path"
            ),
            expected_qsts_output_sha256=_require_sha256(
                input_raw["expected_qsts_output_sha256"],
                "input.expected_qsts_output_sha256",
            ),
            scenario_path=_safe_relative_path(scenario_raw["path"], "scenario.path"),
            report_title=_nonempty_string(report_raw["title"], "report.title"),
            warning=_nonempty_string(report_raw["warning"], "report.warning"),
            render_backend=_nonempty_string(
                report_raw["render_backend"], "report.render_backend"
            ),
            expected_pdf_pages=_exact_int(
                report_raw["expected_pdf_pages"], "report.expected_pdf_pages"
            ),
            override_key=_nonempty_string(
                finance_raw["override_key"], "finance.override_key"
            ),
            deemed_paid_treatment=_nonempty_string(
                finance_raw["deemed_paid_treatment"], "finance.deemed_paid_treatment"
            ),
            finance_wiring_enabled=_exact_bool(
                finance_raw["finance_wiring_enabled"], "finance.finance_wiring_enabled"
            ),
            canonical_eligible=_exact_bool(
                finance_raw["canonical_eligible"], "finance.canonical_eligible"
            ),
            output_dir=_safe_relative_path(
                output_raw["output_dir"], "output.output_dir"
            ),
            html_filename=_safe_filename(
                output_raw["html_filename"], "output.html_filename"
            ),
            pdf_filename=_safe_filename(
                output_raw["pdf_filename"], "output.pdf_filename"
            ),
            record_filename=_safe_filename(
                output_raw["record_filename"], "output.record_filename"
            ),
            record_checksum_filename=_safe_filename(
                output_raw["record_checksum_filename"],
                "output.record_checksum_filename",
            ),
            html_checksum_filename=_safe_filename(
                output_raw["html_checksum_filename"], "output.html_checksum_filename"
            ),
            pdf_checksum_filename=_safe_filename(
                output_raw["pdf_checksum_filename"], "output.pdf_checksum_filename"
            ),
            allow_existing_identical=_exact_bool(
                output_raw["allow_existing_identical"],
                "output.allow_existing_identical",
            ),
        )
        config._require_governed_values()
        return config

    def _require_governed_values(self) -> None:
        expected = {
            "warning": SYNTHETIC_PROCESS_PROVENANCE_WARNING,
            "render_backend": "weasyprint",
            "expected_pdf_pages": _EXPECTED_PAGE_COUNT,
            "override_key": "project.curtailment_pct",
            "deemed_paid_treatment": "kpi_neutral_excluded_from_finance_override",
            "finance_wiring_enabled": False,
            "canonical_eligible": False,
            "output_dir": _OUTPUT_DIR,
            "html_filename": _HTML_FILENAME,
            "pdf_filename": _PDF_FILENAME,
            "record_filename": _RECORD_FILENAME,
            "record_checksum_filename": _RECORD_CHECKSUM_FILENAME,
            "html_checksum_filename": _HTML_CHECKSUM_FILENAME,
            "pdf_checksum_filename": _PDF_CHECKSUM_FILENAME,
        }
        for field_name, value in expected.items():
            if getattr(self, field_name) != value:
                raise ValueError(
                    f"#1074 governed config requires {field_name}={value!r}."
                )

    def identity_mapping(self) -> dict[str, Any]:
        """Return every resolved control retained by the report record."""

        return {
            "input": {
                "handoff_path": self.handoff_path,
                "expected_handoff_sha256": self.expected_handoff_sha256,
                "qsts_output_path": self.qsts_output_path,
                "expected_qsts_output_sha256": self.expected_qsts_output_sha256,
            },
            "scenario": {"path": self.scenario_path},
            "report": {
                "title": self.report_title,
                "warning": self.warning,
                "render_backend": self.render_backend,
                "expected_pdf_pages": self.expected_pdf_pages,
            },
            "finance": {
                "override_key": self.override_key,
                "deemed_paid_treatment": self.deemed_paid_treatment,
                "finance_wiring_enabled": False,
                "canonical_eligible": False,
            },
            "output": {
                "output_dir": self.output_dir,
                "html_filename": self.html_filename,
                "pdf_filename": self.pdf_filename,
                "record_filename": self.record_filename,
                "record_checksum_filename": self.record_checksum_filename,
                "html_checksum_filename": self.html_checksum_filename,
                "pdf_checksum_filename": self.pdf_checksum_filename,
                "allow_existing_identical": self.allow_existing_identical,
            },
        }


def _exact_mapping(value: object, field: str, expected: set[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != expected:
        actual = sorted(value) if isinstance(value, Mapping) else type(value).__name__
        raise ValueError(
            f"{field} keys must be exactly {sorted(expected)}, got {actual}."
        )
    return cast(Mapping[str, Any], value)


def _safe_relative_path(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.startswith(("/", "~"))
        or "\\" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise ValueError(f"{field} must be a safe repository-relative path.")
    return value


def _safe_filename(value: object, field: str) -> str:
    path = _safe_relative_path(value, field)
    if "/" in path:
        raise ValueError(f"{field} must be a filename.")
    return path


def _require_sha256(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{field} must be an exact lowercase SHA-256.")
    return value


def _nonempty_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string.")
    return value


def _exact_int(value: object, field: str) -> int:
    if type(value) is not int or value <= 0:  # noqa: E721
        raise ValueError(f"{field} must be a positive integer.")
    return value


def _exact_bool(value: object, field: str) -> bool:
    if type(value) is not bool:  # noqa: E721
        raise ValueError(f"{field} must be a literal boolean.")
    return value


def _reject_symlink_ancestors(path: Path, field: str) -> None:
    candidate = path.absolute()
    for ancestor in (candidate, *candidate.parents):
        if ancestor.exists() and ancestor.is_symlink():
            raise ValueError(f"{field} must not traverse a symlinked ancestor.")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _render_pdf_weasyprint(html: str) -> tuple[bytes, int]:
    """Render the dedicated HTML with the optional governed PDF backend."""

    try:
        from weasyprint import HTML
    except (ImportError, OSError) as exc:
        raise RuntimeError(
            "#1074 PDF rendering requires the governed [report] WeasyPrint environment."
        ) from exc
    document = HTML(string=html, base_url=str(_TEMPLATE_DIR)).render()
    return cast(bytes, document.write_pdf()), len(document.pages)


def _verify_pdf_warning(pdf: bytes, warning: str) -> tuple[int, int]:
    """Extract each PDF page and count pages carrying the exact warning."""

    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError(
            "#1074 PDF verification requires the governed pdfplumber dependency."
        ) from exc
    with pdfplumber.open(io.BytesIO(pdf)) as document:
        texts = [page.extract_text() or "" for page in document.pages]
    return len(texts), sum(warning in text for text in texts)


def _format_pct(value: float) -> str:
    return f"{value * 100:,.4f}%"


def _format_pp(value: float) -> str:
    return f"{value * 100:+,.4f} pp"


def _format_money(value: float) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.0f}"


def _format_money_delta(value: float) -> str:
    sign = "+" if value > 0 else "-" if value < 0 else ""
    return f"{sign}${abs(value):,.0f}"


def _format_mwh(value: float) -> str:
    return f"{value:,.3f} MWh"


def _format_mwh_delta(value: float) -> str:
    return f"{value:+,.3f} MWh"


def _environment() -> Environment:
    environment = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    environment.globals.update(
        fmt_pct=_format_pct,
        fmt_pp=_format_pp,
        fmt_money=_format_money,
        fmt_money_delta=_format_money_delta,
        fmt_mwh=_format_mwh,
        fmt_mwh_delta=_format_mwh_delta,
    )
    return environment


def _render_html(context: Mapping[str, Any]) -> str:
    return _environment().get_template(_TEMPLATE_NAME).render(ctx=context)


def _require_warning_on_every_html_page(html: str, warning: str, expected: int) -> int:
    marker = '<section class="page">'
    pages = html.split(marker)[1:]
    if len(pages) != expected or any(warning not in page for page in pages):
        raise ValueError(
            "The exact synthetic warning is not present on every HTML page."
        )
    occurrences = html.count(warning)
    if occurrences < expected:
        raise ValueError("The exact synthetic warning is not persistent in HTML.")
    return occurrences


def _context(
    *,
    config: SyntheticFinanceReportConfig,
    inputs: AuthenticatedSyntheticReportInputs,
    evaluation: SyntheticCounterfactualEvaluation,
    generated_at_utc: str,
) -> dict[str, Any]:
    qsts = inputs.qsts
    return {
        "title": config.report_title,
        "warning": config.warning,
        "generated_at_utc": generated_at_utc,
        "repository_commit": git_sha(),
        "handoff_sha256": inputs.handoff_sha256,
        "qsts_sha256": inputs.qsts_sha256,
        "manifest_sha256": qsts.input_package_manifest_sha256,
        "profile_sha256": qsts.input_profile_sha256,
        "profile_values_sha256": qsts.input_profile_values_sha256,
        "qsts": qsts,
        "evaluation": evaluation,
        "baseline": evaluation.kpis.baseline,
        "counterfactual": evaluation.kpis.counterfactual,
        "movement": evaluation.kpis.movement,
    }


def _publish(
    *,
    output_dir: Path,
    config: SyntheticFinanceReportConfig,
    html: bytes,
    pdf: bytes,
    record: SyntheticProcessProvenanceReportRecord,
) -> str:
    _reject_symlink_ancestors(output_dir, "#1074 output directory")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    record_payload = canonical_json(record.model_dump())
    record_digest = sha256_bytes(record_payload)
    payloads = {
        config.html_filename: html,
        config.pdf_filename: pdf,
        config.record_filename: record_payload,
        config.record_checksum_filename: (
            f"{record_digest}  {config.record_filename}\n".encode("ascii")
        ),
        config.html_checksum_filename: (
            f"{sha256_bytes(html)}  {config.html_filename}\n".encode("ascii")
        ),
        config.pdf_checksum_filename: (
            f"{sha256_bytes(pdf)}  {config.pdf_filename}\n".encode("ascii")
        ),
    }
    stage = Path(
        tempfile.mkdtemp(prefix=".issue1074-stage-", dir=str(output_dir.parent))
    )
    try:
        for name, payload in payloads.items():
            (stage / name).write_bytes(payload)
        if output_dir.exists():
            entries = tuple(output_dir.iterdir())
            if (
                not config.allow_existing_identical
                or {entry.name for entry in entries} != set(payloads)
                or any(entry.is_symlink() or not entry.is_file() for entry in entries)
                or any(
                    (output_dir / name).read_bytes() != payload
                    for name, payload in payloads.items()
                )
            ):
                raise FileExistsError(
                    "A differing or incomplete #1074 output already exists."
                )
            shutil.rmtree(stage)
        else:
            os.replace(stage, output_dir)
    except Exception:
        if stage.exists():
            shutil.rmtree(stage)
        raise
    return record_digest


def generate_synthetic_qsts_finance_report(
    *,
    config: SyntheticFinanceReportConfig,
    repo_root: Path = _REPO_ROOT,
    generated_at_utc: str | None = None,
    pdf_renderer: PdfRenderer = _render_pdf_weasyprint,
    pdf_warning_verifier: PdfWarningVerifier = _verify_pdf_warning,
    finance_evaluator: FinanceEvaluator | None = None,
    output_dir_override: Path | None = None,
) -> tuple[SyntheticProcessProvenanceReportRecord, str]:
    """Authenticate inputs, evaluate the counterfactual, render, verify, and publish."""

    repo = repo_root.resolve()
    handoff_path = repo.joinpath(*config.handoff_path.split("/"))
    qsts_path = repo.joinpath(*config.qsts_output_path.split("/"))
    scenario_path = repo.joinpath(*config.scenario_path.split("/"))
    output_dir = output_dir_override or repo.joinpath(*config.output_dir.split("/"))
    inputs = load_authenticated_synthetic_report_inputs(
        handoff_path=handoff_path,
        expected_handoff_sha256=config.expected_handoff_sha256,
        qsts_output_path=qsts_path,
        expected_qsts_output_sha256=config.expected_qsts_output_sha256,
    )
    scenario_before = scenario_path.read_bytes()
    evaluation = (
        evaluate_synthetic_qsts_finance_counterfactual(
            inputs=inputs,
            scenario_path=scenario_path,
            evaluator=finance_evaluator,
        )
        if finance_evaluator is not None
        else evaluate_synthetic_qsts_finance_counterfactual(
            inputs=inputs, scenario_path=scenario_path
        )
    )
    if evaluation.override_items != (
        (config.override_key, evaluation.counterfactual_project_curtailment_decimal),
    ):
        raise ValueError(
            "#1074 finance override is not the exact governed one-key set."
        )
    if (
        handoff_path.read_bytes() != inputs.handoff_payload
        or qsts_path.read_bytes() != inputs.qsts_payload
        or scenario_path.read_bytes() != scenario_before
    ):
        raise ValueError(
            "An authenticated #1074 input changed during finance evaluation."
        )
    generated = generated_at_utc or _utc_now()
    context = _context(
        config=config, inputs=inputs, evaluation=evaluation, generated_at_utc=generated
    )
    html_text = _render_html(context)
    html_warning_occurrences = _require_warning_on_every_html_page(
        html_text, config.warning, config.expected_pdf_pages
    )
    html = html_text.encode("utf-8")
    pdf, rendered_pages = pdf_renderer(html_text)
    verified_pages, warning_pages = pdf_warning_verifier(pdf, config.warning)
    if (
        rendered_pages != config.expected_pdf_pages
        or verified_pages != rendered_pages
        or warning_pages != rendered_pages
        or not pdf.startswith(b"%PDF-")
    ):
        raise ValueError(
            "Rendered PDF page count or persistent warning verification failed."
        )
    qsts = inputs.qsts
    record = SyntheticProcessProvenanceReportRecord(
        schema=SYNTHETIC_PROCESS_PROVENANCE_REPORT_SCHEMA,
        issue=1074,
        source_input_issue=1077,
        source_qsts_issue=1073,
        generated_at_utc=generated,
        repository_commit=git_sha(),
        report_code_sha256=sha256_path(_MODULE_PATH),
        report_template_sha256=sha256_path(_TEMPLATE_PATH),
        resolved_report_config_sha256=config_sha256(config.identity_mapping()),
        scenario_path=config.scenario_path,
        scenario_sha256=sha256_bytes(scenario_before),
        input_handoff_schema=inputs.handoff.schema,
        input_handoff_sha256=inputs.handoff_sha256,
        qsts_output_schema=qsts.schema,
        qsts_output_sha256=inputs.qsts_sha256,
        package_manifest_sha256=qsts.input_package_manifest_sha256,
        profile_sha256=qsts.input_profile_sha256,
        profile_values_sha256=qsts.input_profile_values_sha256,
        profile_row_count=qsts.profile_row_count,
        profile_start_utc=qsts.profile_start_utc,
        profile_end_utc=qsts.profile_end_utc,
        profile_timezone=qsts.profile_timezone,
        profile_timestep_hours=qsts.profile_timestep_hours,
        profile_unit=qsts.profile_unit,
        synthetic_aep_mwh=qsts.synthetic_aep_mwh,
        synthetic_aep_gwh=qsts.synthetic_aep_gwh,
        gross_energy_mwh=qsts.gross_energy_mwh,
        delivered_energy_mwh=qsts.delivered_energy_mwh,
        deemed_paid_energy_mwh=qsts.deemed_paid_energy_mwh,
        self_curtailed_pre_bess_mwh=qsts.self_curtailed_pre_bess_mwh,
        bess_recovered_energy_mwh=qsts.bess_recovered_energy_mwh,
        self_curtailed_energy_mwh=qsts.self_curtailed_energy_mwh,
        curtailed_total_mwh=qsts.curtailed_total_mwh,
        export_cap_breach_timesteps=qsts.export_cap_breach_timesteps,
        energy_balance_residual_mwh=qsts.energy_balance_residual_mwh,
        qsts_attempted_steps=qsts.solver_telemetry.attempted_steps,
        qsts_converged_steps=qsts.solver_telemetry.converged_steps,
        qsts_nonconverged_steps=qsts.solver_telemetry.nonconverged_steps,
        voltage_violation_steps=cast(
            int, qsts.solver_telemetry.voltage_violation_steps
        ),
        thermal_violation_steps=cast(
            int, qsts.solver_telemetry.thermal_violation_steps
        ),
        operator_schedule_status=qsts.operator_schedule_status,
        baseline_project_curtailment_decimal=evaluation.baseline_project_curtailment_decimal,
        synthetic_self_curtailment_decimal=evaluation.synthetic_self_curtailment_decimal,
        counterfactual_project_curtailment_decimal=evaluation.counterfactual_project_curtailment_decimal,
        deemed_paid_finance_haircut_decimal=0.0,
        kpis=evaluation.kpis,
        report_html_filename=config.html_filename,
        report_html_sha256=sha256_bytes(html),
        report_pdf_filename=config.pdf_filename,
        report_pdf_sha256=sha256_bytes(pdf),
        pdf_page_count=rendered_pages,
        pdf_warning_page_count=warning_pages,
        html_warning_occurrences=html_warning_occurrences,
        input_kind="synthetic_placeholder",
        output_class="synthetic_process_provenance_financial_report",
        finance_mode="segregated_synthetic_counterfactual",
        required_warning=config.warning,
        generated_input=True,
        observed_network_data=False,
        site_representative=False,
        canonical_finance_eligible=False,
        bankable=False,
        publishable=False,
        lender_eligible=False,
        board_eligible=False,
        approval_eligible=False,
        release_eligible=False,
        finance_wiring_enabled=False,
        canonical_finance_executed=False,
        segregated_counterfactual_finance_executed=True,
        canonical_scenario_mutated=False,
        canonical_expected_results_mutated=False,
        canonical_finance_release_refused=True,
    )
    digest = _publish(
        output_dir=output_dir, config=config, html=html, pdf=pdf, record=record
    )
    return record, digest


def cli_summary(
    record: SyntheticProcessProvenanceReportRecord,
    digest: str,
    config: SyntheticFinanceReportConfig,
) -> dict[str, Any]:
    """Return the concise warning-bearing #1074 CLI receipt."""

    return {
        "status": "PASS",
        "issue": 1074,
        "required_warning": record.required_warning,
        "record_path": f"{config.output_dir}/{config.record_filename}",
        "record_sha256": digest,
        "html_sha256": record.report_html_sha256,
        "pdf_sha256": record.report_pdf_sha256,
        "pdf_page_count": record.pdf_page_count,
        "pdf_warning_page_count": record.pdf_warning_page_count,
        "synthetic_aep_gwh": record.synthetic_aep_gwh,
        "synthetic_self_curtailment_pct": record.synthetic_self_curtailment_decimal
        * 100.0,
        "counterfactual_finance_executed": True,
        "canonical_finance_wiring_enabled": False,
        "canonical_finance_release": "REFUSED",
        "canonical_finance_eligible": False,
        "bankable": False,
        "publishable": False,
    }


__all__ = [
    "SyntheticFinanceReportConfig",
    "cli_summary",
    "generate_synthetic_qsts_finance_report",
]

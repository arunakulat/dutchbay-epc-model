"""Opt-in production caller for the design-stage GRID-SCREENING report section (#884, D8).

This is the pivotal reporting dolphin of the grid-capability epic (#870): it SURFACES the
in-house Python grid study (the D1–D7 screens) in a lender-facing report, wrapped in an
**un-suppressible** SCREENING-NOT-BANKABLE + EMT-gap caveat and full engineering-discipline
provenance. It follows the opt-in / latency-gated pattern of the three sibling emitters
(:mod:`app.reports.capital_risk_emit`, :mod:`app.reports.interaction_grid_emit`,
:mod:`app.reports.tech_comparison_emit`) exactly:

* a PURE emitter invoked opt-in and default-off from the batch CLI
  (``run_full_pipeline_v14.py``) after a successful finance run;
* the heavy screens (pandapower / ANDES / OpenDSS time-domain work) belong on the batch /
  async-job path — NEVER the synchronous HTTP report route (the #645 latency ledger);
* ``emit_grid_screen:false`` (the default) → the section is omitted → committed-scenario
  output is BYTE-IDENTICAL and nothing enters finance.

THE CARDINAL RULE — the grid study is ADVISORY (``bankable=False`` on every sub-screen) and
NEVER feeds CFADS / IRR / DSCR. Enabling or emitting this report changes NO committed
pipeline KPI; it only writes an additional advisory HTML artifact and echoes its path back.

Un-suppressible caveat
-----------------------
Every grid report surface carries the machine-stamped caveat
(:data:`MANDATORY_SCREENING_CAVEAT`) and, for a marginal SCR (``< GRID_EMT_CONFIRMATION_SCR``),
an ``EMT confirmation required`` stamp. These are baked STRUCTURALLY into the template and the
assembled model — there is no config toggle that removes them. The caveat cites the real
#868 CEB (2025/003/C) / NSO (2026/001/C) tender evidence so the EMT boundary is EVIDENCED,
not abstract (see ``docs/knowledge_base/grid_screening_scope.md``).

Provenance (surfaced, not internal — the ``surface-provenance-in-presentation-layer`` directive)
-------------------------------------------------------------------------------------------------
The report surfaces (a) DEPENDENCY RESOLUTION / reproducibility — the resolved ``[grid]`` pin
set (pandapower==3.3.0 / andes>=2.0 / opendssdirect.py>=0.9.4) plus the CASPER
available-vs-degraded state of each optional engine at run-time — and (b) VERIFICATION
DISCIPLINE — that the results are adversarially reviewed, KPI-neutral / oracle byte-identical,
and degrade gracefully when an engine is absent.

CASPER
------
The heavy libraries are guarded at call-time inside each screen, so this emitter imports
cleanly in a grid-free environment. Each screen is run best-effort: a missing optional engine
or a screen-specific config gap DEGRADES that screen to an honest "not run" state (surfaced in
the report), it does NOT crash the emitter. The two core screens (SCR + reactive, via the D3
gateway) are the only mandatory ones — the gateway itself falls back to closed-form when
pandapower is absent, so even those never hard-require the extra.

GWTF:
    - CESSPIT: fail-loud only on the master gate — a scenario opted into this report with no
      ``grid`` block, or ``grid.study_enabled`` not True, RAISES (the caller must gate on
      ``study_enabled`` first). Individual downstream screens degrade rather than raise.
    - CCCDIR/ARCH: consumes the grid gateway (:func:`analytics.grid.evaluate_grid.evaluate_grid`)
      and the grid screen entrypoints under ``analytics.grid.*`` + the frozen result contracts
      from ``analytics.contracts_v14`` only. No finance / IRR logic lives here.
"""

from __future__ import annotations

import platform
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Mapping, Optional

from jinja2 import Environment, FileSystemLoader

from analytics.contracts_v14 import (
    GRID_EMT_CONFIRMATION_SCR,
    CurtailmentShareResult,
    FreqResponseResult,
    GridStudyResult,
    HarmonicComplianceResult,
    PocCapabilityEnvelope,
    RideThroughResult,
)
from analytics.grid.evaluate_grid import evaluate_grid
from analytics.scenario_loader import load_scenario_config

__all__ = [
    "GRID_EXTRA_PINS",
    "MANDATORY_SCREENING_CAVEAT",
    "EMT_GAP_CAVEAT",
    "EMT_CONFIRMATION_STAMP",
    "TENDER_EVIDENCE_CAVEAT",
    "SYNTHETIC_CURTAILMENT_WARNING",
    "GridScreeningModel",
    "build_grid_screening_model",
    "emit_grid_screening_report_from_pipeline",
]

# ═════════════════════════════════════════════════════════════════════════════
# The UN-SUPPRESSIBLE caveats. These are module constants baked into the model and
# the template — there is NO config path that removes them. A grid screen presented
# without the screening-not-bankable + EMT-gap caveat would be a lender-facing
# misrepresentation, so the caveat is structural, not a toggle.
# ═════════════════════════════════════════════════════════════════════════════

#: The mandatory machine-stamped headline caveat on every grid report surface.
MANDATORY_SCREENING_CAVEAT = (
    "SCREENING / DESIGN-STAGE ONLY — NOT the utility-accepted bankable grid-connection "
    "study. Every result below is ADVISORY (bankable=false) and NEVER feeds the financial "
    "model (CFADS / IRR / DSCR are unchanged). The bankable connection study is a PSS/E or "
    "PowerFactory run against the CEB/NSCC confidential grid base case with the OEM "
    ".dyr / .dll / .pfd dynamic models — this in-house screen is a design-stage pre-check, "
    "not a sign-off."
)

#: The EMT-gap caveat — the RMS/phasor boundary. Stamped alongside the headline caveat.
EMT_GAP_CAVEAT = (
    "EMT GAP: ANDES / pandapower are RMS / positive-sequence (phasor) tools only. A marginal "
    "SCR (below ~2–3) or a weak-grid interconnection is stamped 'EMT confirmation required' — "
    "the RMS screen cannot be trusted there and an EMT (PSCAD/EMTDC or EMTP) study against the "
    "utility base case with the OEM binaries is mandatory. The RMS screen is NEVER a sign-off "
    "at low SCR."
)

#: The per-SCR EMT-confirmation stamp, applied when the screened SCR is marginal
#: (< GRID_EMT_CONFIRMATION_SCR). Surfaced next to the SCR verdict, un-suppressibly.
EMT_CONFIRMATION_STAMP = (
    "EMT CONFIRMATION REQUIRED — SCR is marginal (< {threshold:g}); the RMS/phasor screen is "
    "not authoritative here. Confirm with an EMT (PSCAD/EMTDC) study against the utility base "
    "case before any design commitment."
).format(threshold=GRID_EMT_CONFIRMATION_SCR)

#: The real #868 CEB/NSO tender evidence that makes the EMT boundary EVIDENCED, not abstract.
#: Surfaced in the report so a lender sees the screen's limits are grounded in real SL tenders.
TENDER_EVIDENCE_CAVEAT = (
    "Evidence (real Sri Lankan CEB/NSO BESS tenders, #868): measured per-GSS 3-phase fault "
    "levels give SCR ≈ 33–77 across all 16 POCs (Vavunathivu 5.8 kA → SCR 33 weakest; Matara "
    "13.5 kA → SCR 77 strongest), validating this pandapower SCR@POC screen. The 160 MW round "
    "(CEB 2025/003/C) did NOT require grid-forming (SCR 33–77 ≫ the 1.2 GFL floor → GFL "
    "compliant); the 250 MW round (NSO 2026/001/C) MANDATES true grid-forming V/F (Vol I "
    "clause 3c; IEEE 1547-2018 + IEEE 2800-2022 + UL 1741-SB) → a GFL-only plant is "
    "non-compliant. BOTH rounds mandate PSS®E + PSCAD/EMTDC dynamic models proving V/P/Q at "
    "SCR = 1, 3, 5, 10 (X/R 5) plus a ±50° phase step; a real OEM (Envision) delivered "
    "RMS-only (PSS/E + DIgSILENT) → a documented EMT/PSCAD gap. The July-2024 national Grid "
    "Code Annex B is SILENT on grid-forming — the control-mode decision lives in each round's "
    "Annex A / Vol I. This is exactly the RMS→EMT boundary this screen stamps."
)

#: The un-suppressible warning applied whenever a generated/non-site-representative QSTS
#: result is presented. Integrity verification proves package identity, not site truth.
SYNTHETIC_CURTAILMENT_WARNING = (
    "SYNTHETIC COUNTERFACTUAL — NOT SITE-REPRESENTATIVE EVIDENCE. These QSTS values "
    "come from generated/test feeder inputs, not the CEB Kalpitiya/Puttalam feeder. "
    "Use them only for software-path testing and scenario learning. They are not lender "
    "evidence, not utility-accepted, not bankable, and cannot influence canonical finance "
    "or headline KPIs. A verified manifest authenticates package identity only; it does "
    "not promote synthetic inputs to real evidence."
)

#: The resolved ``[grid]`` optional-extra pin set (pyproject ``[project.optional-dependencies]
#: .grid``). Surfaced verbatim as the dependency-reproducibility provenance so a lender/auditor
#: sees the exact resolved engines the screen was built against. Kept in sync with pyproject.
GRID_EXTRA_PINS: tuple[tuple[str, str], ...] = (
    ("pandapower", "==3.3.0"),
    ("andes", ">=2.0"),
    ("opendssdirect.py", ">=0.9.4"),
)

#: The verification-discipline statement — surfaced so the report carries the engineering
#: provenance behind the results, not just the numbers (the surface-provenance directive).
VERIFICATION_DISCIPLINE = (
    "Verification discipline: this grid study is additive and default-off. It was "
    "adversarially reviewed, is KPI-neutral (the committed finance canon is oracle "
    "byte-identical whether or not the study runs — nothing here feeds CFADS / IRR / DSCR), "
    "and degrades gracefully — a missing [grid] engine or a screen-specific config gap "
    "downgrades that screen to an honest 'not run' state, surfaced below, never a fabricated "
    "pass and never a crash."
)

#: The distribution-name → import-name map for the optional engines (opendssdirect.py imports
#: as ``opendssdirect``). Used to probe available-vs-degraded state via ``importlib.metadata``.
_ENGINE_IMPORT_NAMES: dict[str, str] = {
    "pandapower": "pandapower",
    "andes": "andes",
    "opendssdirect.py": "opendssdirect",
}


# ═════════════════════════════════════════════════════════════════════════════
# Provenance / result model. Frozen dataclasses (pure data), assembled by the pure
# builder and rendered by the standalone template. Every advisory sub-result is
# optional (None when the screen degraded / did not run).
# ═════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ScreenStatus:
    """The available-vs-degraded state of ONE optional grid engine (CASPER provenance).

    Fields
        distribution: the [grid] extra distribution name (e.g. ``pandapower``).
        pin: the resolved version pin from :data:`GRID_EXTRA_PINS`.
        available: True iff the engine imported at run-time (present in the environment).
        resolved_version: the actually-installed version string, or ``None`` when absent.
    """

    distribution: str
    pin: str
    available: bool
    resolved_version: Optional[str] = None


@dataclass(frozen=True)
class GridScreeningModel:
    """The assembled, render-ready grid-screening report model (#884).

    Pure data. Every advisory sub-result mirrors an ``analytics.contracts_v14`` type and is
    ``None`` when its screen degraded / did not run — surfaced honestly in the template, never
    fabricated. The caveats and provenance are un-suppressible module constants echoed onto the
    model so the template renders them structurally.
    """

    scenario: str
    generated_at: str
    poc_bus_name: Optional[str]

    # Core (mandatory) screens — always attempted via the D3 gateway (closed-form fallback).
    study: GridStudyResult

    # Extended (best-effort) advisory screens — None when degraded / not run.
    harmonics: Optional[HarmonicComplianceResult] = None
    ride_through: tuple[RideThroughResult, ...] = ()
    poc_envelope: Optional[PocCapabilityEnvelope] = None
    freq_response: Optional[FreqResponseResult] = None
    curtailment: Optional[CurtailmentShareResult] = None

    # Per-screen degradation notes (screen name → why it did not run), surfaced verbatim.
    degraded_screens: Mapping[str, str] = field(default_factory=dict)

    # Un-suppressible caveats (echoed from module constants for template access).
    mandatory_caveat: str = MANDATORY_SCREENING_CAVEAT
    emt_gap_caveat: str = EMT_GAP_CAVEAT
    tender_evidence: str = TENDER_EVIDENCE_CAVEAT
    verification_discipline: str = VERIFICATION_DISCIPLINE
    synthetic_curtailment_warning: str = SYNTHETIC_CURTAILMENT_WARNING

    # Dependency-reproducibility provenance (CASPER available-vs-degraded state).
    engine_status: tuple[ScreenStatus, ...] = ()
    python_version: str = ""

    @property
    def emt_confirmation_required(self) -> bool:
        """Whether the screened SCR is marginal (< threshold) → EMT confirmation mandated."""
        return bool(self.study.strength.emt_confirmation_required)

    @property
    def emt_confirmation_stamp(self) -> str:
        """The per-SCR EMT-confirmation stamp text (only meaningful when required)."""
        return EMT_CONFIRMATION_STAMP


# ═════════════════════════════════════════════════════════════════════════════
# CASPER engine-availability probe (dependency provenance).
# ═════════════════════════════════════════════════════════════════════════════


def _probe_engine_status() -> tuple[ScreenStatus, ...]:
    """Probe the available-vs-degraded state of each [grid] optional engine (CASPER).

    Uses ``importlib.metadata.version`` (no heavy import of the engine itself) so probing is
    cheap and never triggers the engine's own import-time cost. An absent engine is DEGRADED,
    surfaced honestly — the screen that needs it falls back / does not run, it never crashes.
    """
    statuses: list[ScreenStatus] = []
    for dist, pin in GRID_EXTRA_PINS:
        version: Optional[str] = None
        available = False
        try:
            version = importlib_metadata.version(dist)
            available = True
        except importlib_metadata.PackageNotFoundError:
            available = False
        statuses.append(
            ScreenStatus(
                distribution=dist,
                pin=pin,
                available=available,
                resolved_version=version,
            )
        )
    return tuple(statuses)


# ═════════════════════════════════════════════════════════════════════════════
# Best-effort extended-screen runners. Each CASPER-guards its own optional engine
# + config gap: on any failure it records a degradation note and returns None,
# degrading gracefully rather than crashing the emitter.
# ═════════════════════════════════════════════════════════════════════════════


def _try_harmonics(
    grid: Mapping[str, Any],
    *,
    scr: float,
    plant_rating_mva: float | None,
    poc_voltage_kv: float | None,
    degraded: dict[str, str],
) -> Optional[HarmonicComplianceResult]:
    from analytics.grid.harmonics import screen_harmonics

    try:
        return screen_harmonics(
            grid,
            scr=scr,
            plant_rating_mva=plant_rating_mva,
            poc_voltage_kv=poc_voltage_kv,
            use_pandapower=True,
        )
    except Exception as exc:  # noqa: BLE001 - CASPER: degrade, don't crash the report
        degraded["harmonics"] = (
            f"SCR-coupled harmonics/flicker screen not run: {type(exc).__name__}: {exc}"
        )
        return None


def _try_ride_through(
    grid: Mapping[str, Any], *, degraded: dict[str, str]
) -> tuple[RideThroughResult, ...]:
    from analytics.grid.ride_through import run_ride_through_suite

    try:
        # run_dynamics=False → pure-Python envelope screen (no ANDES); the ANDES dynamic
        # solve is opt-in and heavy, so the default report path stays RMS-envelope only.
        # The RMS envelope is sourced from the D0 grid-code fixture (run_ride_through_suite →
        # envelope_from_fixture), NOT the scenario ``grid`` block — so ``grid`` is deliberately
        # NOT forwarded here. run_ride_through_suite forwards unknown kwargs to
        # run_ride_through_case (which takes no ``grid`` param), so passing ``grid=`` raised
        # TypeError and degraded the whole screen. (``grid`` stays on the signature: reserved
        # for a future grid-derived envelope override.)
        suite = run_ride_through_suite(run_dynamics=False)
        return tuple(suite[k] for k in sorted(suite))
    except Exception as exc:  # noqa: BLE001 - CASPER: degrade, don't crash the report
        degraded["ride_through"] = (
            f"RMS ride-through (LVRT/HVRT/frequency) screen not run: "
            f"{type(exc).__name__}: {exc}"
        )
        return ()


def _try_poc_envelope(
    config: Mapping[str, Any], *, degraded: dict[str, str]
) -> Optional[PocCapabilityEnvelope]:
    from analytics.grid.hybrid.poc_aggregation import aggregate_poc_capability

    try:
        return aggregate_poc_capability(config)
    except Exception as exc:  # noqa: BLE001 - CASPER: degrade, don't crash the report
        degraded["poc_envelope"] = (
            f"Hybrid-POC composite-SCR / aggregate-Q envelope not run "
            f"(single-tech or no resources block): {type(exc).__name__}: {exc}"
        )
        return None


def _try_freq_response(
    config: Mapping[str, Any], *, degraded: dict[str, str]
) -> Optional[FreqResponseResult]:
    from analytics.grid.hybrid.frequency_response import run_hybrid_frequency_response

    try:
        return run_hybrid_frequency_response(config, run_dynamics=False)
    except Exception as exc:  # noqa: BLE001 - CASPER: degrade, don't crash the report
        degraded["freq_response"] = (
            f"Combined frequency-droop (ENPPC) study not run (no ppc block): "
            f"{type(exc).__name__}: {exc}"
        )
        return None


def _try_curtailment(
    config: Mapping[str, Any], *, degraded: dict[str, str]
) -> Optional[CurtailmentShareResult]:
    from analytics.grid.curtailment_qsts import run_qsts_curtailment

    try:
        # The QSTS entry is gated and provenance-typed. #923-E permits a path-backed
        # synthetic/test result to be PRESENTED for counterfactual learning, while the
        # template applies an un-suppressible warning and exposes the machine evidence
        # flags/limitations. Finance still refuses the result at its separate D6b seam.
        return run_qsts_curtailment(config)
    except Exception as exc:  # noqa: BLE001 - CASPER: degrade, don't crash the report
        degraded["curtailment"] = (
            f"QSTS curtailment split not run: {type(exc).__name__}: {exc}"
        )
        return None


# ═════════════════════════════════════════════════════════════════════════════
# Pure builder.
# ═════════════════════════════════════════════════════════════════════════════


def build_grid_screening_model(
    scenario_config: Mapping[str, Any],
    *,
    scenario_variant: str,
    generated_at: str,
    use_pandapower: bool = True,
) -> GridScreeningModel:
    """Compose the available grid screens into a render-ready :class:`GridScreeningModel`.

    Runs the two CORE screens (SCR + reactive) through the CCCDIR gateway
    :func:`analytics.grid.evaluate_grid.evaluate_grid` (which the caller must have gated on
    ``grid.study_enabled``; the gateway raises otherwise — CESSPIT), then attempts each
    EXTENDED advisory screen best-effort: a missing optional engine or a screen-specific config
    gap degrades that screen to ``None`` with a surfaced note (CASPER), never a crash.

    The un-suppressible caveats + the CASPER engine-availability provenance are stamped onto
    the model unconditionally.

    Args:
        scenario_config: the full resolved scenario config (must carry a ``grid`` block with
            ``study_enabled: true``).
        scenario_variant: the report label (scenario stem).
        generated_at: ISO timestamp stamped on the report.
        use_pandapower: forwarded to the gateway/screens; when False (or pandapower absent) the
            screens use their closed-form fallbacks (CASPER).

    Returns:
        The assembled :class:`GridScreeningModel`.

    Raises:
        ValueError: the config has no ``grid`` block or ``grid.study_enabled`` is not True
            (the master default-off gate — the caller opted in, so this is loud; CESSPIT).
    """
    grid = scenario_config.get("grid") if isinstance(scenario_config, Mapping) else None
    if not isinstance(grid, Mapping):
        raise ValueError(
            "grid-screening report needs a top-level 'grid' block; the scenario declares "
            "none. This report emits only for a scenario with an enabled grid study."
        )
    if grid.get("study_enabled") is not True:
        raise ValueError(
            "grid-screening report needs grid.study_enabled: true (the master default-off "
            f"gate); got study_enabled={grid.get('study_enabled')!r}. Enable the study before "
            "opting into the report."
        )

    # Core screens (mandatory) via the gateway — closed-form fallback if pandapower absent.
    study = evaluate_grid(
        scenario_config, use_pandapower=use_pandapower, run_reactive=True
    )

    degraded: dict[str, str] = {}
    scr = float(study.strength.scr)
    plant_rating_mva = study.strength.plant_rating_mva
    poc_voltage_kv = grid.get("poc_voltage_kv")
    poc_voltage_kv_f = (
        float(poc_voltage_kv)
        if isinstance(poc_voltage_kv, (int, float))
        and not isinstance(poc_voltage_kv, bool)
        else None
    )

    harmonics = _try_harmonics(
        grid,
        scr=scr,
        plant_rating_mva=plant_rating_mva,
        poc_voltage_kv=poc_voltage_kv_f,
        degraded=degraded,
    )
    ride_through = _try_ride_through(grid, degraded=degraded)
    poc_envelope = _try_poc_envelope(scenario_config, degraded=degraded)
    freq_response = _try_freq_response(scenario_config, degraded=degraded)
    curtailment = _try_curtailment(scenario_config, degraded=degraded)

    return GridScreeningModel(
        scenario=scenario_variant,
        generated_at=generated_at,
        poc_bus_name=study.poc_bus_name,
        study=study,
        harmonics=harmonics,
        ride_through=ride_through,
        poc_envelope=poc_envelope,
        freq_response=freq_response,
        curtailment=curtailment,
        degraded_screens=degraded,
        engine_status=_probe_engine_status(),
        python_version=platform.python_version(),
    )


# ═════════════════════════════════════════════════════════════════════════════
# Standalone HTML render. Its own Jinja2 template (autoescaped — a site / bus name is
# escaped) so the grid report is a self-contained advisory artifact, separate from the
# finance lender report (correct: it is advisory, bankable=false). The caveat + provenance
# are STRUCTURAL in the template — there is no toggle that removes them.
# ═════════════════════════════════════════════════════════════════════════════

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_TEMPLATE_NAME = "grid_screening.html.j2"


def _fmt(value: Any, *, digits: int = 2, dash: str = "—") -> str:
    """Format a number to ``digits`` decimals, or an em-dash for None (honest not-run)."""
    if value is None:
        return dash
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        return f"{value:,.{digits}f}"
    return str(value)


def _verdict(
    value: Optional[bool], *, ok: str = "within limits", bad: str = "BREACH"
) -> str:
    """Render a tri-state screening verdict: True→ok, False→bad, None→not run (honest)."""
    if value is None:
        return "not run"
    return ok if value else bad


def _environment() -> Environment:
    """Build the Jinja2 environment for the standalone grid-screening template.

    Autoescape is forced on (the ``.j2`` extension would otherwise defeat
    ``select_autoescape``) so any user-supplied value (site / bus name) is HTML-escaped.
    """
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals.update(fmt=_fmt, verdict=_verdict)
    return env


def render_grid_screening_html(model: GridScreeningModel) -> str:
    """Render the grid-screening model to a standalone HTML document string.

    The un-suppressible caveat, EMT-gap, tender evidence, verification discipline and
    dependency provenance are rendered STRUCTURALLY by the template — no toggle omits them.
    """
    template = _environment().get_template(_TEMPLATE_NAME)
    return template.render(m=model)


def emit_grid_screening_report_from_pipeline(
    result: Mapping[str, Any],
    scenario_config_path: str | Path,
    output_html_path: str | Path,
    *,
    use_pandapower: bool = True,
    scenario_variant: Optional[str] = None,
    generated_at: Optional[str] = None,
) -> Path:
    """Render a standalone advisory grid-screening HTML report from a finance run (#884, D8).

    The opt-in production caller wired into ``run_full_pipeline_v14.py``: after a successful
    finance run it composes the available grid screens (:func:`build_grid_screening_model`) and
    writes a standalone advisory HTML report carrying the un-suppressible SCREENING-not-bankable
    + EMT-gap caveat and the dependency / verification provenance.

    The ``result`` finance dict is accepted for signature-parity with the sibling emitters but
    is deliberately NOT consumed for any grid number — the grid study is advisory and never
    reconciles to a finance KPI (the cardinal rule). The heavy screens live ONLY on this batch
    path, never the synchronous HTTP report route (the #645 latency ledger).

    Args:
        result: the finance pipeline result dict (accepted for parity; not used for grid data).
        scenario_config_path: path to the (possibly wind/solar-patched) effective scenario;
            must carry a ``grid`` block with ``study_enabled: true``.
        output_html_path: where to write the rendered HTML report (parents created).
        use_pandapower: forwarded to the screens; False (or pandapower absent) → closed-form.
        scenario_variant: report label; defaults to the scenario file stem.
        generated_at: ISO timestamp stamped on the report; defaults to ``now(UTC)`` (production
            edge — the wall-clock is stamped here, not in the pure builder).

    Returns:
        The path the HTML report was written to.

    Raises:
        ValueError: the scenario has no ``grid`` block or ``grid.study_enabled`` is not True
            (the caller opted in — CESSPIT).
    """
    scenario_dict = dict(load_scenario_config(str(scenario_config_path)))
    variant = scenario_variant or Path(str(scenario_config_path)).stem
    stamp = generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds")

    model = build_grid_screening_model(
        scenario_dict,
        scenario_variant=variant,
        generated_at=stamp,
        use_pandapower=use_pandapower,
    )
    html = render_grid_screening_html(model)

    out_path = Path(output_html_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path

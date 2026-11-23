"""Report presentation configuration (CCCDIR — config-driven, not hardcoded).

Loads ``config/report_defaults.yaml`` into typed Pydantic models. Branding,
covenant thresholds, and the KPI display spec all live in the YAML; this module
only validates and exposes them. No finance logic (Dolphin).
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Literal, Mapping, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field

#: Repo root, resolved relative to this file (app/reports/report_config.py).
_REPO_ROOT = Path(__file__).resolve().parents[2]

#: Committed default presentation config (single source).
DEFAULT_CONFIG_PATH = _REPO_ROOT / "config" / "report_defaults.yaml"

#: How a KPI value is rendered. ``pct`` multiplies by 100 and appends ``%``;
#: ``multiple`` appends ``x``; ``usd`` adds a thousands separator and ``$``.
KpiKind = Literal["pct", "multiple", "usd"]

#: Residual severity of a registered risk AFTER its mitigation — drives badge colour.
RiskSeverity = Literal["low", "medium", "high"]

#: TCFD climate-risk taxonomy for a registered risk. ``physical`` = acute/chronic hazards
#: to the asset (e.g. extreme wind, flooding); ``transition`` = policy/market/technology
#: shifts (e.g. tariff or tax-regime change). Aligns the register with Equator Principles 4's
#: mandatory TCFD-structured Climate Change Risk Assessment (CCRA). Optional — an untagged
#: (absent) risk carries no climate classification, so all existing configs still load.
ClimateRiskCategory = Literal["physical", "transition"]

#: Controlled dynamic-methodology projection. ``fx_path`` replaces only the configured
#: fallback mitigation after the resolved scenario is proven to match the run manifest.
MethodologyKey = Literal["fx_path"]

#: Where a covenant threshold came from (#1668): the scenario's own ``constraints``
#: block, or this file's report-level default when the scenario declares none.
CovenantSource = Literal["scenario", "report_defaults"]

#: Scenario DSCR covenant label when the scenario's lock-up uses that threshold (#1668).
SCENARIO_LOCKUP_COVENANT_NAME = "lock-up covenant"

#: Scenario DSCR covenant label when no lock-up is declared at that threshold (#1900).
SCENARIO_DSCR_COVENANT_NAME = "minimum DSCR covenant"

#: Equity distribution section names recognized by the waterfall engine.
_EQUITY_SECTION_NAMES = ("equity_distribution", "Equity_Distribution", "equity")

#: What the minimum-DSCR threshold is called, by source. A scenario's
#: ``constraints.min_dscr_covenant`` is labeled ``"lock-up covenant"`` only when the
#: scenario declares an active distribution lock-up at that threshold (#1668, #1900);
#: otherwise a scenario-declared threshold is labeled ``"minimum DSCR covenant"``, and
#: this file's default is a presentation floor (``"lender floor"``). The covenant table,
#: the verdict note, and the IC flag all read this naming rule.
DSCR_THRESHOLD_NAME: Dict[CovenantSource, str] = {
    "scenario": SCENARIO_DSCR_COVENANT_NAME,
    "report_defaults": "lender floor",
}


def _scenario_number(value: Any) -> Optional[float]:
    """A declared covenant value as a finite float, or ``None`` (bools are not numbers)."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _lookup_key_as_engine(mapping: Mapping[str, Any], key: str) -> Any:
    """``mapping[key]``, else the first key equal to ``key`` ignoring case, else ``None``.

    The same lookup as the debt engine's ``finance.debt.helpers._lookup_case_insensitive``,
    restated here because the report layer takes no import on the finance package (the
    debt-package boundary lint and the architecture diagram both refuse one). A test pins
    the two to the same answers (#1862).
    """
    if key in mapping:
        return mapping[key]
    key_lower = key.lower()
    for existing_key, value in mapping.items():
        if str(existing_key).lower() == key_lower:
            return value
    return None


def declared_lockup_threshold(
    scenario_config: Optional[Mapping[str, Any]],
) -> Optional[float]:
    """Return the scenario's declared positive lock-up DSCR threshold, or ``None`` (#1900).

    Mirrors ``finance.equity_distribution_v14_hydra._build_distribution_config``'s
    authored-input chain without falling back to the engine's internal 1.25x default:
    returns ``None`` when equity distribution is disabled, when ``min_dscr_threshold``
    is explicitly disabled (``<= 0``) or non-numeric, or when neither
    ``equity_distribution.min_dscr_threshold`` nor ``constraints.min_dscr_covenant``
    declares a positive threshold.
    """
    if not isinstance(scenario_config, Mapping):
        return None
    equity: Mapping[str, Any] = {}
    for section_name in _EQUITY_SECTION_NAMES:
        section = _lookup_key_as_engine(scenario_config, section_name)
        if isinstance(section, Mapping) and section:
            equity = section
            break
    if not bool(equity.get("enabled", True)):
        return None
    if "min_dscr_threshold" in equity and equity.get("min_dscr_threshold") is not None:
        explicit = _scenario_number(equity.get("min_dscr_threshold"))
        return explicit if (explicit is not None and explicit > 0.0) else None
    constraints = _lookup_key_as_engine(scenario_config, "constraints")
    if isinstance(constraints, Mapping):
        covenant = _scenario_number(
            _lookup_key_as_engine(constraints, "min_dscr_covenant")
        )
        if covenant is not None and covenant > 0.0:
            return covenant
    return None


def dscr_threshold_name(source: CovenantSource, *, is_lockup: bool = False) -> str:
    """Return the display name for a minimum-DSCR threshold (#1668, #1900)."""
    if source == "scenario" and is_lockup:
        return SCENARIO_LOCKUP_COVENANT_NAME
    return DSCR_THRESHOLD_NAME[source]


class ReportMeta(BaseModel):
    """Branding / front-matter for the rendered report."""

    model_config = ConfigDict(extra="forbid")

    title: str
    subtitle: str
    organization: str
    version: str
    confidentiality: str
    disclaimer: str


class Covenants(BaseModel):
    """Lender policy thresholds the report flags KPIs against."""

    model_config = ConfigDict(extra="forbid")

    min_dscr_floor: float
    min_dscr_target: float
    max_balloon_pct: float
    #: Set by the report from the scenario (#1668); the YAML defaults leave both
    #: as ``report_defaults``.
    min_dscr_floor_source: CovenantSource = "report_defaults"
    #: True only when the scenario declares an active lock-up at ``min_dscr_floor`` (#1900).
    min_dscr_floor_is_lockup: bool = False
    max_balloon_pct_source: CovenantSource = "report_defaults"

    @property
    def min_dscr_floor_name(self) -> str:
        """The minimum-DSCR threshold's name for its source and lock-up status (#1668, #1900)."""
        return dscr_threshold_name(
            self.min_dscr_floor_source, is_lockup=self.min_dscr_floor_is_lockup
        )


class KpiSpec(BaseModel):
    """One row of the KPI display table: which KPI, its label, and formatting."""

    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    kind: KpiKind


class RiskItem(BaseModel):
    """One row of the lender risk register: a project risk, its mitigation, and the
    RESIDUAL severity after that mitigation. Config-authored (CCCDIR) — the report layer
    renders these; it does not derive them."""

    model_config = ConfigDict(extra="forbid")

    category: str
    risk: str
    mitigation: str
    severity: RiskSeverity
    # TCFD/EP4 climate-risk classification (physical | transition). Optional: absent = the
    # risk is not climate-classified (extra="forbid" preserved), so every existing config
    # still validates. Additive presentation only — moves no computed number.
    climate_risk_category: Optional[ClimateRiskCategory] = None
    # Optional dynamic methodology selector. Absent means faithful config passthrough;
    # ``fx_path`` is resolved only from a manifest-matched scenario in report_model.
    methodology_key: Optional[MethodologyKey] = None


class LimitationItem(BaseModel):
    """One model-limitation / scope caveat rendered in every report (#734).

    Config-authored (CCCDIR) so no output is read without its scope caveats; the report layer
    renders these verbatim and derives none. This is the one report-wide home for caveats that
    otherwise lived only as module docstrings / result-notes (e.g. the BESS-LCOS 'dispatch is not
    simulated' note in finance.bess_lcos, the three-statement tax/100%-sweep/equity-balancing note
    in analytics.three_statement) — surfaced, not duplicated."""

    model_config = ConfigDict(extra="forbid")

    topic: str
    detail: str


class ReportConfig(BaseModel):
    """The full validated report presentation config."""

    model_config = ConfigDict(extra="forbid")

    report: ReportMeta
    covenants: Covenants
    kpi_table: List[KpiSpec]
    # Optional so a minimal/legacy config (or a test fixture) without a register still
    # validates; the committed default seeds the real DutchBay risk profile.
    risk_register: List[RiskItem] = Field(default_factory=list)
    # Optional so a minimal/legacy config (or a test fixture) without limitations still validates;
    # the committed default seeds the model-wide scope caveats (#734).
    model_limitations: List[LimitationItem] = Field(default_factory=list)


def load_report_config(path: Optional[Path] = None) -> ReportConfig:
    """Load and validate the report presentation config.

    Args:
        path: Optional override path to a YAML config. Defaults to the committed
            ``config/report_defaults.yaml``.

    Returns:
        The validated :class:`ReportConfig`.

    Raises:
        FileNotFoundError: The config file does not exist.
        pydantic.ValidationError: The YAML is missing required keys or has
            unknown ones (``extra="forbid"``).
    """
    cfg_path = path if path is not None else DEFAULT_CONFIG_PATH
    with open(cfg_path, "r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    return ReportConfig.model_validate(raw)

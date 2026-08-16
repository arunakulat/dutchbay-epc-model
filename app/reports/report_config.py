"""Report presentation configuration (CCCDIR — config-driven, not hardcoded).

Loads ``config/report_defaults.yaml`` into typed Pydantic models. Branding,
covenant thresholds, and the KPI display spec all live in the YAML; this module
only validates and exposes them. No finance logic (Dolphin).
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Literal, Optional

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

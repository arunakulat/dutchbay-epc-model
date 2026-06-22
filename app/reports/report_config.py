"""Report presentation configuration (CCCDIR — config-driven, not hardcoded).

Loads ``config/report_defaults.yaml`` into typed Pydantic models. Branding,
covenant thresholds, and the KPI display spec all live in the YAML; this module
only validates and exposes them. No finance logic (Dolphin).
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict

#: Repo root, resolved relative to this file (app/reports/report_config.py).
_REPO_ROOT = Path(__file__).resolve().parents[2]

#: Committed default presentation config (single source).
DEFAULT_CONFIG_PATH = _REPO_ROOT / "config" / "report_defaults.yaml"

#: How a KPI value is rendered. ``pct`` multiplies by 100 and appends ``%``;
#: ``multiple`` appends ``x``; ``usd`` adds a thousands separator and ``$``.
KpiKind = Literal["pct", "multiple", "usd"]


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


class ReportConfig(BaseModel):
    """The full validated report presentation config."""

    model_config = ConfigDict(extra="forbid")

    report: ReportMeta
    covenants: Covenants
    kpi_table: List[KpiSpec]


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

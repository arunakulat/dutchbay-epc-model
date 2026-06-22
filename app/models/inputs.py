"""Customer-facing wizard input model — the form → scenario bridge.

``WindFarmInputs`` is the friendly, validated surface a multi-step wizard
submits. ``to_scenario_config()`` loads a committed base scenario variant and
deep-merges the mapped form fields into it, producing a full v14 scenario dict
that the service seam (``app.services.run_finance_case``) runs.

This is a **mapping** layer only — it contains no finance logic (Dolphin). It
maps friendly field names onto the canonical scenario paths and inherits
everything else from the chosen base variant (CCCDIR: the variant→path table is
the single source, no scattered scenario paths).

Note: the synchronous path keeps the base variant's frozen ``aep_summary`` — the
form's capacity/CF edits tweak the finance inputs but do not re-derive AEP. Use
the asynchronous live-ERA5 path (roadmap Sprint 2) when AEP must be recomputed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from analytics.scenario_loader import load_scenario_config

ScenarioVariant = Literal["lendercase", "basecase", "equitycase"]

#: Friendly variant name → committed base scenario file (single source).
_VARIANT_SCENARIOS: Dict[ScenarioVariant, str] = {
    "lendercase": "scenarios/dutchbay_lendercase_2025Q4.yaml",
    "basecase": "scenarios/dutchbay_basecase_2025Q4.yaml",
    "equitycase": "scenarios/dutchbay_equitycase_2025Q4.yaml",
}

#: Repo root, resolved relative to this file (app/models/inputs.py → parents[2]).
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _deep_merge(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge ``overrides`` into a copy of ``base`` (overrides win).

    Generic nested-dict merge mirroring the engine's override semantics: nested
    dicts recurse; scalars and lists are replaced. Not finance logic.
    """
    out: Dict[str, Any] = dict(base)
    for key, value in overrides.items():
        existing = out.get(key)
        if isinstance(value, dict) and isinstance(existing, dict):
            out[key] = _deep_merge(existing, value)
        else:
            out[key] = value
    return out


class WindFarmInputs(BaseModel):
    """One multi-step wizard submission, validated and mapped to a v14 scenario.

    Only the fields a client edits are exposed; everything else is inherited from
    the chosen ``scenario_variant`` base. Validation mirrors the engine's physical
    constraints (capacity > 0, capacity factor in (0, 1], life 1–60 years, …).
    Unknown fields are rejected (CESSPIT).
    """

    model_config = ConfigDict(extra="forbid")

    scenario_variant: ScenarioVariant = "lendercase"

    # Site / project
    site_name: str = Field(..., min_length=1)
    location: Optional[str] = None
    capacity_mw: float = Field(..., gt=0)
    capacity_factor: float = Field(..., gt=0, le=1)
    project_life_years: int = Field(..., ge=1, le=60)
    cod_year: Optional[int] = Field(None, ge=2000, le=2100)
    num_turbines: Optional[int] = Field(None, gt=0)
    hub_height_m: Optional[float] = Field(None, gt=0)

    # Commercial / finance
    ppa_price_lkr_per_kwh: float = Field(..., gt=0)
    ppa_term_years: int = Field(..., ge=1, le=40)
    capex_total_usd: float = Field(..., gt=0)
    opex_annual_usd: float = Field(..., ge=0)
    fx_start_lkr_per_usd: float = Field(..., gt=0)

    # Optional debt knobs (inherited from the variant when omitted)
    debt_ratio: Optional[float] = Field(None, ge=0, le=1)
    target_dscr: Optional[float] = Field(None, gt=0)

    def to_overrides(self) -> Dict[str, Any]:
        """Build the nested scenario-override dict from the set fields."""
        project: Dict[str, Any] = {
            "name": self.site_name,
            "capacity_mw": self.capacity_mw,
            "capacity_factor": self.capacity_factor,
            "life_years": self.project_life_years,
        }
        if self.location is not None:
            project["location"] = self.location
        if self.cod_year is not None:
            project["cod_year"] = self.cod_year

        turbine: Dict[str, Any] = {"total_capacity_mw": self.capacity_mw}
        if self.num_turbines is not None:
            turbine["n_turbines"] = self.num_turbines
        if self.hub_height_m is not None:
            turbine["hub_height_m"] = self.hub_height_m

        financing: Dict[str, Any] = {}
        if self.debt_ratio is not None:
            financing["debt_ratio"] = self.debt_ratio
        if self.target_dscr is not None:
            financing["target_dscr"] = self.target_dscr

        overrides: Dict[str, Any] = {
            "project": project,
            "turbine": turbine,
            "capex": {"usd_total": self.capex_total_usd},
            "opex": {"usd_per_year": self.opex_annual_usd},
            "tariff": {
                "lkr_per_kwh": self.ppa_price_lkr_per_kwh,
                "ppa_term_years": self.ppa_term_years,
            },
            "fx": {"start_lkr_per_usd": self.fx_start_lkr_per_usd},
        }
        if financing:
            overrides["Financing_Terms"] = financing
        return overrides

    def base_scenario_path(self, repo_root: Optional[Path] = None) -> Path:
        """Resolve the committed base scenario file for this variant."""
        root = repo_root if repo_root is not None else _REPO_ROOT
        return root / _VARIANT_SCENARIOS[self.scenario_variant]

    def to_scenario_config(self, repo_root: Optional[Path] = None) -> Dict[str, Any]:
        """Load the base variant and merge the form fields → full scenario dict.

        The returned dict is a ready-to-run v14 scenario suitable for
        ``app.services.run_finance_case``.
        """
        base = dict(load_scenario_config(str(self.base_scenario_path(repo_root))))
        return _deep_merge(base, self.to_overrides())

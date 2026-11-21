"""Report sections for the site analyses (#1824).

One section per site analysis (:data:`analytics.site_analysis_blocks.SITE_ANALYSIS_BLOCKS`) and
one for the wind resource transfer those analyses read. :func:`build_site_analyses_block` gives
every section a status:

- ``completed``: the analysis ran live, or its committed summary matches the tree;
- ``stale``: the committed summary no longer matches the code or the inputs it was written
  from. Its figures are shown under the reasons, so a reader sees both;
- ``not_run``: the scenario declares the block but no summary has been committed for it;
- ``failed``: the analysis raised. The reason is listed and the report still renders (#1760
  "write figures, list failure");
- ``not_applicable``: the scenario declares no block for it.

The FX and tenor screening and the equipment cost parity run live, on the run's effective
scenario. The wind battery options and the PV + BESS sizing are read from their committed
summaries (:mod:`analytics.site_analysis_runs`). Titles and screening labels come from
``conf/site_analysis_sections.yaml``; every figure comes from the scenario and the analyses.
Nothing here names a site or holds a figure (``ARCH-01``).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import yaml
from pydantic import BaseModel, ConfigDict, Field

from analytics.site_analysis_blocks import (
    SITE_ANALYSIS_BLOCKS,
    resolve_site_analysis_block,
)
from analytics.site_analysis_runs import (
    MODE_LIVE,
    REPO_ROOT,
    SITE_ANALYSIS_RUNS,
    load_summary,
    method_config_path,
    provenance,
    run_site_analysis,
    stale_reasons,
    summary_path,
)

SECTIONS_CONFIG = Path("conf") / "site_analysis_sections.yaml"
SECTIONS_SCHEMA = "site_analysis_sections_v1"

#: The wind resource section's key, ahead of the four analyses.
WIND_RESOURCE_TRANSFER = "wind_resource_transfer"

#: Every section, in report order.
SECTION_KEYS: Tuple[str, ...] = (WIND_RESOURCE_TRANSFER, *SITE_ANALYSIS_BLOCKS)

STATUS_COMPLETED = "completed"
STATUS_STALE = "stale"
STATUS_NOT_RUN = "not_run"
STATUS_FAILED = "failed"
STATUS_NOT_APPLICABLE = "not_applicable"


class SiteAnalysisTable(BaseModel):
    """A small table of pre-formatted cells."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    caption: str
    columns: List[str]
    rows: List[List[str]] = Field(default_factory=list)


class SiteAnalysisSection(BaseModel):
    """One analysis's section: its status, labels, figures and where they came from."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    title: str
    status: str
    reason: Optional[str] = None
    stale_reasons: List[str] = Field(default_factory=list)
    labels: List[str] = Field(default_factory=list)
    hold: Optional[str] = None
    notes: Optional[str] = None
    site: Optional[str] = None
    figures: List[Tuple[str, str]] = Field(default_factory=list)
    tables: List[SiteAnalysisTable] = Field(default_factory=list)
    source: Optional[str] = None
    provenance: Optional[str] = None


class SiteAnalysesBlock(BaseModel):
    """Every site-analysis section of one report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intro: str
    sections: List[SiteAnalysisSection]

    @property
    def shown(self) -> List[SiteAnalysisSection]:
        """The sections that apply to the scenario."""
        return [s for s in self.sections if s.status != STATUS_NOT_APPLICABLE]

    @property
    def not_applicable(self) -> List[SiteAnalysisSection]:
        """The sections whose block the scenario does not declare."""
        return [s for s in self.sections if s.status == STATUS_NOT_APPLICABLE]


# --------------------------------------------------------------------------- formatting


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _pct(value: Any, digits: int = 2) -> str:
    f = _num(value)
    return "n/a" if f is None else f"{f * 100:.{digits}f}%"


def _pct_points(value: Any, digits: int = 2) -> str:
    f = _num(value)
    return "n/a" if f is None else f"{f:.{digits}f}%"


def _usd(value: Any) -> str:
    f = _num(value)
    return "n/a" if f is None else f"USD {f:,.0f}"


def _ratio(value: Any, digits: int = 2) -> str:
    f = _num(value)
    return "n/a" if f is None else f"{f:.{digits}f}"


def _plain(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    f = _num(value)
    if f is not None and not isinstance(value, str):
        return f"{f:,.4g}"
    return str(value)


def _get(data: Any, *path: str) -> Any:
    for key in path:
        if not isinstance(data, Mapping):
            return None
        data = data.get(key)
    return data


def _site(result: Mapping[str, Any]) -> Optional[str]:
    site = result.get("site")
    if not isinstance(site, Mapping):
        return None
    parts = [str(site[k]) for k in ("name", "location") if site.get(k)]
    return ", ".join(parts) or None


def _provenance_text(prov: Any, mode: str) -> Optional[str]:
    if not isinstance(prov, Mapping):
        return None
    code = _get(prov, "code", "tree")
    config = _get(prov, "config", "tree")
    how = "run live in this report" if mode == MODE_LIVE else "committed summary"
    return (
        f"{how}; code {str(code)[:12]}, config {str(config)[:12]}, "
        f"model version {prov.get('model_version')}"
    )


# --------------------------------------------------------------------------- figures


def _figures_storage_options(
    result: Mapping[str, Any],
) -> Tuple[List[Tuple[str, str]], List[SiteAnalysisTable]]:
    wind_only = result.get("wind_only") or {}
    base = _get(result, "revenue_bases", "base")
    figures = [
        ("Wind only: project IRR", _pct(wind_only.get("project_irr"))),
        ("Wind only: equity IRR", _pct(wind_only.get("equity_irr"))),
        ("Wind only: project NPV", _usd(wind_only.get("project_npv"))),
        ("Revenue basis for the options", _plain(base)),
        (
            "Recommended option (reading A)",
            _plain(result.get("recommended_option_reading_A")),
        ),
    ]
    options = result.get("options") or {}
    readings = sorted(
        {r for opt in options.values() for r in (opt.get("readings") or {})}
    )
    columns = ["Option", "Operation", "Power (MW)", "Energy (MWh)", "Fits reading A"]
    for r in readings:
        columns += [f"Project IRR, reading {r}", f"Project NPV change, reading {r}"]
    rows: List[List[str]] = []
    for name in sorted(options):
        opt = options[name]
        row = [
            name,
            _plain(opt.get("operation")),
            _plain(opt.get("power_mw")),
            _plain(opt.get("energy_mwh")),
            _plain(opt.get("fits_reading_A_turbine_plus_battery_le_limit")),
        ]
        for r in readings:
            kpis = _get(opt, "readings", r, "bases", base) or {}
            row += [
                _pct(kpis.get("project_irr")),
                _usd(kpis.get("delta_project_npv_vs_wind_only")),
            ]
        rows.append(row)
    tables = [
        SiteAnalysisTable(
            caption=f"Battery options on the {base} revenue basis, against wind only",
            columns=columns,
            rows=rows,
        )
    ]
    return figures, tables


def _figures_equipment_cost_parity(
    result: Mapping[str, Any],
) -> Tuple[List[Tuple[str, str]], List[SiteAnalysisTable]]:
    res = _get(result, "equipment_parity", "results") or {}
    figures = [
        ("Benchmark project", _plain(result.get("benchmark_name"))),
        (
            "Benchmark equipment cost",
            f"{_usd(res.get('benchmark_equipment_usd_per_kw'))} per kW",
        ),
        (
            "Benchmark capacity factor",
            _pct_points(res.get("benchmark_capacity_factor_pct")),
        ),
        ("Site capacity factor", _pct_points(res.get("site_capacity_factor_pct"))),
        (
            "Site to benchmark yield per MW",
            _ratio(res.get("site_to_benchmark_yield_per_mw_ratio"), 3),
        ),
        (
            "Break-even equipment price premium per MW",
            _pct_points(res.get("break_even_equipment_price_per_mw_premium_pct")),
        ),
        (
            "Calculation basis",
            _plain(_get(result, "equipment_parity", "calculation_basis")),
        ),
    ]
    routes = result.get("cost_buildup") or {}
    rows = [
        [
            str(route),
            _plain(ev.get("status")),
            _plain(ev.get("applicable_package_count")),
            str(len(ev.get("unpriced_required_package_ids") or [])),
            _usd(ev.get("total_usd")),
        ]
        for route, ev in sorted(routes.items())
        if isinstance(ev, Mapping)
    ]
    tables = [
        SiteAnalysisTable(
            caption="Cost build-up by delivery route",
            columns=[
                "Route",
                "Status",
                "Packages",
                "Unpriced required packages",
                "Total",
            ],
            rows=rows,
        )
    ]
    return figures, tables


def _dscr_row(name: str, case: Any) -> List[str]:
    case = case if isinstance(case, Mapping) else {}
    return [
        name,
        _ratio(_get(case, "p50", "min_dscr")),
        _ratio(_get(case, "p50", "average_dscr")),
        _ratio(_get(case, "assumed_downside", "min_dscr")),
        _pct(case.get("gearing_decimal")),
        _usd(case.get("debt_usd")),
    ]


def _figures_financing_screening(
    result: Mapping[str, Any],
) -> Tuple[List[Tuple[str, str]], List[SiteAnalysisTable]]:
    rows = [_dscr_row("Base case", result.get("base_case"))]
    for name, case in sorted((result.get("tenor_variants") or {}).items()):
        rows.append(_dscr_row(f"Tenor variant: {name}", case))
    for name, case in sorted((result.get("sensitivities") or {}).items()):
        rows.append(_dscr_row(f"Sensitivity: {name}", case))
    figures = [
        ("Engine path", _plain(result.get("engine_path_status"))),
        ("Generation basis", _plain(result.get("generation_basis_note"))),
    ]
    tables = [
        SiteAnalysisTable(
            caption="Annual DSCR screening by case (screening indicators only)",
            columns=[
                "Case",
                "Minimum DSCR, P50",
                "Average DSCR, P50",
                "Minimum DSCR, assumed downside",
                "Gearing",
                "Debt",
            ],
            rows=rows,
        )
    ]
    return figures, tables


def _figures_solar_storage_sizing(
    result: Mapping[str, Any],
) -> Tuple[List[Tuple[str, str]], List[SiteAnalysisTable]]:
    rec = result.get("recommendation")
    figures: List[Tuple[str, str]] = []
    if isinstance(rec, Mapping):
        for key in sorted(rec):
            value = rec[key]
            if not isinstance(value, (Mapping, list)):
                figures.append((f"Recommendation: {key}", _plain(value)))
    return figures, []


def _figures_wind_resource_transfer(
    result: Mapping[str, Any],
) -> Tuple[List[Tuple[str, str]], List[SiteAnalysisTable]]:
    yld = result.get("yield")
    if not isinstance(yld, Mapping) or _num(yld.get("net_aep_gwh")) is None:
        raise ValueError("the transfer summary carries no yield.net_aep_gwh")
    figures = [
        ("Net AEP, P50 (screening)", f"{_num(yld.get('net_aep_gwh')):.2f} GWh a year"),
        ("Net capacity factor (screening)", _pct(yld.get("net_capacity_factor"))),
        ("Total losses", _pct_points(yld.get("total_loss_pct"))),
        ("Basis", _plain(yld.get("basis"))),
    ]
    return figures, []


FigureBuilder = Callable[
    [Mapping[str, Any]], Tuple[List[Tuple[str, str]], List[SiteAnalysisTable]]
]

_FIGURES: Dict[str, FigureBuilder] = {
    WIND_RESOURCE_TRANSFER: _figures_wind_resource_transfer,
    "storage_options": _figures_storage_options,
    "solar_storage_sizing": _figures_solar_storage_sizing,
    "financing_screening": _figures_financing_screening,
    "equipment_cost_parity": _figures_equipment_cost_parity,
}


# --------------------------------------------------------------------------- sections


def load_sections_config(root: Path = REPO_ROOT) -> Dict[str, Any]:
    """Read and check ``conf/site_analysis_sections.yaml``."""
    raw = yaml.safe_load((root / SECTIONS_CONFIG).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != SECTIONS_SCHEMA:
        raise ValueError(f"{SECTIONS_CONFIG} must declare {SECTIONS_SCHEMA}")
    sections = raw.get("sections")
    if not isinstance(sections, dict) or set(sections) != set(SECTION_KEYS):
        raise ValueError(f"{SECTIONS_CONFIG} must hold exactly {list(SECTION_KEYS)}")
    for key, entry in sections.items():
        if not isinstance(entry, dict) or not isinstance(entry.get("title"), str):
            raise ValueError(f"{SECTIONS_CONFIG}: sections.{key} needs a title")
        labels = entry.get("labels", [])
        if not isinstance(labels, list) or not all(isinstance(x, str) for x in labels):
            raise ValueError(f"{SECTIONS_CONFIG}: sections.{key}.labels must be text")
    return raw


def _section(
    key: str, entry: Mapping[str, Any], status: str, **fields: Any
) -> SiteAnalysisSection:
    shows_results = status in (STATUS_COMPLETED, STATUS_STALE)
    return SiteAnalysisSection(
        key=key,
        title=str(entry["title"]),
        status=status,
        labels=list(entry.get("labels", [])) if shows_results else [],
        **fields,
    )


def _with_results(
    key: str,
    entry: Mapping[str, Any],
    status: str,
    result: Mapping[str, Any],
    *,
    mode: str,
    source: Optional[str],
    reasons: Sequence[str] = (),
) -> SiteAnalysisSection:
    figures, tables = _FIGURES[key](result)
    hold = result.get("hold") or result.get("hold_caveat")
    if key == "equipment_cost_parity":
        hold = _get(result, "equipment_parity", "site_aep_hold_status") or hold
    return _section(
        key,
        entry,
        status,
        stale_reasons=list(reasons),
        hold=str(hold) if hold else None,
        notes=str(result["notes"]) if result.get("notes") else None,
        site=_site(result),
        figures=figures,
        tables=tables,
        source=source,
        provenance=_provenance_text(result.get("provenance"), mode),
    )


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _analysis_section(
    block: str,
    entry: Mapping[str, Any],
    scenario: Mapping[str, Any],
    scenario_path: Path,
    root: Path,
) -> SiteAnalysisSection:
    block_value = resolve_site_analysis_block(scenario, block)
    if block_value is None:
        return _section(
            block,
            entry,
            STATUS_NOT_APPLICABLE,
            reason=f"the scenario declares no {block} block",
        )
    spec = SITE_ANALYSIS_RUNS[block]
    if spec.mode == MODE_LIVE:
        result = run_site_analysis(block, scenario, scenario_path, root=root)
        return _with_results(
            block,
            entry,
            STATUS_COMPLETED,
            result,
            mode=spec.mode,
            source=method_config_path(block, block_value),
        )
    target = summary_path(scenario_path, block, root=root)
    summary = load_summary(target)
    if summary is None:
        return _section(
            block,
            entry,
            STATUS_NOT_RUN,
            reason=(
                f"no committed summary at {_rel(target, root)}; write it with "
                f"scripts/run_site_analysis_v14.py analysis={block} "
                f"scenario={_rel(scenario_path, root)} write=true"
            ),
        )
    current = provenance(block, block_value, scenario_path, root=root)
    reasons = stale_reasons(summary.get("provenance"), current)
    return _with_results(
        block,
        entry,
        STATUS_STALE if reasons else STATUS_COMPLETED,
        summary,
        mode=spec.mode,
        source=_rel(target, root),
        reasons=reasons,
    )


def _transfer_section(
    entry: Mapping[str, Any], scenario: Mapping[str, Any], root: Path
) -> SiteAnalysisSection:
    key = WIND_RESOURCE_TRANSFER
    named: Optional[str] = None
    for dotted in entry.get("named_by", []):
        value = _get(scenario, *str(dotted).split("."))
        if isinstance(value, str) and value:
            named = value
            break
    if named is None:
        return _section(
            key,
            entry,
            STATUS_NOT_APPLICABLE,
            reason="no block of the scenario names a wind resource transfer summary",
        )
    path = root / named
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError(f"{named} must hold a JSON object")
    return _with_results(
        key,
        entry,
        STATUS_COMPLETED,
        data,
        mode="input",
        source=named,
    )


def build_site_analyses_block(
    scenario: Mapping[str, Any],
    scenario_path: Path,
    *,
    root: Path = REPO_ROOT,
) -> Optional[SiteAnalysesBlock]:
    """Build every site-analysis section for one scenario.

    Returns ``None`` when the scenario declares none of the site-analysis blocks, so a report
    for such a scenario is unchanged. Otherwise every section is listed: an analysis that
    raises is listed as ``failed`` with its reason, and the others still render.

    Args:
        scenario: The run's effective scenario mapping.
        scenario_path: The scenario's file, absolute or relative to ``root``. It locates the
            committed summaries and enters their config digest.
        root: The repository root.

    Raises:
        ValueError: ``conf/site_analysis_sections.yaml`` is malformed.
    """
    if not any(resolve_site_analysis_block(scenario, b) for b in SITE_ANALYSIS_BLOCKS):
        return None
    cfg = load_sections_config(root)
    path = Path(scenario_path)
    if not path.is_absolute():
        path = root / path
    sections: List[SiteAnalysisSection] = []
    for key in SECTION_KEYS:
        entry = cfg["sections"][key]
        try:
            if key == WIND_RESOURCE_TRANSFER:
                sections.append(_transfer_section(entry, scenario, root))
            else:
                sections.append(_analysis_section(key, entry, scenario, path, root))
        except Exception as exc:  # noqa: BLE001 - listed with its reason, never silent
            sections.append(
                _section(
                    key,
                    entry,
                    STATUS_FAILED,
                    reason=f"{type(exc).__name__}: {exc}",
                )
            )
    return SiteAnalysesBlock(intro=str(cfg.get("intro", "")).strip(), sections=sections)


__all__ = [
    "SECTION_KEYS",
    "STATUS_COMPLETED",
    "STATUS_FAILED",
    "STATUS_NOT_APPLICABLE",
    "STATUS_NOT_RUN",
    "STATUS_STALE",
    "SiteAnalysesBlock",
    "SiteAnalysisSection",
    "SiteAnalysisTable",
    "WIND_RESOURCE_TRANSFER",
    "build_site_analyses_block",
    "load_sections_config",
]

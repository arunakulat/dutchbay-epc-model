"""Opt-in what-if cases (#1403/#1523) and CASPER lender-risk blocks (#1825 slice iv).

Two surfaces feed this section of the command-line lender report:

* **What-if cases (#1403 with #1523 caveats)**: loads non-canonical ``what_if_case`` YAML
  files (default ``scenarios/what_if/*.yaml``), runs those whose ``base_scenario`` matches
  the report's scenario through :func:`analytics.what_if_cases.run_what_if_case`, and
  surfaces the base-vs-case KPI deltas alongside each case's ``source``, per-parameter
  ``provenance``, and ``limitations`` verbatim (#1523).
* **CASPER lender-risk blocks (FRAMEWORK-01)**: runs
  :func:`analytics.mc.exports.build_casper_risk_blocks` over a lender-grade canonical
  Monte Carlo result guarded by :mod:`app.reports.capital_risk_emit` (at least
  :data:`~app.reports.capital_risk_emit.LENDER_GRADE_MIN_TRIALS` trials,
  ``monte_carlo.allow_toy_fallback`` forced off, and zero toy-fallback trials permitted).

What the section is, and is not:

* Beside the committed case, never a replacement for it. Every committed figure and KPI is
  unchanged.
* Universal (#1760 / CASPER / FRAMEWORK-01): every input comes from the scenario or the
  declared case files. Any part that does not apply or cannot run is listed explicitly with
  its reason, while misconfigured opt-in settings fail closed.

GWTF:
    - FRAMEWORK-01: explicit reason when a part does not apply; no fabricated defaults.
    - FRAMEWORK-03: one seam; ``report_model`` holds the typed blocks, this module builds
      them.
    - CESSPIT: strict settings validation and lender Monte Carlo guards.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from analytics.contracts_v14 import MonteCarloResult
from analytics.mc.covenant import resolve_min_dscr_covenant
from analytics.mc.exports import CovenantSpec, build_casper_risk_blocks
from analytics.what_if_cases import WhatIfCase, load_what_if_case, run_what_if_case
from app.reports.capital_risk_emit import (
    LENDER_GRADE_MIN_TRIALS,
    run_lender_grade_monte_carlo,
)
from app.reports.report_model import (
    CasperCovenantSummary,
    CasperLenderRiskBlock,
    CasperLenderRiskRow,
    WhatIfCaseBlock,
    WhatIfKpiRow,
    WhatIfLenderRiskBlock,
    WhatIfParameterSummary,
    WhatIfVariantBlock,
)

__all__ = [
    "DEFAULT_WHAT_IF_LENDER_RISK_SETTINGS",
    "SECTION_WHAT_IF_LENDER_RISK",
    "WhatIfLenderRiskSettings",
    "build_what_if_lender_risk_section",
    "settings_from_config",
]

#: The section's name in the report's "sections not run" list.
SECTION_WHAT_IF_LENDER_RISK = "What-if cases and lender risk"

_PREFIX = "lender_report.what_if_lender_risk"
_DEFAULT_WHAT_IF_DIR = "scenarios/what_if"
_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]

#: Human labels and display units for #1403 what-if KPIs.
_KPI_DISPLAY_SPEC: Dict[str, Tuple[str, str]] = {
    "project_irr": ("Project IRR", "pct"),
    "equity_irr": ("Equity IRR", "pct"),
    "irr": ("Project IRR", "pct"),
    "project_npv": ("Project NPV", "usd"),
    "equity_npv": ("Equity NPV", "usd"),
    "npv": ("NPV", "usd"),
    "total_idc_usd": ("Total IDC", "usd"),
    "max_debt_usd": ("Max debt", "usd"),
    "total_cfads_usd": ("Total CFADS", "usd"),
    "min_dscr": ("Minimum DSCR", "ratio"),
    "avg_dscr": ("Average DSCR", "ratio"),
    "llcr": ("LLCR", "ratio"),
    "plcr": ("PLCR", "ratio"),
}

_FLOOR_PINNED_DISCLOSURE = (
    "Dual-DSCR debt sculpting pins per-trial minimum DSCR at the covenant floor, so "
    "Prob(DSCR < floor) is a structural 0.0% with no distributional signal (#725). Read "
    "lender tail risk from LLCR, PLCR, and Project NPV."
)


@dataclass(frozen=True)
class WhatIfLenderRiskSettings:
    """Analysis settings for ``lender_report.what_if_lender_risk`` (CESSPIT)."""

    enabled: bool = False
    what_if_dir: Optional[str] = _DEFAULT_WHAT_IF_DIR
    case_files: Optional[Tuple[str, ...]] = None
    mc_trials: int = LENDER_GRADE_MIN_TRIALS
    mc_seed: Optional[int] = None


#: Off by default (#1825: each analytics section is opt-in under emit_all).
DEFAULT_WHAT_IF_LENDER_RISK_SETTINGS = WhatIfLenderRiskSettings()


def _require_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer; got {value!r}")
    return int(value)


def settings_from_config(
    raw: Optional[Mapping[str, Any]],
) -> WhatIfLenderRiskSettings:
    """Read and strictly validate ``lender_report.what_if_lender_risk``.

    Raises:
        ValueError: On unknown keys, non-boolean ``enabled``, invalid paths, or an MC
            trial count below :data:`LENDER_GRADE_MIN_TRIALS`.
    """
    if raw is None:
        return DEFAULT_WHAT_IF_LENDER_RISK_SETTINGS
    if not isinstance(raw, Mapping):
        raise ValueError(f"{_PREFIX} must be a mapping")
    known = {"enabled", "what_if_dir", "case_files", "mc"}
    unknown = sorted(set(raw) - known)
    if unknown:
        raise ValueError(f"{_PREFIX}: unknown key(s) {unknown}")

    enabled = raw.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ValueError(f"{_PREFIX}.enabled must be a boolean; got {enabled!r}")

    if "what_if_dir" in raw:
        raw_dir = raw["what_if_dir"]
        if raw_dir is None:
            what_if_dir: Optional[str] = None
        elif not isinstance(raw_dir, str) or not raw_dir.strip():
            raise ValueError(
                f"{_PREFIX}.what_if_dir must be a non-empty string or null"
            )
        else:
            what_if_dir = raw_dir.strip()
    else:
        what_if_dir = _DEFAULT_WHAT_IF_DIR

    case_files: Optional[Tuple[str, ...]] = None
    if "case_files" in raw and raw["case_files"] is not None:
        raw_files = raw["case_files"]
        if (
            not isinstance(raw_files, Sequence)
            or isinstance(raw_files, (str, bytes))
            or not raw_files
            or not all(isinstance(p, str) and p.strip() for p in raw_files)
        ):
            raise ValueError(
                f"{_PREFIX}.case_files must be a non-empty list of file paths"
            )
        case_files = tuple(p.strip() for p in raw_files)

    mc_raw = raw.get("mc")
    if mc_raw is None:
        mc: Mapping[str, Any] = {}
    elif not isinstance(mc_raw, Mapping) or set(mc_raw) - {"trials", "seed"}:
        raise ValueError(f"{_PREFIX}.mc takes only trials and seed")
    else:
        mc = mc_raw

    trials = _require_int(
        mc.get("trials", LENDER_GRADE_MIN_TRIALS), f"{_PREFIX}.mc.trials"
    )
    if trials < LENDER_GRADE_MIN_TRIALS:
        raise ValueError(
            f"{_PREFIX}.mc.trials must be at least {LENDER_GRADE_MIN_TRIALS} "
            f"(the lender-grade floor), not {trials}"
        )

    seed_raw = mc.get("seed", None)
    seed: Optional[int] = (
        None if seed_raw is None else _require_int(seed_raw, f"{_PREFIX}.mc.seed")
    )

    return WhatIfLenderRiskSettings(
        enabled=enabled,
        what_if_dir=what_if_dir,
        case_files=case_files,
        mc_trials=trials,
        mc_seed=seed,
    )


# ----------------------------------------------------------------- helpers


def _finite_or_none(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    num = float(value)
    return num if math.isfinite(num) else None


def _format_param_value(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return ", ".join(str(x) for x in value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _variant_label(case: WhatIfCase, variant: Mapping[str, Any]) -> str:
    if case.kind == "grid_connection_delay":
        months = int(variant["delay_months"])
        return f"{months}-month grid connection delay"
    if case.kind == "developer_funded_connection":
        amt = float(variant["connection_capex_usd"])
        return f"Developer-funded connection (${amt:,.0f})"
    if case.kind == "tariff_reference":
        rate = float(variant["tariff_per_kwh"])
        ccy = str(variant["currency"]).upper()
        return f"Tariff reference ({ccy} {rate:,.2f}/kWh)"
    return ", ".join(f"{k}={v}" for k, v in variant.items())


def _sources_and_uses_totals(
    su: Optional[Mapping[str, Any]],
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    if not isinstance(su, Mapping):
        return None, None, None
    sources = su.get("sources")
    debt_usd: Optional[float] = None
    equity_usd: Optional[float] = None
    if isinstance(sources, Mapping):
        equity_usd = _finite_or_none(sources.get("equity_usd"))
        debt_parts = [
            _finite_or_none(v) for k, v in sources.items() if k != "equity_usd"
        ]
        valid_debt = [v for v in debt_parts if v is not None]
        if valid_debt:
            debt_usd = float(sum(valid_debt))
    total_uses = _finite_or_none(su.get("uses_total_usd"))
    return debt_usd, equity_usd, total_uses


def _display_repo_path(raw: Optional[str], repo_root: Path) -> Optional[str]:
    if raw is None:
        return None
    p = Path(raw)
    try:
        return p.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return p.name


def _resolve_what_if_paths(
    settings: WhatIfLenderRiskSettings, root: Path
) -> Tuple[List[Path], str]:
    if settings.case_files is not None:
        resolved: List[Path] = []
        for entry in settings.case_files:
            candidate = Path(entry)
            if not candidate.is_absolute():
                candidate = root / candidate
            if not candidate.is_file():
                raise FileNotFoundError(
                    f"{_PREFIX}.case_files entry does not exist: {candidate}"
                )
            resolved.append(candidate)
        return resolved, "configured case_files"
    if settings.what_if_dir is not None:
        directory = Path(settings.what_if_dir)
        if not directory.is_absolute():
            directory = root / directory
        if not directory.is_dir():
            raise FileNotFoundError(
                f"{_PREFIX}.what_if_dir directory does not exist: {directory}"
            )
        return sorted(directory.glob("*.yaml")), str(settings.what_if_dir)
    return [], "no what_if_dir or case_files configured"


def _build_what_if_cases(
    scenario_config_path: Union[str, Path],
    scenario: Mapping[str, Any],
    settings: WhatIfLenderRiskSettings,
    *,
    what_if_runner: Optional[Callable[[Dict[str, Any]], Mapping[str, Any]]],
    repo_root: Path,
) -> Union[List[WhatIfCaseBlock], str]:
    paths, source_desc = _resolve_what_if_paths(settings, repo_root)
    if not paths:
        return f"not run: no #1403 what-if case files found ({source_desc})"

    loaded = [load_what_if_case(path, repo_root=repo_root) for path in paths]
    target = Path(scenario_config_path).resolve()
    matching = [case for case in loaded if case.base_scenario.resolve() == target]
    if not matching:
        return (
            f"not run: none of the {len(loaded)} case(s) in {source_desc} target "
            f"base_scenario {Path(scenario_config_path).name}"
        )

    blocks: List[WhatIfCaseBlock] = []
    for case in matching:
        res = run_what_if_case(
            case,
            runner=what_if_runner,
            base_config=copy.deepcopy(dict(scenario)),
        )
        disclosure = res["case"]
        params = [
            WhatIfParameterSummary(
                name=str(name),
                value_display=(
                    _format_param_value(meta["presets"])
                    if meta.get("presets")
                    else _format_param_value(meta.get("value"))
                ),
                provenance=str(meta["provenance"]),
            )
            for name, meta in (disclosure.get("parameters") or {}).items()
        ]
        variants: List[WhatIfVariantBlock] = []
        for var in res["variants"]:
            kpi_rows: List[WhatIfKpiRow] = []
            for row in var["report"]:
                key = str(row["kpi"])
                label, unit = _KPI_DISPLAY_SPEC.get(key, (key.replace("_", " "), "raw"))
                kpi_rows.append(
                    WhatIfKpiRow(
                        kpi=key,
                        label=label,
                        unit=unit,
                        base=_finite_or_none(row.get("base")),
                        case=_finite_or_none(row.get("case")),
                        delta=_finite_or_none(row.get("delta")),
                    )
                )
            debt_usd, equity_usd, total_uses_usd = _sources_and_uses_totals(
                var.get("sources_and_uses")
            )
            variants.append(
                WhatIfVariantBlock(
                    label=_variant_label(case, var["parameters"]),
                    parameters=dict(var["parameters"]),
                    changed_paths=[str(c["path"]) for c in var["changes"]],
                    kpis=kpi_rows,
                    debt_usd=debt_usd,
                    equity_usd=equity_usd,
                    total_uses_usd=total_uses_usd,
                )
            )
        blocks.append(
            WhatIfCaseBlock(
                case_id=str(disclosure["id"]),
                kind=str(disclosure["kind"]),
                label=str(disclosure["label"]),
                canonical=bool(disclosure["canonical"]),
                base_scenario=str(
                    _display_repo_path(disclosure.get("base_scenario"), repo_root)
                    or disclosure["base_scenario"]
                ),
                case_file=_display_repo_path(disclosure.get("case_file"), repo_root),
                source=str(disclosure["source"]),
                limitations=[str(item) for item in disclosure["limitations"]],
                parameters=params,
                notes=str(disclosure.get("notes") or ""),
                variants=variants,
            )
        )
    return blocks


def _mc_method_label(mc_result: MonteCarloResult) -> str:
    metadata = getattr(mc_result, "metadata", None)
    if not isinstance(metadata, Mapping):
        return "monte_carlo"
    sampler = str(metadata.get("sampler", "monte_carlo"))
    label = f"{sampler} sampling"
    if bool(metadata.get("correlation_enabled", False)):
        label += ", rank correlation"
    return label


def _validate_mc_result_lender_guards(mc_result: MonteCarloResult) -> None:
    metadata = getattr(mc_result, "metadata", None)
    toy = (
        int(metadata.get("toy_fallback_count", 0))
        if isinstance(metadata, Mapping)
        else 0
    )
    if toy > 0:
        raise ValueError(
            f"MonteCarloResult has {toy} toy-fallback trial(s): lender-grade outputs "
            "refuse fabricated fallback trials."
        )
    iterations = int(getattr(mc_result, "iterations", 0))
    if iterations < LENDER_GRADE_MIN_TRIALS:
        raise ValueError(
            f"CASPER lender-risk block needs >= {LENDER_GRADE_MIN_TRIALS} trials; "
            f"got {iterations}."
        )


def _casper_row_unit(metric_label: str) -> str:
    if metric_label.startswith("Prob(") or metric_label == "Project IRR":
        return "pct"
    if metric_label == "Project NPV":
        return "usd"
    return "ratio"


def _can_reuse_mc_result(
    mc_result: Optional[MonteCarloResult],
    settings: WhatIfLenderRiskSettings,
) -> bool:
    if mc_result is None:
        return False
    iterations = int(getattr(mc_result, "iterations", 0))
    if iterations < settings.mc_trials:
        return False
    if settings.mc_seed is None:
        return True
    metadata = getattr(mc_result, "metadata", None)
    res_seed = metadata.get("seed") if isinstance(metadata, Mapping) else None
    return res_seed == settings.mc_seed


def _build_casper_lender_risk(
    scenario_config_path: Union[str, Path],
    scenario: Mapping[str, Any],
    settings: WhatIfLenderRiskSettings,
    *,
    mc_result: Optional[MonteCarloResult],
    mc_runner: Optional[Callable[..., MonteCarloResult]],
) -> Union[CasperLenderRiskBlock, str]:
    active_mc: Optional[MonteCarloResult] = None
    if _can_reuse_mc_result(mc_result, settings):
        active_mc = mc_result
    else:
        mc_block = scenario.get("monte_carlo")
        if not isinstance(mc_block, Mapping) or not mc_block.get("parameters"):
            return "not run: the scenario declares no monte_carlo.parameters to sample"
        runner = mc_runner or run_lender_grade_monte_carlo
        active_mc = runner(
            scenario,
            n_trials=settings.mc_trials,
            min_trials=LENDER_GRADE_MIN_TRIALS,
            seed=settings.mc_seed,
        )

    assert active_mc is not None
    _validate_mc_result_lender_guards(active_mc)

    dscr_floor = resolve_min_dscr_covenant(scenario)
    try:
        blocks = build_casper_risk_blocks(
            active_mc, covenant=CovenantSpec(dscr_floor=dscr_floor)
        )
    except (KeyError, RuntimeError, ImportError) as exc:
        # Sanctioned CASPER degradation when raw trial arrays or pandas are absent.
        return f"not run: CASPER lender-risk table unavailable ({type(exc).__name__}: {exc})"

    table = blocks.get("lender_risk_table")
    if table is None:
        return "not run: build_casper_risk_blocks returned no lender_risk_table"

    rows: List[CasperLenderRiskRow] = []
    coverage_notes: List[str] = []
    for raw_row in table.to_dict(orient="records"):
        metric_label = str(raw_row["metric"])
        note_raw = raw_row.get("coverage_note")
        note = note_raw if isinstance(note_raw, str) and note_raw.strip() else None
        if note is not None and note not in coverage_notes:
            coverage_notes.append(note)
        rows.append(
            CasperLenderRiskRow(
                metric=metric_label,
                unit=_casper_row_unit(metric_label),
                p50=_finite_or_none(raw_row.get("P50")),
                p90=_finite_or_none(raw_row.get("P90")),
                p95=_finite_or_none(raw_row.get("P95")),
                mean=_finite_or_none(raw_row.get("mean")),
                std=_finite_or_none(raw_row.get("std")),
                defined_trials=int(raw_row["defined_trials"]),
                total_trials=int(raw_row["total_trials"]),
                unavailable_trials=int(raw_row["unavailable_trials"]),
                coverage_note=note,
            )
        )

    cov = blocks["covenant"]
    floor_pinned = bool(cov["floor_pinned"])
    covenant = CasperCovenantSummary(
        dscr_floor=float(cov["dscr_floor"]),
        prob_breach=float(cov["prob_breach"]),
        floor_pinned=floor_pinned,
        worst_year_dscr_p95_downside=_finite_or_none(
            cov.get("worst_year_dscr_p95_downside")
        ),
        n_trials=int(cov["n_trials"]),
        n_total_trials=int(cov["n_total_trials"]),
        unavailable_trials=int(cov["unavailable_trials"]),
    )

    metadata = getattr(active_mc, "metadata", None)
    seed_used = (
        int(metadata["seed"])
        if isinstance(metadata, Mapping)
        and isinstance(metadata.get("seed"), int)
        and not isinstance(metadata.get("seed"), bool)
        else settings.mc_seed
    )
    scenario_label = str(
        getattr(active_mc, "scenario_name", None)
        or (scenario.get("project") or {}).get("name")
        or Path(scenario_config_path).stem
    )
    return CasperLenderRiskBlock(
        scenario=scenario_label,
        method=_mc_method_label(active_mc),
        n_trials=int(cov["n_total_trials"]),
        seed=seed_used,
        allow_toy_fallback=False,
        covenant=covenant,
        rows=rows,
        floor_pinned_note=_FLOOR_PINNED_DISCLOSURE if floor_pinned else None,
        coverage_notes=coverage_notes,
    )


def build_what_if_lender_risk_section(
    scenario_config_path: Union[str, Path],
    scenario: Mapping[str, Any],
    settings: WhatIfLenderRiskSettings,
    *,
    mc_result: Optional[MonteCarloResult] = None,
    what_if_runner: Optional[Callable[[Dict[str, Any]], Mapping[str, Any]]] = None,
    mc_runner: Optional[Callable[..., MonteCarloResult]] = None,
    repo_root: Optional[Path] = None,
) -> Union[WhatIfLenderRiskBlock, str]:
    """Build the what-if (#1403/#1523) and CASPER lender-risk section, or say why not.

    Args:
        scenario_config_path: Path to the scenario evaluated by the report.
        scenario: The parsed scenario configuration mapping (never mutated).
        settings: ``lender_report.what_if_lender_risk``.
        mc_result: Optional already-computed lender-grade :class:`MonteCarloResult`
            from the same run (avoids a duplicate Monte Carlo execution when compatible).
        what_if_runner: Test seam passed through to :func:`run_what_if_case`.
        mc_runner: Test seam replacing :func:`run_lender_grade_monte_carlo`.
        repo_root: Repository root for resolving relative what-if paths; defaults to the
            repository root.

    Returns:
        A :class:`WhatIfLenderRiskBlock` when enabled, or a ``"not run: ..."`` string
        when switched off.

    Raises:
        ValueError, FileNotFoundError, WhatIfCaseError: When enabled with misconfigured
            settings, missing configured case paths, malformed case YAML, a trial count
            below :data:`LENDER_GRADE_MIN_TRIALS`, or toy-fallback trials present.
    """
    if not settings.enabled:
        return (
            f"not run: switched off ({_PREFIX}.enabled is false; the section is opt-in, "
            "#1825)"
        )
    if settings.mc_trials < LENDER_GRADE_MIN_TRIALS:
        raise ValueError(
            f"{_PREFIX}.mc.trials must be at least {LENDER_GRADE_MIN_TRIALS} "
            f"(the lender-grade floor), not {settings.mc_trials}"
        )

    root = Path(repo_root) if repo_root is not None else _DEFAULT_REPO_ROOT
    not_run: List[str] = []

    what_if_out = _build_what_if_cases(
        scenario_config_path,
        scenario,
        settings,
        what_if_runner=what_if_runner,
        repo_root=root,
    )
    if isinstance(what_if_out, str):
        not_run.append(f"What-if cases (#1403): {what_if_out}")
        what_if_cases: List[WhatIfCaseBlock] = []
    else:
        what_if_cases = what_if_out

    casper_out = _build_casper_lender_risk(
        scenario_config_path,
        scenario,
        settings,
        mc_result=mc_result,
        mc_runner=mc_runner,
    )
    if isinstance(casper_out, str):
        not_run.append(f"CASPER lender-risk blocks (FRAMEWORK-01): {casper_out}")
        casper_block: Optional[CasperLenderRiskBlock] = None
    else:
        casper_block = casper_out

    return WhatIfLenderRiskBlock(
        what_if_cases=what_if_cases,
        casper_lender_risk=casper_block,
        parts_not_run=not_run,
    )

"""Non-canonical what-if cases applied to a named base scenario (#1403).

A what-if case is a small YAML file that names a base scenario, says which input
it changes and by how much, and carries the source, limitations and provenance
of every parameter. This module loads such a file, derives the case config from
a deep copy of the base, runs the base and the case through the same v14
pipeline, and returns both KPI vectors with the case's disclosure attached.

Nothing here is canonical and nothing here is site-specific. The base scenario,
the tariff, the currency, the connection amount and the delay all come from the
case YAML, so the same file shape works for any project the engine can run. The
committed base scenarios are never written to, so the KPIs they produce cannot
move because a case exists.

Three kinds are supported. Each is built only from inputs the engine already
reads, so no engine code changes and no default moves:

``grid_connection_delay``
    The plant is built on the base schedule but cannot export until the grid
    connection is ready. Each 12 months of delay adds one idle construction
    period with no capex and no debt draw, so interest during construction keeps
    accruing, commercial operation and the first revenue move out by the same
    number of years, and the project cash flows are discounted from the later
    start. The engine runs in whole years, so a delay that is not a whole number
    of years is refused rather than rounded.

``developer_funded_connection``
    The developer pays for grid connection assets that the grid owner would
    otherwise build. The amount is added to the base capex total as its own
    breakdown line, so it is financed and depreciated like the rest of the capex.
    Reimbursement must be zero: the engine has no channel for a reimbursement or
    annuity, and #1403 keeps it at zero until a written instrument evidences it.

``tariff_reference``
    The energy tariff is replaced by a published reference value, labelled a
    reference and not an entitlement. The tariff field is named by the case's
    currency (``tariff.<currency>_per_kwh``), and the base scenario must already
    carry that field, so the case cannot invent a tariff path the engine ignores.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import yaml

#: Months in one engine operating period. The v14 cashflow engine is annual.
MONTHS_PER_ENGINE_PERIOD = 12

SUPPORTED_KINDS: Tuple[str, ...] = (
    "grid_connection_delay",
    "developer_funded_connection",
    "tariff_reference",
)

_REQUIRED_CASE_KEYS: Tuple[str, ...] = (
    "id",
    "kind",
    "label",
    "canonical",
    "base_scenario",
    "parameters",
    "source",
    "limitations",
    "report_kpis",
)
_OPTIONAL_CASE_KEYS: Tuple[str, ...] = ("notes",)

_PARAMETERS_BY_KIND: Dict[str, Tuple[str, ...]] = {
    "grid_connection_delay": ("delay_months",),
    "developer_funded_connection": (
        "connection_capex_usd",
        "reimbursement_usd_per_year",
    ),
    "tariff_reference": ("tariff_per_kwh", "currency"),
}


class WhatIfCaseError(ValueError):
    """A what-if case file or its base scenario cannot be used as declared."""


@dataclass(frozen=True)
class WhatIfParameter:
    """One case parameter with the provenance that has to travel with it."""

    name: str
    value: Any
    provenance: str
    presets: Tuple[Any, ...] = ()
    deferred_presets: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class WhatIfCase:
    """A loaded, validated what-if case."""

    case_id: str
    kind: str
    label: str
    base_scenario: Path
    parameters: Mapping[str, WhatIfParameter]
    source: str
    limitations: Tuple[str, ...]
    report_kpis: Tuple[str, ...]
    case_path: Optional[Path] = None
    notes: str = ""

    def variants(self) -> List[Dict[str, Any]]:
        """Return one parameter assignment per runnable variant.

        A parameter with ``presets`` expands into one variant per preset; every
        other parameter keeps its single ``value``. At most one parameter in a
        case may carry presets, which the loader enforces.
        """
        base = {name: p.value for name, p in self.parameters.items()}
        for name, param in self.parameters.items():
            if param.presets:
                return [{**base, name: preset} for preset in param.presets]
        return [base]

    def disclosure(self) -> Dict[str, Any]:
        """Return the case's source, limitations and provenance for the output."""
        return {
            "id": self.case_id,
            "kind": self.kind,
            "label": self.label,
            "canonical": False,
            "base_scenario": str(self.base_scenario),
            "case_file": None if self.case_path is None else str(self.case_path),
            "source": self.source,
            "limitations": list(self.limitations),
            "parameters": {
                name: {
                    "value": p.value,
                    "presets": list(p.presets),
                    "deferred_presets": dict(p.deferred_presets),
                    "provenance": p.provenance,
                }
                for name, p in self.parameters.items()
            },
            "notes": self.notes,
        }


# --------------------------------------------------------------------------- loading


def _require_text(raw: Mapping[str, Any], key: str, where: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise WhatIfCaseError(f"{where}.{key} must be a non-empty string.")
    return value.strip()


def _parse_parameter(name: str, raw: Any, where: str) -> WhatIfParameter:
    if not isinstance(raw, Mapping):
        raise WhatIfCaseError(
            f"{where}.{name} must be a mapping with value and provenance."
        )
    unknown = set(raw) - {"value", "presets", "deferred_presets", "provenance"}
    if unknown:
        raise WhatIfCaseError(f"{where}.{name} has unknown keys {sorted(unknown)}.")
    provenance = _require_text(raw, "provenance", f"{where}.{name}")
    presets_raw = raw.get("presets", [])
    if not isinstance(presets_raw, Sequence) or isinstance(presets_raw, str):
        raise WhatIfCaseError(f"{where}.{name}.presets must be a list.")
    presets = tuple(presets_raw)
    if "value" in raw and presets:
        raise WhatIfCaseError(
            f"{where}.{name} declares both value and presets; declare one."
        )
    if "value" not in raw and not presets:
        raise WhatIfCaseError(f"{where}.{name} must declare a value or presets.")
    deferred_raw = raw.get("deferred_presets", {}) or {}
    if not isinstance(deferred_raw, Mapping):
        raise WhatIfCaseError(
            f"{where}.{name}.deferred_presets must map each preset to its reason."
        )
    deferred = {str(k): str(v) for k, v in deferred_raw.items()}
    for key, reason in deferred.items():
        if not reason.strip():
            raise WhatIfCaseError(
                f"{where}.{name}.deferred_presets[{key}] needs a stated reason."
            )
    return WhatIfParameter(
        name=name,
        value=raw.get("value", presets[0] if presets else None),
        provenance=provenance,
        presets=presets,
        deferred_presets=deferred,
    )


def parse_what_if_case(
    raw: Mapping[str, Any],
    *,
    case_path: Optional[Path] = None,
    repo_root: Optional[Path] = None,
) -> WhatIfCase:
    """Validate a case mapping (the ``what_if_case`` block) and return the case.

    Args:
        raw: The ``what_if_case`` mapping from a case file.
        case_path: The file it came from, kept for the disclosure.
        repo_root: Directory that a relative ``base_scenario`` resolves against.
            Defaults to the current working directory.

    Raises:
        WhatIfCaseError: A required key is missing, an unknown key is present, the
            case claims to be canonical, or a parameter lacks its provenance.
    """
    where = "what_if_case"
    if not isinstance(raw, Mapping):
        raise WhatIfCaseError(f"{where} must be a mapping.")
    missing = [k for k in _REQUIRED_CASE_KEYS if k not in raw]
    if missing:
        raise WhatIfCaseError(f"{where} is missing required keys {missing}.")
    unknown = set(raw) - set(_REQUIRED_CASE_KEYS) - set(_OPTIONAL_CASE_KEYS)
    if unknown:
        raise WhatIfCaseError(f"{where} has unknown keys {sorted(unknown)}.")
    if raw["canonical"] is not False:
        raise WhatIfCaseError(
            f"{where}.canonical must be false: a what-if case is never canonical."
        )
    kind = _require_text(raw, "kind", where)
    if kind not in SUPPORTED_KINDS:
        raise WhatIfCaseError(
            f"{where}.kind {kind!r} is not supported; expected one of "
            f"{list(SUPPORTED_KINDS)}."
        )
    params_raw = raw["parameters"]
    if not isinstance(params_raw, Mapping):
        raise WhatIfCaseError(f"{where}.parameters must be a mapping.")
    expected = set(_PARAMETERS_BY_KIND[kind])
    if set(params_raw) != expected:
        raise WhatIfCaseError(
            f"{where}.parameters for kind {kind!r} must be exactly "
            f"{sorted(expected)}; got {sorted(params_raw)}."
        )
    parameters = {
        name: _parse_parameter(name, params_raw[name], f"{where}.parameters")
        for name in _PARAMETERS_BY_KIND[kind]
    }
    if sum(1 for p in parameters.values() if p.presets) > 1:
        raise WhatIfCaseError(f"{where}: at most one parameter may carry presets.")

    limitations = raw["limitations"]
    if (
        not isinstance(limitations, Sequence)
        or isinstance(limitations, str)
        or not limitations
        or not all(isinstance(x, str) and x.strip() for x in limitations)
    ):
        raise WhatIfCaseError(f"{where}.limitations must be a non-empty list of text.")
    report_kpis = raw["report_kpis"]
    if (
        not isinstance(report_kpis, Sequence)
        or isinstance(report_kpis, str)
        or not report_kpis
        or not all(isinstance(x, str) and x for x in report_kpis)
    ):
        raise WhatIfCaseError(f"{where}.report_kpis must be a non-empty list of names.")

    base = Path(_require_text(raw, "base_scenario", where))
    if not base.is_absolute():
        base = (repo_root or Path.cwd()) / base

    case = WhatIfCase(
        case_id=_require_text(raw, "id", where),
        kind=kind,
        label=_require_text(raw, "label", where),
        base_scenario=base,
        parameters=parameters,
        source=_require_text(raw, "source", where),
        limitations=tuple(x.strip() for x in limitations),
        report_kpis=tuple(report_kpis),
        case_path=case_path,
        notes=str(raw.get("notes", "") or "").strip(),
    )
    for variant in case.variants():
        _VALIDATORS[kind](variant)
    return case


def load_what_if_case(
    path: str | Path, *, repo_root: Optional[Path] = None
) -> WhatIfCase:
    """Load and validate a what-if case file.

    The file holds one top-level ``what_if_case`` mapping. A relative
    ``base_scenario`` resolves against ``repo_root``, or against the current
    working directory when ``repo_root`` is not given.
    """
    case_path = Path(path)
    doc = yaml.safe_load(case_path.read_text(encoding="utf-8"))
    if not isinstance(doc, Mapping) or set(doc) != {"what_if_case"}:
        raise WhatIfCaseError(
            f"{case_path}: a case file holds exactly one top-level key, what_if_case."
        )
    return parse_what_if_case(
        doc["what_if_case"], case_path=case_path, repo_root=repo_root
    )


# ------------------------------------------------------------------ per-kind rules


def _finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WhatIfCaseError(f"{name} must be a number; got {value!r}.")
    number = float(value)
    if not math.isfinite(number):
        raise WhatIfCaseError(f"{name} must be finite; got {value!r}.")
    return number


def _delay_periods(delay_months: Any) -> int:
    months = _finite_number(delay_months, "delay_months")
    if months <= 0 or months != int(months):
        raise WhatIfCaseError(
            f"delay_months must be a positive whole number of months; got {delay_months!r}."
        )
    if int(months) % MONTHS_PER_ENGINE_PERIOD:
        raise WhatIfCaseError(
            f"delay_months {int(months)} is not a whole number of engine periods "
            f"({MONTHS_PER_ENGINE_PERIOD} months each). The cashflow engine is "
            "annual and has no partial-year operating lever, so this delay is "
            "refused rather than rounded."
        )
    return int(months) // MONTHS_PER_ENGINE_PERIOD


def _validate_delay(variant: Mapping[str, Any]) -> None:
    _delay_periods(variant["delay_months"])


def _validate_connection(variant: Mapping[str, Any]) -> None:
    amount = _finite_number(variant["connection_capex_usd"], "connection_capex_usd")
    if amount < 0:
        raise WhatIfCaseError("connection_capex_usd must not be negative.")
    reimbursement = _finite_number(
        variant["reimbursement_usd_per_year"], "reimbursement_usd_per_year"
    )
    if reimbursement != 0.0:
        raise WhatIfCaseError(
            "reimbursement_usd_per_year must be 0. The engine has no reimbursement "
            "or annuity channel, and none is modelled until a written instrument "
            "evidences one (#1403)."
        )


def _currency_code(value: Any) -> str:
    if not isinstance(value, str) or not value.isalpha() or len(value) != 3:
        raise WhatIfCaseError(
            f"currency must be a three-letter currency code; got {value!r}."
        )
    return value.lower()


def _validate_tariff(variant: Mapping[str, Any]) -> None:
    tariff = _finite_number(variant["tariff_per_kwh"], "tariff_per_kwh")
    if tariff <= 0:
        raise WhatIfCaseError("tariff_per_kwh must be positive.")
    _currency_code(variant["currency"])


_VALIDATORS: Dict[str, Callable[[Mapping[str, Any]], None]] = {
    "grid_connection_delay": _validate_delay,
    "developer_funded_connection": _validate_connection,
    "tariff_reference": _validate_tariff,
}


# -------------------------------------------------------------------- derivation


def _section(config: Dict[str, Any], name: str) -> Dict[str, Any]:
    section = config.get(name)
    if not isinstance(section, dict):
        raise WhatIfCaseError(f"base scenario has no {name!r} mapping to modify.")
    return section


def _apply_delay(
    config: Dict[str, Any], variant: Mapping[str, Any]
) -> List[Dict[str, Any]]:
    from finance.debt_v14 import (
        _extract_financing_terms,
        _resolve_construction_periods,
    )

    periods = _delay_periods(variant["delay_months"])
    terms = _section(config, "Financing_Terms")
    # Resolve the base schedules exactly as the debt engine does, placeholders and
    # their warnings included, so the case extends what the base actually runs.
    resolved = _extract_financing_terms(config)
    construction = _resolve_construction_periods(config)
    schedule = [float(x) for x in resolved["construction_schedule"]]
    drawdown = [float(x) for x in resolved["debt_drawdown_pct"]]
    if len(schedule) != construction or len(drawdown) != construction:
        raise WhatIfCaseError(
            "the base construction_schedule and debt_drawdown_pct must each have one "
            f"entry per construction period ({construction}); got {len(schedule)} and "
            f"{len(drawdown)}, so the idle delay periods cannot be appended safely."
        )
    changes: List[Dict[str, Any]] = [
        {
            "path": "Financing_Terms.construction_periods",
            "base": construction,
            "case": construction + periods,
        },
        {
            "path": "Financing_Terms.construction_schedule",
            "base": schedule,
            "case": schedule + [0.0] * periods,
        },
        {
            "path": "Financing_Terms.debt_drawdown_pct",
            "base": drawdown,
            "case": drawdown + [0.0] * periods,
        },
    ]
    terms["construction_periods"] = construction + periods
    terms["construction_schedule"] = schedule + [0.0] * periods
    terms["debt_drawdown_pct"] = drawdown + [0.0] * periods

    # Calendar labels that restate the construction window move with it, when the
    # base carries them, so the case does not report a COD the cash flows contradict.
    project = config.get("project")
    if isinstance(project, dict) and project.get("cod_year") is not None:
        cod = int(_finite_number(project["cod_year"], "project.cod_year"))
        project["cod_year"] = cod + periods
        changes.append({"path": "project.cod_year", "base": cod, "case": cod + periods})
    timeline = config.get("timeline")
    if isinstance(timeline, dict):
        for key in ("construction_years", "lifetime_years"):
            if timeline.get(key) is not None:
                old = int(_finite_number(timeline[key], f"timeline.{key}"))
                timeline[key] = old + periods
                changes.append(
                    {"path": f"timeline.{key}", "base": old, "case": old + periods}
                )
    return changes


def _apply_connection(
    config: Dict[str, Any], variant: Mapping[str, Any]
) -> List[Dict[str, Any]]:
    amount = float(variant["connection_capex_usd"])
    capex = _section(config, "capex")
    if capex.get("derive_from_breakdown"):
        raise WhatIfCaseError(
            "the base scenario derives capex from its breakdown; this case adds to "
            "capex.usd_total and would be ignored, so it is refused."
        )
    total = _finite_number(capex.get("usd_total"), "capex.usd_total")
    breakdown = capex.get("breakdown")
    line = "developer_funded_connection_usd"
    if isinstance(breakdown, dict) and line in breakdown:
        raise WhatIfCaseError(
            f"the base scenario already carries capex.breakdown.{line}."
        )
    capex["usd_total"] = total + amount
    changes: List[Dict[str, Any]] = [
        {"path": "capex.usd_total", "base": total, "case": total + amount}
    ]
    if isinstance(breakdown, dict):
        breakdown[line] = amount
        changes.append(
            {"path": f"capex.breakdown.{line}", "base": None, "case": amount}
        )
    return changes


def _apply_tariff(
    config: Dict[str, Any], variant: Mapping[str, Any]
) -> List[Dict[str, Any]]:
    key = f"{_currency_code(variant['currency'])}_per_kwh"
    tariff = _section(config, "tariff")
    if key not in tariff:
        raise WhatIfCaseError(
            f"the base scenario has no tariff.{key}; the case refuses to write a "
            "tariff field the base scenario does not use."
        )
    old = _finite_number(tariff[key], f"tariff.{key}")
    new = float(variant["tariff_per_kwh"])
    tariff[key] = new
    return [{"path": f"tariff.{key}", "base": old, "case": new}]


_APPLIERS: Dict[
    str, Callable[[Dict[str, Any], Mapping[str, Any]], List[Dict[str, Any]]]
] = {
    "grid_connection_delay": _apply_delay,
    "developer_funded_connection": _apply_connection,
    "tariff_reference": _apply_tariff,
}


def build_case_config(
    case: WhatIfCase,
    base_config: Mapping[str, Any],
    variant: Mapping[str, Any],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Return ``(case_config, changes)`` for one variant of ``case``.

    ``base_config`` is deep-copied and never modified. ``changes`` lists every
    config path the case moved, with its base and case values.
    """
    _VALIDATORS[case.kind](variant)
    config = copy.deepcopy(dict(base_config))
    changes = _APPLIERS[case.kind](config, variant)
    meta = config.get("meta")
    meta = dict(meta) if isinstance(meta, Mapping) else {}
    meta["what_if_case"] = {"id": case.case_id, "canonical": False, **dict(variant)}
    config["meta"] = meta
    return config, changes


# -------------------------------------------------------------------------- running


def _numeric_kpis(kpis: Mapping[str, Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for key, value in kpis.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        out[key] = float(value)
    return out


def _sources_and_uses(result: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """Return the debt engine's sources-and-uses table, when the run published one."""
    debt = result.get("debt_result")
    funding = debt.get("funding") if isinstance(debt, Mapping) else None
    table = funding.get("sources_and_uses") if isinstance(funding, Mapping) else None
    return copy.deepcopy(dict(table)) if isinstance(table, Mapping) else None


def _kpi_rows(
    names: Sequence[str], base: Mapping[str, Any], case: Mapping[str, Any]
) -> List[Dict[str, Any]]:
    rows = []
    for name in names:
        b, c = base.get(name), case.get(name)
        numeric = all(
            isinstance(v, (int, float)) and not isinstance(v, bool) for v in (b, c)
        )
        rows.append(
            {
                "kpi": name,
                "base": b,
                "case": c,
                "delta": (float(c) - float(b)) if numeric else None,  # type: ignore[arg-type]
            }
        )
    return rows


def run_what_if_case(
    case: WhatIfCase,
    *,
    runner: Optional[Callable[[Dict[str, Any]], Mapping[str, Any]]] = None,
    base_config: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Run the base scenario and every variant of ``case``; return both with disclosure.

    Args:
        case: A loaded case.
        runner: Callable taking a config and returning a pipeline result with a
            ``kpis`` mapping. Defaults to the ``evaluate_with_overrides`` gateway
            (``ARCH-04``) with no overrides, so the base and every variant run
            through the same validated v14 pipeline path.
        base_config: The base config, if the caller has already loaded it.
            Defaults to loading ``case.base_scenario``.

    Returns:
        ``{"case": disclosure, "base": {...}, "variants": [...]}``. Each variant
        carries its parameters, the config changes, the ``report_kpis`` rows, the
        debt engine's sources and uses (the liquidity view: how much of the larger
        or smaller funding need falls on debt and on equity) and the full numeric
        KPI vector of the case run.
    """
    if runner is None:
        from analytics.evaluation_v14 import evaluate_with_overrides

        def runner(cfg: Dict[str, Any]) -> Mapping[str, Any]:
            return evaluate_with_overrides(raw_config=cfg, return_full_result=True)

    if base_config is None:
        from analytics.scenario_loader import load_scenario_config

        base_config = load_scenario_config(case.base_scenario)

    base_result = runner(copy.deepcopy(dict(base_config)))
    base_kpis = dict(base_result["kpis"])
    variants = []
    for variant in case.variants():
        config, changes = build_case_config(case, base_config, variant)
        case_result = runner(config)
        case_kpis = dict(case_result["kpis"])
        variants.append(
            {
                "parameters": dict(variant),
                "changes": changes,
                "report": _kpi_rows(case.report_kpis, base_kpis, case_kpis),
                "sources_and_uses": _sources_and_uses(case_result),
                "kpis": _numeric_kpis(case_kpis),
            }
        )
    return {
        "case": case.disclosure(),
        "base": {
            "scenario": str(case.base_scenario),
            "sources_and_uses": _sources_and_uses(base_result),
            "kpis": _numeric_kpis(base_kpis),
        },
        "variants": variants,
    }

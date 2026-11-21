"""Optional scenario blocks for the site analyses (#1754).

The owner ruled on 2026-11-16 that the analyses first built for one site (wind battery
options, PV + BESS sizing, FX and tenor screening, equipment cost parity) run for every
scenario, with the location, sizes and technology taken from the scenario YAML. This module
is the contract for the four top-level blocks those analyses read:

- ``storage_options``: wind battery options (its optional ``headline_option`` names one held
  option to carry into the scenario's own KPIs, #1823, ``analytics.storage_headline``);
- ``solar_storage_sizing``: PV + BESS sizing and dispatch;
- ``financing_screening``: FX and tenor screening;
- ``equipment_cost_parity``: equipment cost parity.

Every analysis is on by default for every scenario (owner ruling, 2026-11-16).
:func:`plan_site_analyses` lists all four for any scenario. An analysis whose block the scenario
declares is planned to run; one whose block is absent is listed as ``not_applicable`` with the
reason, never skipped silently and never an error, because its site inputs can only come from
the scenario. Validation adds nothing for an absent block, so a scenario without the blocks
validates exactly as before. A block that is present is checked strictly: an unknown key, a missing required key, a wrong type, a value out of range or a
referenced file that does not exist is an error that names the path (``FRAMEWORK-02``).
Nothing here holds a site name, a path or a figure (``ARCH-01``): every value comes from the
scenario.

Every block shares one envelope:

- ``site``: ``name`` and ``location`` (text), optional ``latitude_deg`` and
  ``longitude_deg`` (given together) and an optional ``geometry_file``;
- ``retrieved``: the ISO date the inputs were gathered;
- ``sources``: a non-empty list of the documents the inputs come from;
- ``method_config`` (optional): the analysis's method-parameter file;
- ``notes`` (optional).

Private anchors are never a value in a block: an analysis that needs them takes their path
at run time, outside the scenario.

Each block holds what its analysis reads today. When an analysis is wired to its block, its
item adds any further key here explicitly, so the keys stay strict.
"""

from __future__ import annotations

import datetime as _dt
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]

#: The four optional top-level blocks, in a fixed order.
SITE_ANALYSIS_BLOCKS: Tuple[str, ...] = (
    "storage_options",
    "solar_storage_sizing",
    "financing_screening",
    "equipment_cost_parity",
)

#: What each block's analysis is called in a plan.
SITE_ANALYSIS_NAMES: Dict[str, str] = {
    "storage_options": "wind battery options",
    "solar_storage_sizing": "PV + BESS sizing and dispatch",
    "financing_screening": "FX and tenor screening",
    "equipment_cost_parity": "equipment cost parity",
}

#: Plan statuses.
STATUS_RUN = "run"
STATUS_NOT_APPLICABLE = "not_applicable"

#: The label every financing-screening block must carry: its results are screening
#: figures under the F-5 HOLD, never lender terms.
SCREENING_LABEL = "screening"

#: Delivery routes a cost-buildup package may belong to.
COST_BUILDUP_ROUTES: Tuple[str, ...] = (
    "common",
    "route_specific",
    "marine",
    "marine_conditional",
    "road",
)

_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

Check = Callable[[Any, str, List[str]], None]


# --------------------------------------------------------------------------- leaf checks


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _number(
    *,
    gt: Optional[float] = None,
    ge: Optional[float] = None,
    le: Optional[float] = None,
    lt: Optional[float] = None,
) -> Check:
    def check(value: Any, path: str, errors: List[str]) -> None:
        if not _is_number(value):
            errors.append(f"{path}: must be a finite number (got {value!r})")
            return
        v = float(value)
        if gt is not None and not v > gt:
            errors.append(f"{path}: must be > {gt} (got {value!r})")
        if ge is not None and not v >= ge:
            errors.append(f"{path}: must be >= {ge} (got {value!r})")
        if lt is not None and not v < lt:
            errors.append(f"{path}: must be < {lt} (got {value!r})")
        if le is not None and not v <= le:
            errors.append(f"{path}: must be <= {le} (got {value!r})")

    return check


def _positive_int(value: Any, path: str, errors: List[str]) -> None:
    if not (isinstance(value, int) and not isinstance(value, bool) and value > 0):
        errors.append(f"{path}: must be a positive integer (got {value!r})")


def _nonnegative_int(value: Any, path: str, errors: List[str]) -> None:
    if not (isinstance(value, int) and not isinstance(value, bool) and value >= 0):
        errors.append(f"{path}: must be a non-negative integer (got {value!r})")


def _nonempty_str(value: Any, path: str, errors: List[str]) -> None:
    if not (isinstance(value, str) and value.strip()):
        errors.append(f"{path}: must be a non-empty string (got {value!r})")


def _currency(value: Any, path: str, errors: List[str]) -> None:
    if not (isinstance(value, str) and _CURRENCY_RE.match(value)):
        errors.append(
            f"{path}: must be a three-letter ISO currency code (got {value!r})"
        )


def _iso_date(value: Any, path: str, errors: List[str]) -> None:
    if isinstance(value, _dt.datetime):
        errors.append(f"{path}: must be a date, not a date and time (got {value!r})")
        return
    if isinstance(value, _dt.date):
        return
    if isinstance(value, str) and _ISO_DATE_RE.match(value):
        try:
            _dt.date.fromisoformat(value)
            return
        except ValueError:
            pass
    errors.append(f"{path}: must be an ISO date YYYY-MM-DD (got {value!r})")


def _repo_file(value: Any, path: str, errors: List[str]) -> None:
    if not (isinstance(value, str) and value.strip()):
        errors.append(
            f"{path}: must be a repository-relative file path (got {value!r})"
        )
        return
    rel = Path(value)
    if rel.is_absolute() or ".." in rel.parts:
        errors.append(
            f"{path}: must be relative to the repository root, without '..' "
            f"(got {value!r})"
        )
        return
    if not (REPO_ROOT / rel).is_file():
        errors.append(f"{path}: file not found in the repository (got {value!r})")


def _enum(choices: Sequence[str]) -> Check:
    def check(value: Any, path: str, errors: List[str]) -> None:
        if value not in choices:
            errors.append(f"{path}: must be one of {list(choices)} (got {value!r})")

    return check


def _literal(expected: str) -> Check:
    def check(value: Any, path: str, errors: List[str]) -> None:
        if value != expected:
            errors.append(f"{path}: must be {expected!r} (got {value!r})")

    return check


def _optional_number_ge0(value: Any, path: str, errors: List[str]) -> None:
    if value is None:
        return
    _number(ge=0.0)(value, path, errors)


def _list_of(item: Check, *, unique: bool = False) -> Check:
    def check(value: Any, path: str, errors: List[str]) -> None:
        if not isinstance(value, list) or not value:
            errors.append(f"{path}: must be a non-empty list (got {value!r})")
            return
        for i, entry in enumerate(value):
            item(entry, f"{path}[{i}]", errors)
        if unique:
            try:
                if len(set(value)) != len(value):
                    errors.append(f"{path}: entries must be unique (got {value!r})")
            except TypeError:
                errors.append(f"{path}: entries must be unique scalars")

    return check


# ------------------------------------------------------------------------ mapping checks


@dataclass(frozen=True)
class _Key:
    check: Check
    required: bool = True


@dataclass(frozen=True)
class _Mapping:
    keys: Mapping[str, _Key]
    rules: Tuple[Callable[[Mapping[str, Any], str, List[str]], None], ...] = field(
        default_factory=tuple
    )

    def __call__(self, value: Any, path: str, errors: List[str]) -> None:
        if not isinstance(value, Mapping):
            errors.append(f"{path}: must be a mapping (got {type(value).__name__})")
            return
        for key in value:
            if key not in self.keys:
                errors.append(
                    f"{path}.{key}: unknown key; allowed keys are {sorted(self.keys)}"
                )
        for key, spec in self.keys.items():
            if key not in value:
                if spec.required:
                    errors.append(f"{path}.{key}: required key is missing")
                continue
            spec.check(value[key], f"{path}.{key}", errors)
        for rule in self.rules:
            rule(value, path, errors)


def _req(check: Check) -> _Key:
    return _Key(check, required=True)


def _opt(check: Check) -> _Key:
    return _Key(check, required=False)


def _coordinates_together(
    block: Mapping[str, Any], path: str, errors: List[str]
) -> None:
    if ("latitude_deg" in block) != ("longitude_deg" in block):
        errors.append(f"{path}: latitude_deg and longitude_deg must be given together")


def _cut_out_above_cut_in(
    block: Mapping[str, Any], path: str, errors: List[str]
) -> None:
    cut_in: Any = block.get("cut_in_ms")
    cut_out: Any = block.get("cut_out_ms")
    if _is_number(cut_in) and _is_number(cut_out) and not cut_out > cut_in:
        errors.append(f"{path}: cut_out_ms must be above cut_in_ms")


def _unique_package_ids(block: Mapping[str, Any], path: str, errors: List[str]) -> None:
    packages = block.get("cost_buildup_packages")
    if not isinstance(packages, list):
        return
    ids = [p.get("id") for p in packages if isinstance(p, Mapping)]
    if len(ids) != len(set(map(str, ids))):
        errors.append(f"{path}.cost_buildup_packages: package ids must be unique")


_SITE = _Mapping(
    {
        "name": _req(_nonempty_str),
        "location": _req(_nonempty_str),
        "latitude_deg": _opt(_number(ge=-90.0, le=90.0)),
        "longitude_deg": _opt(_number(ge=-180.0, le=180.0)),
        "geometry_file": _opt(_repo_file),
    },
    rules=(_coordinates_together,),
)

_ENVELOPE: Dict[str, _Key] = {
    "site": _req(_SITE),
    "retrieved": _req(_iso_date),
    "sources": _req(_list_of(_nonempty_str)),
    "method_config": _opt(_repo_file),
    "notes": _opt(_nonempty_str),
}

_COMPONENTS = _list_of(_number(ge=0.0))


def _hour_of_day(value: Any, path: str, errors: List[str]) -> None:
    if not (
        isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 23
    ):
        errors.append(f"{path}: must be an integer hour from 0 to 23 (got {value!r})")


_UTC_HOURS = _list_of(_hour_of_day, unique=True)


def _block(keys: Mapping[str, _Key], *rules: Any) -> _Mapping:
    merged: Dict[str, _Key] = dict(_ENVELOPE)
    merged.update(keys)
    return _Mapping(merged, rules=tuple(rules))


def _bool(value: Any, path: str, errors: List[str]) -> None:
    if not isinstance(value, bool):
        errors.append(f"{path}: must be true or false (got {value!r})")


def _unique_ids(key: str) -> Callable[[Mapping[str, Any], str, List[str]], None]:
    def rule(block: Mapping[str, Any], path: str, errors: List[str]) -> None:
        entries = block.get(key)
        if not isinstance(entries, list):
            return
        ids = [str(e.get("id")) for e in entries if isinstance(e, Mapping)]
        if len(ids) != len(set(ids)):
            errors.append(f"{path}.{key}: ids must be unique")

    return rule


def _low_mode_high(value: Any, path: str, errors: List[str]) -> None:
    _Mapping(
        {
            "low": _req(_number(gt=0.0)),
            "mode": _req(_number(gt=0.0)),
            "high": _req(_number(gt=0.0)),
        }
    )(value, path, errors)
    if isinstance(value, Mapping) and all(
        _is_number(value.get(k)) for k in ("low", "mode", "high")
    ):
        if not value["low"] <= value["mode"] <= value["high"]:
            errors.append(f"{path}: must satisfy low <= mode <= high")


def _weights_sum_to_one(block: Mapping[str, Any], path: str, errors: List[str]) -> None:
    values = list(block.values())
    if values and all(_is_number(v) for v in values):
        if not math.isclose(sum(float(v) for v in values), 1.0, abs_tol=1e-9):
            errors.append(f"{path}: weights must sum to 1")


def _export_caps(value: Any, path: str, errors: List[str]) -> None:
    if not isinstance(value, Mapping) or not value:
        errors.append(
            f"{path}: must be a non-empty mapping of reading to cap (MW or null)"
        )
        return
    for name, cap in value.items():
        if not (isinstance(name, str) and name.strip()):
            errors.append(f"{path}: reading names must be non-empty strings")
        if cap is not None:
            _number(gt=0.0)(cap, f"{path}.{name}", errors)


def _any_mapping(value: Any, path: str, errors: List[str]) -> None:
    if not isinstance(value, Mapping):
        errors.append(f"{path}: must be a mapping (got {type(value).__name__})")


def _headline_option_is_a_held_option(
    block: Mapping[str, Any], path: str, errors: List[str]
) -> None:
    """``headline_option`` names one ``held`` option of ``sizes.options`` (#1823)."""
    if "headline_option" in block and "headline_option_applied" in block:
        errors.append(
            f"{path}: headline_option and headline_option_applied are exclusive"
        )
    name = block.get("headline_option")
    if name is None:
        return
    sizes = block.get("sizes")
    options = sizes.get("options") if isinstance(sizes, Mapping) else None
    if not isinstance(options, list):
        return
    match = [o for o in options if isinstance(o, Mapping) and o.get("id") == name]
    if not match:
        errors.append(f"{path}.headline_option: no option has id {name!r}")
    elif match[0].get("operation") != "held":
        errors.append(
            f"{path}.headline_option: option {name!r} must be held to be carried "
            "into the headline KPIs"
        )


#: Battery operating modes for a wind battery option: ``cycled`` daily for revenue, or
#: ``held`` for the black-start function only.
STORAGE_OPERATIONS: Tuple[str, ...] = ("cycled", "held")

_STORAGE_OPTIONS = _block(
    {
        "technology": _req(
            _Mapping(
                {
                    "wind_turbine": _req(
                        _Mapping(
                            {
                                "rated_mw": _req(_number(gt=0.0)),
                                "hub_height_m": _req(_number(gt=0.0)),
                                "rotor_diameter_m": _req(_number(gt=0.0)),
                                "cut_in_ms": _req(_number(gt=0.0)),
                                "cut_out_ms": _req(_number(gt=0.0)),
                                "air_density_kgm3": _req(_number(gt=0.0)),
                                "power_loss_fractions": _req(
                                    _list_of(_number(ge=0.0, lt=1.0))
                                ),
                            },
                            rules=(_cut_out_above_cut_in,),
                        )
                    ),
                    "battery": _req(
                        _Mapping(
                            {
                                "round_trip_efficiency": _req(_number(gt=0.0, le=1.0)),
                                "dc_per_nominal": _req(_number(ge=1.0)),
                                "black_start_reserve_mwh": _req(_number(ge=0.0)),
                                "duration_h_for_tariff": _req(_number(gt=0.0)),
                                "usd_per_kwh": _req(_low_mode_high),
                                "om_usd_per_dc_kwh_year": _req(_number(ge=0.0)),
                            }
                        )
                    ),
                }
            )
        ),
        "hourly_profile": _req(
            _Mapping(
                {
                    "reference_config": _req(_repo_file),
                    "reference_point": _req(_nonempty_str),
                    "transfer_summary": _req(_repo_file),
                    "reference_height_m": _req(_number(gt=0.0)),
                    "high_output_check_mw": _req(_number(gt=0.0)),
                }
            )
        ),
        "sizes": _req(
            _Mapping(
                {
                    "options": _req(
                        _list_of(
                            _Mapping(
                                {
                                    "id": _req(_nonempty_str),
                                    "power_mw": _req(_number(gt=0.0)),
                                    "energy_mwh": _req(_number(gt=0.0)),
                                    "operation": _req(_enum(STORAGE_OPERATIONS)),
                                }
                            )
                        )
                    )
                },
                rules=(_unique_ids("options"),),
            )
        ),
        "tariff": _req(
            _Mapping(
                {
                    "currency": _req(_currency),
                    "wind_components": _req(_COMPONENTS),
                    "storage_priority_components": _req(_COMPONENTS),
                    "storage_other_components": _req(_COMPONENTS),
                    "cross_check_priority_components": _req(_COMPONENTS),
                    "cross_check_other_components": _req(_COMPONENTS),
                    "round_trip_efficiency_basis": _req(_number(gt=0.0, le=1.0)),
                    "contract_years": _req(_positive_int),
                    "priority_window_utc_hours": _req(_UTC_HOURS),
                    "component_check_tolerance": _req(_number(ge=0.0)),
                    "one_time_adjustment_weights": _req(
                        _Mapping(
                            {
                                "lkr_usd": _req(_number(ge=0.0, le=1.0)),
                                "ccpi": _req(_number(ge=0.0, le=1.0)),
                            },
                            rules=(_weights_sum_to_one,),
                        )
                    ),
                }
            )
        ),
        "grid_limits": _req(
            _Mapping(
                {
                    "export_limit_mw": _req(_number(gt=0.0)),
                    "export_cap_readings": _req(_export_caps),
                    "ramp_limit_mw_per_min": _req(_number(gt=0.0)),
                    "illustrative_other_wind_mw": _req(_list_of(_number(ge=0.0))),
                }
            )
        ),
        "firming_supplier": _req(
            _Mapping(
                {
                    "offer_usd_per_dc_kwh": _req(_number(gt=0.0)),
                    "dc_block_usd_per_dc_kwh": _req(_number(gt=0.0)),
                    "ac_skid_usd": _req(_number(gt=0.0)),
                    "ac_skid_mw": _req(_number(gt=0.0)),
                    "ems_usd": _req(_number(ge=0.0)),
                    "install_transport_share": _req(_number(ge=0.0, lt=1.0)),
                    "service_share_of_cif_per_year": _req(_number(ge=0.0, lt=1.0)),
                    "usable_per_dc": _req(_number(gt=0.0, le=1.0)),
                    "smallest_block_dc_mwh": _req(_number(gt=0.0)),
                    "power_cell_premium": _req(_list_of(_number(ge=1.0))),
                }
            )
        ),
        "uncertainty": _req(
            _Mapping({"wind_yield_sigma": _req(_number(ge=0.0, lt=1.0))})
        ),
        "pricing_config": _opt(_repo_file),
        # #1823: carry one held option into the scenario's headline KPIs
        # (analytics.storage_headline). The applied form is written by that step only.
        "headline_option": _opt(_nonempty_str),
        "headline_option_applied": _opt(_any_mapping),
    },
    _headline_option_is_a_held_option,
)


def _sizing_flag(value: Any, path: str, errors: List[str]) -> None:
    if not isinstance(value, bool):
        errors.append(f"{path}: must be true or false (got {value!r})")


def _list_of_mappings(value: Any, path: str, errors: List[str]) -> None:
    """A list, possibly empty, of mappings (an empty list switches the cases off)."""
    if not isinstance(value, list):
        errors.append(f"{path}: must be a list (got {value!r})")
        return
    for i, entry in enumerate(value):
        _any_mapping(entry, f"{path}[{i}]", errors)


def _pv_tables_entry(value: Any, path: str, errors: List[str]) -> None:
    if value == "land_max":
        return
    _positive_int(value, path, errors)


def _optional_limit_mw(value: Any, path: str, errors: List[str]) -> None:
    if value is None:
        return
    _number(gt=0.0)(value, path, errors)


def _max_ratio_not_below_min(
    block: Mapping[str, Any], path: str, errors: List[str]
) -> None:
    lo: Any = block.get("min_dc_ac_ratio")
    hi: Any = block.get("max_dc_ac_ratio")
    if _is_number(lo) and _is_number(hi) and hi < lo:
        errors.append(f"{path}: max_dc_ac_ratio must not be below min_dc_ac_ratio")


def _rte_range_in_order(block: Mapping[str, Any], path: str, errors: List[str]) -> None:
    lo: Any = block.get("rte_low")
    hi: Any = block.get("rte_high")
    if _is_number(lo) and _is_number(hi) and hi < lo:
        errors.append(f"{path}: rte_high must not be below rte_low")


#: One reading of a capacity limit: each limit in MW, or null for no limit of that kind
#: (the keys of :data:`solar_resource.pv_bess_sizing.READING_KEYS`).
_SIZING_READING = _Mapping(
    {
        "max_pv_ac_plus_bess_mw": _req(_optional_limit_mw),
        "max_export_mw": _req(_optional_limit_mw),
        "max_pv_ac_mw": _req(_optional_limit_mw),
        "max_bess_power_mw": _req(_optional_limit_mw),
    }
)


def _sizing_readings(value: Any, path: str, errors: List[str]) -> None:
    """Readings by name, plus ``committed`` naming one of them.

    The names themselves must match the regulatory config's readings; the sizing checks
    that when it runs, because the regulatory config is a separate file.
    """
    if not isinstance(value, Mapping):
        errors.append(f"{path}: must be a mapping (got {type(value).__name__})")
        return
    names = [k for k in value if k != "committed"]
    if not names:
        errors.append(f"{path}: must name at least one reading")
    for name in names:
        if name == "by_reading":
            errors.append(f"{path}.{name}: 'by_reading' is a reserved name")
            continue
        _SIZING_READING(value[name], f"{path}.{name}", errors)
    if "committed" not in value:
        errors.append(f"{path}.committed: required key is missing")
    elif value["committed"] not in names:
        errors.append(
            f"{path}.committed: must name one of the readings {names} "
            f"(got {value['committed']!r})"
        )


_SIZING_SIZE = _Mapping(
    {
        "reading": _req(_nonempty_str),
        "pv_tables": _req(_positive_int),
        "pv_ac_mw": _req(_number(gt=0.0)),
        "bess_power_mw": _req(_number(gt=0.0)),
    }
)


def _sizing_recommendation(value: Any, path: str, errors: List[str]) -> None:
    """The recorded choices by role; ``committed`` is the size the scenario carries."""
    if not isinstance(value, Mapping) or not value:
        errors.append(f"{path}: must be a non-empty mapping of sizes by role")
        return
    if "committed" not in value:
        errors.append(f"{path}.committed: required key is missing")
    for role, size in value.items():
        _SIZING_SIZE(size, f"{path}.{role}", errors)


_SOLAR_STORAGE_SIZING = _block(
    {
        # The unit, pricing and regulatory configs the sizing reads (file references).
        "unit_config": _req(_repo_file),
        "pricing_config": _req(_repo_file),
        "regulatory_config": _req(_repo_file),
        # Dotted paths into the unit config, each of which must already exist there (the
        # sizing checks the paths when it runs).
        "unit_overrides": _req(_any_mapping),
        "grid": _req(
            _Mapping(
                {
                    "pv_tables": _req(_list_of(_pv_tables_entry, unique=True)),
                    "pv_ac_mw": _req(_list_of(_number(gt=0.0), unique=True)),
                    "min_dc_ac_ratio": _req(_number(gt=0.0)),
                    "max_dc_ac_ratio": _req(_number(gt=0.0)),
                    "bess_power_mw": _req(_list_of(_number(gt=0.0), unique=True)),
                    "bess_duration_h": _req(_number(gt=0.0, le=24.0)),
                },
                rules=(_max_ratio_not_below_min,),
            )
        ),
        "readings": _req(_sizing_readings),
        "uncertainty": _req(
            _Mapping(
                {
                    "yield_sigma_pct": _req(_number(ge=0.0)),
                    "yield_clip_sigma": _req(_number(gt=0.0)),
                    "rte_low": _req(_number(gt=0.0, le=1.0)),
                    "rte_high": _req(_number(gt=0.0, le=1.0)),
                    "residual_fade_pct_per_year": _req(
                        _Mapping(
                            {
                                "low": _req(_number(ge=0.0)),
                                "mode": _req(_number(ge=0.0)),
                                "high": _req(_number(ge=0.0)),
                            }
                        )
                    ),
                },
                rules=(_rte_range_in_order,),
            )
        ),
        "battery_health": _req(
            _Mapping(
                {
                    "fade_pct_per_year": _req(_number(ge=0.0)),
                    "fade_basis": _req(_nonempty_str),
                    "augment_below_soh": _req(_number(gt=0.0, le=1.0)),
                    "restore_to_soh": _req(_number(gt=0.0, le=1.0)),
                    "augmentation_usd_per_kwh": _req(_number(ge=0.0)),
                    "augmentation_basis": _req(_nonempty_str),
                    "replaces_price_reserve": _req(_sizing_flag),
                }
            )
        ),
        "plant": _req(
            _Mapping(
                {
                    "grid_civils_development_usd": _req(_number(ge=0.0)),
                    "fixed_opex_usd_per_year": _req(_number(ge=0.0)),
                    "bess_dc_per_nominal": _req(_number(ge=1.0)),
                }
            )
        ),
        "curtailment_scenario": _req(
            _Mapping(
                {
                    "enabled": _req(_sizing_flag),
                    "daytime_export_curtailment_fraction": _req(
                        _number(ge=0.0, le=1.0)
                    ),
                    "basis": _req(_nonempty_str),
                }
            )
        ),
        # The one-at-a-time cases and break-even inputs are checked case by case when the
        # sizing runs (solar_resource.pv_bess_sizing).
        "sensitivities": _req(
            _Mapping(
                {
                    "round_trip_efficiency": _req(_number(gt=0.0, le=1.0)),
                    "one_at_a_time": _req(_list_of_mappings),
                    "break_even": _req(_list_of_mappings),
                }
            )
        ),
        "recommendation": _req(_sizing_recommendation),
        # The run's stated limitations, listed in its summary.
        "limitations": _req(_list_of(_nonempty_str)),
    }
)


def _downside_not_above_p50(
    block: Mapping[str, Any], path: str, errors: List[str]
) -> None:
    p50: Any = block.get("p50_gwh")
    downside: Any = block.get("assumed_downside_gwh")
    if _is_number(p50) and _is_number(downside) and downside > p50:
        errors.append(f"{path}: assumed_downside_gwh must not exceed p50_gwh")


def _fx_window_dates_in_order(
    block: Mapping[str, Any], path: str, errors: List[str]
) -> None:
    start: Any = block.get("start_date")
    end: Any = block.get("end_date")
    try:
        if str(start) >= str(end):
            errors.append(f"{path}: start_date must be before end_date")
    except TypeError:
        pass


#: Scenario inputs a named financing sensitivity may override (the screening reads the
#: rest from the scenario itself).
_FINANCING_SENSITIVITY = _Mapping(
    {
        "id": _req(_nonempty_str),
        "description": _req(_nonempty_str),
        "capex_usd": _opt(_number(gt=0.0)),
        "opex_usd_equivalent_year1": _opt(_number(ge=0.0)),
        "tariff_fixed_lkr_per_kwh": _opt(_number(ge=0.0)),
        "tariff_om_lkr_per_kwh": _opt(_number(ge=0.0)),
        "fx_close_lkr_per_usd": _opt(_number(gt=0.0)),
        "fx_depreciation_decimal": _opt(_number(gt=-1.0, lt=1.0)),
    }
)

_FX_OBSERVATION = _Mapping(
    {
        "date": _req(_iso_date),
        "lkr_per_usd": _req(_number(gt=0.0)),
        "type": _req(_nonempty_str),
        "is_assumption": _req(_bool),
        "evidence_status": _req(_nonempty_str),
    }
)

_FX_WINDOW = _Mapping(
    {
        "label": _req(_nonempty_str),
        "start": _req(_number(gt=0.0)),
        "end": _req(_number(gt=0.0)),
        "start_date": _req(_iso_date),
        "end_date": _req(_iso_date),
        "is_assumption": _req(_bool),
        "evidence_status": _req(_nonempty_str),
    },
    rules=(_fx_window_dates_in_order,),
)

_FINANCING_SCREENING = _block(
    {
        "label": _req(_literal(SCREENING_LABEL)),
        "debt": _req(
            _Mapping(
                {
                    "dfi_share": _req(_number(ge=0.0, le=1.0)),
                    "dfi_rate_decimal": _req(_number(ge=0.0, lt=1.0)),
                    "local_rate_decimal": _req(_number(ge=0.0, lt=1.0)),
                    "dfi_tenor_years": _req(_positive_int),
                    "local_tenor_years": _req(_positive_int),
                    "lender_tail_years": _req(_nonnegative_int),
                    "annual_credit_fee_decimal": _opt(_number(ge=0.0, lt=1.0)),
                }
            )
        ),
        "opex": _req(
            _Mapping(
                {
                    "usd_share": _req(_number(ge=0.0, le=1.0)),
                    "usd_escalation_decimal": _req(_number(gt=-1.0, lt=1.0)),
                    "local_escalation_decimal": _req(_number(gt=-1.0, lt=1.0)),
                }
            )
        ),
        # Stated only for a flat-tariff scenario: a scenario with tariff.om_indexation sets
        # the O&M part's escalation itself, and the screening refuses both or neither.
        "tariff_om_escalation_decimal": _opt(_number(gt=-1.0, lt=1.0)),
        "min_p50_dscr": _req(_number(gt=0.0)),
        "min_downside_dscr": _req(_number(gt=0.0)),
        "average_p50_dscr": _req(_number(gt=0.0)),
        "allowance_years": _req(_positive_int),
        "fx_shock": _req(
            _Mapping(
                {
                    "shock_decimal": _req(_number(ge=0.0, lt=1.0)),
                    "operating_year": _req(_positive_int),
                }
            )
        ),
        "generation": _req(
            _Mapping(
                {
                    "p50_gwh": _req(_number(gt=0.0)),
                    "assumed_downside_gwh": _req(_number(gt=0.0)),
                    "basis_note": _req(_nonempty_str),
                },
                rules=(_downside_not_above_p50,),
            )
        ),
        "tenor_variants": _opt(
            _list_of(
                _Mapping(
                    {
                        "id": _req(_nonempty_str),
                        "dfi_tenor_years": _req(_positive_int),
                        "ppa_years": _req(_positive_int),
                        "lender_tail_years": _req(_nonnegative_int),
                    }
                )
            )
        ),
        "sensitivities": _opt(_list_of(_FINANCING_SENSITIVITY)),
        "fixed_debt_stress": _opt(
            _Mapping(
                {
                    "held_debt_usd": _req(_number(gt=0.0)),
                    "operating_year": _req(_positive_int),
                    "depreciation_rates": _req(
                        _list_of(_number(gt=-1.0, lt=1.0), unique=True)
                    ),
                    "shock_decimals": _req(
                        _list_of(_number(ge=0.0, lt=1.0), unique=True)
                    ),
                }
            )
        ),
        "fx_history": _opt(
            _Mapping(
                {
                    "observations": _req(_list_of(_FX_OBSERVATION)),
                    "cagr_windows": _opt(_list_of(_FX_WINDOW)),
                }
            )
        ),
    },
    _unique_ids("tenor_variants"),
    _unique_ids("sensitivities"),
)

_PACKAGE = _Mapping(
    {
        "id": _req(_nonempty_str),
        "package": _req(_nonempty_str),
        "route": _req(_enum(COST_BUILDUP_ROUTES)),
        "quoted_amount_usd": _req(_optional_number_ge0),
    }
)

_EQUIPMENT_COST_PARITY = _block(
    {
        "energy_summary": _req(_repo_file),
        "capex_config": _req(_repo_file),
        "operating_life_years": _req(_positive_int),
        "loss_retention_factors": _req(_list_of(_number(gt=0.0, le=1.0))),
        "benchmark": _req(
            _Mapping(
                {
                    "name": _req(_nonempty_str),
                    "source": _req(_nonempty_str),
                    "status": _req(_nonempty_str),
                    "turbine_count": _req(_positive_int),
                    "rated_capacity_mw": _req(_number(gt=0.0)),
                    "historical_unreconciled_capacity_mw": _opt(_number(gt=0.0)),
                    "turbine_supply_usd": _req(_number(gt=0.0)),
                    "annual_aep_mwh": _req(_number(gt=0.0)),
                    "operating_life_years": _req(_positive_int),
                }
            )
        ),
        "sensitivity_premium_pct": _req(_list_of(_number(gt=-100.0), unique=True)),
        "cost_buildup_packages": _req(_list_of(_PACKAGE)),
    },
    _unique_package_ids,
)

_BLOCK_CONTRACTS: Dict[str, _Mapping] = {
    "storage_options": _STORAGE_OPTIONS,
    "solar_storage_sizing": _SOLAR_STORAGE_SIZING,
    "financing_screening": _FINANCING_SCREENING,
    "equipment_cost_parity": _EQUIPMENT_COST_PARITY,
}


# ------------------------------------------------------------------------ public API


def allowed_keys(block: str) -> List[str]:
    """Return the sorted top-level keys a block may carry."""
    return sorted(_BLOCK_CONTRACTS[block].keys)


def declared_site_analysis_blocks(config: Mapping[str, Any]) -> List[str]:
    """Return the site-analysis blocks a scenario declares, in canonical order."""
    if not isinstance(config, Mapping):
        return []
    return [name for name in SITE_ANALYSIS_BLOCKS if name in config]


def validate_site_analysis_blocks(config: Mapping[str, Any], errors: List[str]) -> None:
    """Append one message per problem in every declared block; absent blocks are skipped."""
    for name in declared_site_analysis_blocks(config):
        _BLOCK_CONTRACTS[name](config[name], name, errors)


def resolve_site_analysis_block(
    config: Mapping[str, Any], block: str
) -> Optional[Mapping[str, Any]]:
    """Return a scenario's validated block, or ``None`` when the scenario has none.

    Raises:
        KeyError: ``block`` is not one of :data:`SITE_ANALYSIS_BLOCKS`.
        ValueError: the block is present but malformed; the message lists every problem.
    """
    if block not in _BLOCK_CONTRACTS:
        raise KeyError(
            f"unknown site-analysis block {block!r}; expected one of "
            f"{list(SITE_ANALYSIS_BLOCKS)}"
        )
    if not isinstance(config, Mapping) or block not in config:
        return None
    errors: List[str] = []
    _BLOCK_CONTRACTS[block](config[block], block, errors)
    if errors:
        raise ValueError(f"scenario block {block!r} is malformed: " + "; ".join(errors))
    resolved: Mapping[str, Any] = config[block]
    return resolved


def plan_site_analyses(config: Mapping[str, Any]) -> Dict[str, Dict[str, str]]:
    """List every site analysis for a scenario, and whether it applies.

    Every analysis is on by default (owner ruling, 2026-11-16), so the plan always holds all
    four, in :data:`SITE_ANALYSIS_BLOCKS` order. An analysis whose block the scenario declares
    is ``run``; one without its block is ``not_applicable``, with the reason.

    Raises:
        ValueError: a declared block is malformed; the message lists every problem.
    """
    plan: Dict[str, Dict[str, str]] = {}
    for block in SITE_ANALYSIS_BLOCKS:
        entry = {"analysis": SITE_ANALYSIS_NAMES[block]}
        if resolve_site_analysis_block(config, block) is None:
            entry["status"] = STATUS_NOT_APPLICABLE
            entry["reason"] = f"the scenario declares no {block} block"
        else:
            entry["status"] = STATUS_RUN
        plan[block] = entry
    return plan


__all__ = [
    "SITE_ANALYSIS_NAMES",
    "STATUS_NOT_APPLICABLE",
    "STATUS_RUN",
    "plan_site_analyses",
    "COST_BUILDUP_ROUTES",
    "SCREENING_LABEL",
    "STORAGE_OPERATIONS",
    "SITE_ANALYSIS_BLOCKS",
    "allowed_keys",
    "declared_site_analysis_blocks",
    "resolve_site_analysis_block",
    "validate_site_analysis_blocks",
]

"""Wind-resource → v14 cashflow scenario adapter.

Sprint 19 (W.3) — integration bridge between :mod:`wind_resource.wind_pipeline`
and the canonical v14 finance pipeline.

Design constraints
------------------
1. **Pure function.** No filesystem I/O, no network calls, no logging side
   effects. Callers own JSON I/O.
2. **No heavy imports.** This module deliberately does *not* import
   :mod:`cdsapi`, :mod:`xarray`, or :mod:`netcdf4`. Finance consumers must be
   able to import this adapter without installing the ``[wind]`` extra.
3. **Lender-defensible defaults.** Default ``adapter_mode='fill_if_absent'``
   refuses to silently overwrite existing scenario values; instead it
   validates alignment and raises on drift exceeding ``tolerance_pct``.

Adapter modes
-------------
``overwrite``
    Wind export wins. Every mapped field in the scenario dict is replaced
    with the wind-derived value. Use when the wind run is the canonical
    source of truth and the scenario YAML is a build artifact.

``fill_if_absent`` (default)
    Where the scenario already carries a value, the adapter validates that
    the wind export agrees within ``tolerance_pct``; mismatch raises
    :class:`WindAdapterDriftError`. Where the scenario is silent, the
    wind-derived value is written. Use for lender-grade runs where the YAML
    is the human-curated, audit-trailed input and the wind export acts as a
    guardrail.

``validate_only``
    Never writes. Every mapped field must already exist in the scenario and
    agree with the wind export within tolerance; any missing field or any
    drift raises :class:`WindAdapterDriftError`. Use in CI to prove that an
    approved scenario YAML is still consistent with the latest wind run.

Resolution-order note
---------------------
``finance.cashflow_v14_params._build_cashflow_parameters`` reads
``capacity_factor`` from the first non-empty location in this priority
order::

    project.capacity_factor_pct   (1)
    project.capacity_factor       (2)  ← canonical lender-case home
    production.capacity_factor_net (3)
    production.capacity_factor    (4)
    parameters.capacity_factor_pct (5)
    parameters.capacity_factor    (6)
    capacity_factor_pct           (7)
    capacity_factor               (8)

The adapter writes to ``project.capacity_factor`` because that is the slot
the canonical lender scenarios already occupy; writing to a lower-priority
slot would be silently shadowed.

Unit conventions
----------------
``WindPipeline.export_for_cashflow_model`` reports ``capacity_factor_percent``
as a *percentage* (e.g. ``42.8``). v14 scenarios store the decimal
(``0.428``) at ``project.capacity_factor``. The adapter normalises to
decimal before writing or comparing.

Defect references
-----------------
- W3 — this module is the adapter
- W6 — the round-trip test in ``tests/wind/test_cashflow_adapter.py``
  proves alignment within ±0.5%
"""

from __future__ import annotations

import copy
from typing import Any, Literal, Mapping, MutableMapping

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = [
    "AdapterMode",
    "DEFAULT_TOLERANCE_PCT",
    "WindAdapterDriftError",
    "WindCashflowExport",
    "wind_export_to_scenario_patch",
]


AdapterMode = Literal["overwrite", "fill_if_absent", "validate_only"]

DEFAULT_TOLERANCE_PCT: float = 0.5
"""Default acceptable drift in percent between wind-derived and YAML values.

Sprint 19 design decision (round-trip test W.4d) — chosen to accommodate
year-1 degradation application and grid-loss rounding while still catching
genuine logic drift. Configurable per-call via ``tolerance_pct``.
"""


class WindAdapterDriftError(ValueError):
    """Raised when wind-export values disagree with scenario YAML beyond tolerance.

    Carries structured detail (field, wind value, scenario value, drift
    percent, tolerance) so CI can fail loudly with an actionable message
    rather than a generic ValueError.
    """

    def __init__(
        self,
        field: str,
        wind_value: float | None,
        scenario_value: float | None,
        drift_pct: float | None,
        tolerance_pct: float,
        mode: str,
    ) -> None:
        self.field = field
        self.wind_value = wind_value
        self.scenario_value = scenario_value
        self.drift_pct = drift_pct
        self.tolerance_pct = tolerance_pct
        self.mode = mode
        if drift_pct is None:
            msg = (
                f"[{mode}] field '{field}': scenario value missing "
                f"(wind_value={wind_value!r}, scenario_value={scenario_value!r})"
            )
        else:
            msg = (
                f"[{mode}] field '{field}': drift {drift_pct:.3f}% exceeds "
                f"tolerance {tolerance_pct:.3f}% "
                f"(wind_value={wind_value!r}, scenario_value={scenario_value!r})"
            )
        super().__init__(msg)


class WindCashflowExport(BaseModel):
    """Typed view of ``WindPipeline.export_for_cashflow_model`` output.

    Validates the shape of the wind export at the adapter boundary, so
    downstream code can rely on field presence and numeric types. Extra keys
    are tolerated (``extra='allow'``) because the producer may add fields
    over time; the adapter only consumes the documented surface.
    """

    model_config = ConfigDict(extra="allow", frozen=True)

    scenario: Literal["P50", "P75", "P90"]
    annual_generation_mwh: float = Field(..., gt=0.0)
    capacity_factor_percent: float = Field(..., gt=0.0, le=100.0)
    revenue_annual_usd: float = Field(..., ge=0.0)
    revenue_cumulative_usd: float = Field(..., ge=0.0)
    project_capacity_mw: float = Field(..., gt=0.0)
    num_turbines: int = Field(..., gt=0)
    rated_capacity_per_turbine_kw: float = Field(..., gt=0.0)
    ppa_years: int = Field(..., gt=0)
    tariff_lkr_per_kwh: float = Field(..., gt=0.0)
    exchange_rate_lkr_usd: float = Field(..., gt=0.0)

    @field_validator("capacity_factor_percent")
    @classmethod
    def _cf_sane(cls, v: float) -> float:
        # Defensive: WindPipeline emits CF in percent (e.g. 42.8). A value
        # ≤ 1.0 almost certainly indicates the producer accidentally wrote a
        # decimal — refuse rather than silently halve the project economics.
        if v <= 1.0:
            raise ValueError(
                f"capacity_factor_percent={v} looks like a decimal; "
                "WindPipeline export contract is *percent* (e.g. 42.8)."
            )
        return v


# ---------------------------------------------------------------------------
# Field mapping table
#
# Each entry: (wind_export_attr, scenario_path_tuple, transform, label)
#  - wind_export_attr: attribute name on the validated WindCashflowExport
#  - scenario_path_tuple: nested key path in the scenario dict to read/write
#  - transform: callable applied to the wind value before write/compare
#                (used to convert CF percent -> decimal, etc.)
#  - label: human-readable name for error messages
#
# Order is significant only for deterministic error reporting; modes do not
# short-circuit, so a single call surfaces every drifting field at once is
# *not* implemented — first failure raises. This matches the lender-grade
# "fail fast" preference and keeps the contract small.
# ---------------------------------------------------------------------------

_FIELD_MAP: tuple[tuple[str, tuple[str, ...], Any, str], ...] = (
    (
        "project_capacity_mw",
        ("project", "capacity_mw"),
        lambda x: float(x),
        "project.capacity_mw",
    ),
    (
        "capacity_factor_percent",
        ("project", "capacity_factor"),
        lambda x: float(x) / 100.0,  # percent -> decimal
        "project.capacity_factor",
    ),
    (
        "tariff_lkr_per_kwh",
        ("tariff", "lkr_per_kwh"),
        lambda x: float(x),
        "tariff.lkr_per_kwh",
    ),
    (
        "exchange_rate_lkr_usd",
        ("fx", "start_lkr_per_usd"),
        lambda x: float(x),
        "fx.start_lkr_per_usd",
    ),
)

#: Attributes in :data:`_FIELD_MAP` that carry COMMERCIAL (not physical) values.
#: The wind run is authoritative for PHYSICAL resource (capacity, capacity factor)
#: but NOT for tariff/FX — those are commercial inputs owned by the scenario /
#: wizard, and a (possibly stale) wind export must never overwrite or veto them
#: (#996 Problem #2; the solar adapter carries no commercial fields at all). A
#: caller on the live location-assessment path passes ``physical_only=True`` to
#: write/validate the physical slots only.
_COMMERCIAL_ATTRS: frozenset[str] = frozenset(
    {"tariff_lkr_per_kwh", "exchange_rate_lkr_usd"}
)


def _get_nested(d: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    """Return d[path[0]][path[1]]... or ``None`` if any segment is missing.

    Treats an empty mapping at an intermediate segment as a hit (returns the
    empty mapping), matching the convention used elsewhere in v14.
    """
    cur: Any = d
    for key in path:
        if not isinstance(cur, Mapping) or key not in cur:
            return None
        cur = cur[key]
    return cur


def _set_nested(d: MutableMapping[str, Any], path: tuple[str, ...], value: Any) -> None:
    """Set d[path[0]][path[1]]... = value, creating intermediate dicts."""
    cur: MutableMapping[str, Any] = d
    for key in path[:-1]:
        nxt = cur.get(key)
        if not isinstance(nxt, MutableMapping):
            nxt = {}
            cur[key] = nxt
        cur = nxt
    cur[path[-1]] = value


def _drift_pct(wind_value: float, scenario_value: float) -> float:
    """Symmetric relative drift in percent.

    Uses ``max(abs(a), abs(b))`` as the denominator so a zero on either side
    doesn't divide by zero, and so the result is the same regardless of
    which value is "expected".
    """
    denom = max(abs(wind_value), abs(scenario_value))
    if denom == 0.0:
        return 0.0
    return 100.0 * abs(wind_value - scenario_value) / denom


def wind_export_to_scenario_patch(
    export_dict: Mapping[str, Any],
    scenario_yaml_dict: Mapping[str, Any],
    *,
    scenario_name: str = "P75",
    adapter_mode: AdapterMode = "fill_if_absent",
    tolerance_pct: float = DEFAULT_TOLERANCE_PCT,
    physical_only: bool = False,
) -> dict[str, Any]:
    """Apply a wind export to a v14 scenario dict under the chosen mode.

    Parameters
    ----------
    export_dict
        Output of :meth:`wind_resource.wind_pipeline.WindPipeline.export_for_cashflow_model`.
        Validated against :class:`WindCashflowExport` at the boundary.
    scenario_yaml_dict
        Parsed v14 scenario YAML (e.g. ``scenarios/dutchbay_lendercase_2025Q4.yaml``).
        Deep-copied internally; the input mapping is **not** mutated.
    scenario_name
        Sanity check — must match ``export_dict['scenario']``. Surfaces a
        clear error if the caller asks for P50 but passes a P75 export.
    adapter_mode
        ``'overwrite'`` | ``'fill_if_absent'`` (default) | ``'validate_only'``.
        See module docstring for semantics.
    tolerance_pct
        Acceptable symmetric relative drift in percent. Default 0.5.
    physical_only
        When ``True``, touch only the PHYSICAL resource slots
        (``project.capacity_mw``, ``project.capacity_factor``) and leave the
        COMMERCIAL slots (``tariff.lkr_per_kwh``, ``fx.start_lkr_per_usd``)
        entirely untouched — no write, no drift check. The wind run is
        authoritative for physical resource, never for tariff/FX (#996 Problem
        #2); the live location-assessment path sets this so a possibly-stale
        export cannot overwrite or veto the scenario's own commercial inputs.
        Default ``False`` (legacy full-map behaviour, incl. commercial slots).

    Returns
    -------
    dict
        New scenario dict (independent of the input). For ``validate_only``
        this is a deep copy of the input with the ``wind_resource``
        metadata block updated; no economics fields are changed.

    Raises
    ------
    WindAdapterDriftError
        In ``fill_if_absent`` mode: a present scenario value disagrees
        beyond ``tolerance_pct``. In ``validate_only`` mode: any missing or
        drifting field. In ``overwrite`` mode: never raised on drift (the
        whole point is to replace), but Pydantic validation of the export
        may still raise :class:`pydantic.ValidationError`.
    ValueError
        ``scenario_name`` does not match ``export_dict['scenario']`` or
        ``adapter_mode`` is unrecognised.
    """
    # --- 0. argument hygiene ---------------------------------------------
    if adapter_mode not in ("overwrite", "fill_if_absent", "validate_only"):
        raise ValueError(
            f"adapter_mode must be one of overwrite|fill_if_absent|validate_only; "
            f"got {adapter_mode!r}"
        )

    # --- 1. validate the export ------------------------------------------
    export = WindCashflowExport.model_validate(export_dict)

    if export.scenario != scenario_name:
        raise ValueError(
            f"scenario_name={scenario_name!r} but export carries "
            f"scenario={export.scenario!r}; refusing to mix P-levels"
        )

    # --- 2. deep-copy so we never mutate caller's dict --------------------
    patched: dict[str, Any] = copy.deepcopy(dict(scenario_yaml_dict))

    # --- 3. per-field merge under the requested mode ---------------------
    for attr, path, transform, label in _FIELD_MAP:
        if physical_only and attr in _COMMERCIAL_ATTRS:
            # Live location-assessment path: the wind run owns physical resource
            # only; the scenario's own tariff/FX stay authoritative (#996 P2).
            continue
        wind_raw = getattr(export, attr)
        wind_value = transform(wind_raw)
        scenario_value = _get_nested(patched, path)

        if adapter_mode == "overwrite":
            _set_nested(patched, path, wind_value)
            continue

        if scenario_value is None:
            if adapter_mode == "validate_only":
                raise WindAdapterDriftError(
                    field=label,
                    wind_value=wind_value,
                    scenario_value=None,
                    drift_pct=None,
                    tolerance_pct=tolerance_pct,
                    mode=adapter_mode,
                )
            # fill_if_absent: write
            _set_nested(patched, path, wind_value)
            continue

        # scenario_value is present — both modes (fill_if_absent and
        # validate_only) compare against tolerance.
        try:
            scenario_value_f = float(scenario_value)
        except (TypeError, ValueError):
            raise WindAdapterDriftError(
                field=label,
                wind_value=wind_value,
                scenario_value=scenario_value,
                drift_pct=None,
                tolerance_pct=tolerance_pct,
                mode=adapter_mode,
            ) from None

        drift = _drift_pct(wind_value, scenario_value_f)
        if drift > tolerance_pct:
            raise WindAdapterDriftError(
                field=label,
                wind_value=wind_value,
                scenario_value=scenario_value_f,
                drift_pct=drift,
                tolerance_pct=tolerance_pct,
                mode=adapter_mode,
            )
        # within tolerance — leave the scenario value untouched (lender
        # YAML stays canonical), no write needed.

    # --- 4. always write the wind_resource provenance metadata -----------
    # Even in validate_only mode we annotate provenance so artifacts can
    # later be traced back to a wind run. This is metadata, not economics,
    # so it doesn't violate the "never writes" promise of validate_only —
    # the promise applies to fields cashflow_v14 consumes.
    wind_meta_existing = patched.get("wind_resource")
    if not isinstance(wind_meta_existing, dict):
        wind_meta_existing = {}
        patched["wind_resource"] = wind_meta_existing
    wind_meta_existing.update(
        {
            "source": "frozen_export",
            "scenario": export.scenario,
            "net_aep_mwh": float(export.annual_generation_mwh),
            "capacity_factor_decimal": float(export.capacity_factor_percent) / 100.0,
            "adapter_mode": adapter_mode,
            "adapter_tolerance_pct": float(tolerance_pct),
            "num_turbines": int(export.num_turbines),
            "rated_capacity_per_turbine_kw": float(
                export.rated_capacity_per_turbine_kw
            ),
            "ppa_years": int(export.ppa_years),
        }
    )

    return patched

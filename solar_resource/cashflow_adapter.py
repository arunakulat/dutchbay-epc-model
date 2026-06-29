"""Solar-resource → v14 cashflow scenario adapter (the OVERWRITE finance bridge).

Photovoltaic analogue of :mod:`wind_resource.cashflow_adapter`. Bridges a *frozen*
solar AEP export (the serialized output of :func:`solar_resource.pv_producer.compute_solar_aep`)
into the canonical v14 finance pipeline by patching the hybrid scenario's per-technology
generation block.

Frozen-export design (why finance never imports ``pvlib``)
----------------------------------------------------------
This module is a **pure function over plain dicts** — it does NOT import
:mod:`pvlib` or call :func:`compute_solar_aep`. The expensive physics run happens
once, offline, behind the optional ``[solar]`` extra; its result is serialized to a
small export dict (see :func:`build_solar_cashflow_export`) and frozen into the
scenario. Finance then reads a static number, exactly as the wind side consumes a
frozen ``WindPipeline.export_for_cashflow_model`` dict rather than re-running PyWake,
and exactly as #237 froze the ERA5-fitted Weibull (8.199 / 2.665) into the scenario.
The base install and every CI lane therefore run the hybrid finance case with no
``pvlib`` dependency.

Relationship to the VALIDATE producer
-------------------------------------
:mod:`solar_resource.pv_producer` exposes a *VALIDATE-only* surface
(:func:`validate_declared_solar_cf`) that cross-checks a config-declared P50 CF and
never mutates it — the photovoltaic analogue of the ERA5 / ARCO wind VALIDATE guard.
This adapter is the complementary *OVERWRITE* surface: when the modelled CF is chosen
as the financed driver, it replaces the declared per-tech CF. The two are deliberate
opposites — one guards a human-curated P50, the other makes the modelled P50 the
billed quantity — selected per call via ``adapter_mode``.

What it writes (and why the headline is recomputed)
---------------------------------------------------
Unlike the wind adapter (which writes ``project.capacity_factor`` directly because a
wind-only project's headline *is* the wind CF), a hybrid bills each technology off its
own ``generation.technologies.<tech>.capacity_factor`` (the M3 per-tech cashflow). So
this adapter writes:

    generation.technologies.<tech>.capacity_mw      (identity / commercial nameplate)
    generation.technologies.<tech>.capacity_factor  (the financed driver — DECIMAL)
    generation.technologies.<tech>.aep_gwh          (reporting split)

and then **recomputes the blended** ``project.capacity_factor`` from the per-tech sum,
because the engine cross-checks (``finance.cashflow_v14_production.resolve_tech_generation_specs``,
±1%) and the load-time guard (``analytics.aep_reconciliation``) both require::

    Σ_tech (capacity_mw · capacity_factor)  ==  project.capacity_mw · project.capacity_factor

Storage technologies (``type: bess`` and any future ``finance.tech_types.STORAGE_TYPES``)
are excluded from the blend exactly as the engine excludes them — the predicate is
reused, not re-derived, so the recomputed headline tracks the engine's billed basis.
It does NOT touch ``expected_results`` / ``resource.aep_summary_path``: those are the
*independent* bankable references the reconciliation guard checks the headline against,
and rewriting them from ``capacity × CF`` would disarm the guard. Re-baselining the
bankable reference is a deliberate, audited scenario edit, not an adapter side effect.

Unit convention
---------------
``SolarAEPResult.capacity_factor`` (and therefore the export) is a **decimal** against
the DC nameplate (e.g. ``0.179``), matching ``generation.technologies.solar.capacity_factor``.
There is NO percent→decimal transform here (contrast the wind export, which reports CF
in percent). The validator rejects a value > 1.0 as a likely mis-scaled percent.

Adapter modes
-------------
``overwrite``
    Solar export wins. Every mapped per-tech field is replaced and the blended
    headline recomputed. Use when the modelled solar run is the canonical financed
    source and the scenario YAML is a build artifact.

``fill_if_absent`` (default)
    Where the scenario already carries a per-tech value, validate that the export
    agrees within ``tolerance_pct``; mismatch raises :class:`SolarAdapterDriftError`.
    Where the scenario is silent, write the export value. The headline is recomputed
    only if a write occurred.

``validate_only``
    Never writes economics. Every mapped field must already exist and agree within
    tolerance; any missing field or drift raises. Use in CI to prove a frozen scenario
    YAML still agrees with the latest solar run (the symmetric of the wind/ERA5 guard).
"""

from __future__ import annotations

import copy
from typing import Any, Literal, Mapping, MutableMapping

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = [
    "SolarAdapterMode",
    "DEFAULT_TOLERANCE_PCT",
    "SolarAdapterDriftError",
    "SolarCashflowExport",
    "build_solar_cashflow_export",
    "solar_export_to_scenario_patch",
]


SolarAdapterMode = Literal["overwrite", "fill_if_absent", "validate_only"]

DEFAULT_TOLERANCE_PCT: float = 0.5
"""Default acceptable drift (percent) between solar-derived and YAML per-tech values.

Mirrors the wind adapter's default. Chosen to catch genuine logic drift while
tolerating the small rounding between a frozen export and a re-authored YAML;
configurable per call via ``tolerance_pct``.
"""

#: Tolerance (fraction) on the export's DC nameplate vs the scenario's per-tech
#: ``capacity_mw`` identity check. Capacity is a committed commercial nameplate, so a
#: real mismatch (e.g. applying a 100 MW export to a 50 MW slot) must fail loud in
#: every mode; a hair of rounding is tolerated.
_CAPACITY_IDENTITY_TOL: float = 1e-6


class SolarAdapterDriftError(ValueError):
    """Raised when a solar-export value disagrees with the scenario beyond tolerance.

    Carries structured detail (field, solar value, scenario value, drift percent,
    tolerance, mode) so CI fails loud with an actionable message rather than a generic
    ``ValueError``.
    """

    def __init__(
        self,
        field: str,
        solar_value: float | None,
        scenario_value: float | None,
        drift_pct: float | None,
        tolerance_pct: float,
        mode: str,
    ) -> None:
        self.field = field
        self.solar_value = solar_value
        self.scenario_value = scenario_value
        self.drift_pct = drift_pct
        self.tolerance_pct = tolerance_pct
        self.mode = mode
        if drift_pct is None:
            msg = (
                f"[{mode}] field '{field}': scenario value missing "
                f"(solar_value={solar_value!r}, scenario_value={scenario_value!r})"
            )
        else:
            msg = (
                f"[{mode}] field '{field}': drift {drift_pct:.3f}% exceeds "
                f"tolerance {tolerance_pct:.3f}% "
                f"(solar_value={solar_value!r}, scenario_value={scenario_value!r})"
            )
        super().__init__(msg)


class SolarCashflowExport(BaseModel):
    """Typed view of a frozen solar AEP export.

    Validates the shape at the adapter boundary so downstream code can rely on field
    presence and numeric types. Extra keys are tolerated (``extra='allow'``) because the
    producer may add provenance fields over time; the adapter only consumes the
    documented surface. Build one from a :class:`solar_resource.pv_producer.SolarAEPResult`
    via :func:`build_solar_cashflow_export`.
    """

    model_config = ConfigDict(extra="allow", frozen=True)

    scenario: Literal["P50", "P75", "P90"]
    technology: str = "solar"
    annual_energy_gwh: float = Field(..., gt=0.0)
    capacity_factor: float = Field(..., gt=0.0, le=1.0)  # DECIMAL against DC nameplate
    dc_capacity_mw: float = Field(..., gt=0.0)  # MWp — identity-checked vs scenario
    specific_yield_kwh_per_kwp: float | None = Field(default=None, gt=0.0)

    @field_validator("capacity_factor")
    @classmethod
    def _cf_is_decimal(cls, v: float) -> float:
        # Defensive mirror of the wind validator, inverted: the solar producer emits CF
        # as a DECIMAL (e.g. 0.179). A value > 1.0 almost certainly means a percent was
        # passed by mistake — refuse rather than book ~18x the real solar generation.
        if v > 1.0:
            raise ValueError(
                f"capacity_factor={v} looks like a percent; the solar export contract "
                "is a *decimal* against the DC nameplate (e.g. 0.179)."
            )
        return v


def build_solar_cashflow_export(
    result: Any,
    *,
    dc_capacity_mw: float,
    scenario: Literal["P50", "P75", "P90"] = "P50",
    technology: str = "solar",
) -> dict[str, Any]:
    """Serialize a :class:`SolarAEPResult` + nameplate into a frozen export dict.

    The offline freeze step: run :func:`solar_resource.pv_producer.compute_solar_aep`
    (behind the ``[solar]`` extra) once, pass the result here, and commit the returned
    dict (or the values it carries) into the scenario. Kept separate from the producer
    so this adapter — and its consumers — never import ``pvlib``.

    For ``scenario="P50"`` the deterministic energy/CF are used. For ``"P75"``/``"P90"`` the
    energy is pulled from ``result.exceedance`` (the P50/P75/P90 build-up) and the capacity
    factor is recomputed as a decimal against the DC nameplate; this requires the result to
    have been produced with ``compute_solar_aep(..., emit_exceedance=True)``.

    Args:
        result: A ``solar_resource.pv_producer.SolarAEPResult`` (duck-typed: needs
            ``annual_energy_gwh``, ``capacity_factor``, ``specific_yield_kwh_per_kwp`` and,
            for a non-P50 ``scenario``, ``exceedance``).
        dc_capacity_mw: The PV DC nameplate (MWp) the result was produced for — the
            ``SolarResourceConfig.dc_capacity_mw`` input, echoed for the identity check.
        scenario: The exceedance level to export: ``"P50"`` (default), ``"P75"`` or ``"P90"``
            (the 1-year P90).
        technology: The ``generation.technologies`` key this export targets.

    Returns:
        A plain dict validated-compatible with :class:`SolarCashflowExport`.

    Raises:
        ValueError: a non-P50 ``scenario`` is requested but ``result.exceedance`` is None.
    """
    if scenario == "P50":
        annual_energy_gwh = float(result.annual_energy_gwh)
        capacity_factor = float(result.capacity_factor)
    else:
        exceedance = getattr(result, "exceedance", None)
        if exceedance is None:
            raise ValueError(
                f"scenario={scenario!r} requested but result.exceedance is None — run "
                "compute_solar_aep(..., emit_exceedance=True) to populate P75/P90."
            )
        energy_by_level = {
            "P75": exceedance.p75_gwh,
            "P90": exceedance.p90_1yr_gwh,
        }
        annual_energy_gwh = float(energy_by_level[scenario])
        # Recompute CF as a DECIMAL against the DC nameplate for the chosen P-level
        # (energy MWh / (MWp * 8760 h)) — the same basis as the P50 capacity_factor.
        capacity_factor = annual_energy_gwh * 1.0e3 / (float(dc_capacity_mw) * 8760.0)

    return {
        "scenario": scenario,
        "technology": technology,
        "annual_energy_gwh": annual_energy_gwh,
        "capacity_factor": capacity_factor,
        "dc_capacity_mw": float(dc_capacity_mw),
        "specific_yield_kwh_per_kwp": float(result.specific_yield_kwh_per_kwp),
    }


# ---------------------------------------------------------------------------
# Per-tech field mapping table
#
# Each entry: (export_attr, scenario_subpath_under_the_tech_block, label_suffix)
# The full scenario path is generation.technologies.<technology>.<subpath>.
#   - capacity_mw    : commercial nameplate — identity with the export's DC capacity.
#   - capacity_factor: the financed driver (DECIMAL), written verbatim.
#   - aep_gwh        : the reporting split (capacity_mw · CF · 8.760).
# Order is significant only for deterministic error reporting; the first drift raises
# (lender-grade fail-fast), matching the wind adapter.
# ---------------------------------------------------------------------------

_TECH_FIELD_MAP: tuple[tuple[str, str], ...] = (
    ("dc_capacity_mw", "capacity_mw"),
    ("capacity_factor", "capacity_factor"),
    ("annual_energy_gwh", "aep_gwh"),
)


def _get_nested(d: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    """Return ``d[path[0]][path[1]]...`` or ``None`` if any segment is missing."""
    cur: Any = d
    for key in path:
        if not isinstance(cur, Mapping) or key not in cur:
            return None
        cur = cur[key]
    return cur


def _set_nested(d: MutableMapping[str, Any], path: tuple[str, ...], value: Any) -> None:
    """Set ``d[path[0]][path[1]]... = value``, creating intermediate dicts."""
    cur: MutableMapping[str, Any] = d
    for key in path[:-1]:
        nxt = cur.get(key)
        if not isinstance(nxt, MutableMapping):
            nxt = {}
            cur[key] = nxt
        cur = nxt
    cur[path[-1]] = value


def _drift_pct(solar_value: float, scenario_value: float) -> float:
    """Symmetric relative drift in percent (``max(|a|, |b|)`` denominator; 0/0 → 0)."""
    denom = max(abs(solar_value), abs(scenario_value))
    if denom == 0.0:
        return 0.0
    return 100.0 * abs(solar_value - scenario_value) / denom


def _recompute_project_capacity_factor(patched: MutableMapping[str, Any]) -> None:
    """Rewrite ``project.capacity_factor`` as the per-tech capacity-weighted blend.

    Reproduces the engine invariant enforced by
    ``finance.cashflow_v14_production.resolve_tech_generation_specs`` (±1%) and relied
    on by ``analytics.aep_reconciliation``::

        project.capacity_factor = Σ_tech(capacity_mw · capacity_factor) / project.capacity_mw

    Storage technologies are excluded using the engine's own
    ``finance.tech_types.is_storage_type`` predicate (lazy-imported so this module stays
    importable without finance and without ``pvlib``). No-op when the generation block,
    a resolvable ``project.capacity_mw``, or any contributing tech is absent — degenerate
    or single-field test scenarios are left untouched.
    """
    generation = patched.get("generation")
    techs = generation.get("technologies") if isinstance(generation, Mapping) else None
    project = patched.get("project")
    if not isinstance(techs, Mapping) or not isinstance(project, MutableMapping):
        return
    capacity_mw = project.get("capacity_mw")
    if not isinstance(capacity_mw, (int, float)) or isinstance(capacity_mw, bool):
        return
    if float(capacity_mw) <= 0:
        return

    from finance.tech_types import is_storage_type  # engine-canonical predicate

    weighted = 0.0
    contributing = 0
    for block in techs.values():
        if not isinstance(block, Mapping) or is_storage_type(block.get("type")):
            continue
        cap = block.get("capacity_mw")
        cf = block.get("capacity_factor")
        if not isinstance(cap, (int, float)) or isinstance(cap, bool):
            continue
        if not isinstance(cf, (int, float)) or isinstance(cf, bool):
            continue
        weighted += float(cap) * float(cf)
        contributing += 1
    if contributing == 0:
        return
    project["capacity_factor"] = weighted / float(capacity_mw)


def solar_export_to_scenario_patch(
    export_dict: Mapping[str, Any],
    scenario_yaml_dict: Mapping[str, Any],
    *,
    scenario_name: str = "P50",
    adapter_mode: SolarAdapterMode = "fill_if_absent",
    tolerance_pct: float = DEFAULT_TOLERANCE_PCT,
    technology: str = "solar",
) -> dict[str, Any]:
    """Apply a frozen solar export to a v14 hybrid scenario under the chosen mode.

    Args:
        export_dict: A frozen solar export (see :func:`build_solar_cashflow_export`).
            Validated against :class:`SolarCashflowExport` at the boundary.
        scenario_yaml_dict: A parsed v14 hybrid scenario. Deep-copied internally; the
            input mapping is **not** mutated.
        scenario_name: Sanity check — must match ``export_dict['scenario']``.
        adapter_mode: ``'overwrite'`` | ``'fill_if_absent'`` (default) |
            ``'validate_only'``. See module docstring.
        tolerance_pct: Acceptable symmetric per-tech drift (percent). Default 0.5.
        technology: The ``generation.technologies`` key to patch (default ``"solar"``).

    Returns:
        A new scenario dict (independent of the input) with the per-tech solar block
        patched and ``project.capacity_factor`` re-blended. For ``validate_only`` this is
        a deep copy with only the ``solar_resource`` provenance metadata added; no
        economics fields change.

    Raises:
        SolarAdapterDriftError: In ``fill_if_absent`` mode when a present per-tech value
            disagrees beyond ``tolerance_pct``; in ``validate_only`` mode on any missing
            or drifting field; in any mode when the export's DC nameplate disagrees with
            a present ``capacity_mw`` (the identity check).
        ValueError: ``scenario_name`` does not match the export's P-level, or
            ``adapter_mode`` is unrecognised.
        pydantic.ValidationError: The export fails schema validation.
    """
    # --- 0. argument hygiene ---------------------------------------------
    if adapter_mode not in ("overwrite", "fill_if_absent", "validate_only"):
        raise ValueError(
            "adapter_mode must be one of overwrite|fill_if_absent|validate_only; "
            f"got {adapter_mode!r}"
        )

    # --- 1. validate the export ------------------------------------------
    export = SolarCashflowExport.model_validate(export_dict)
    if export.scenario != scenario_name:
        raise ValueError(
            f"scenario_name={scenario_name!r} but export carries "
            f"scenario={export.scenario!r}; refusing to mix P-levels"
        )

    # --- 2. deep-copy so we never mutate the caller's dict ----------------
    patched: dict[str, Any] = copy.deepcopy(dict(scenario_yaml_dict))
    base = ("generation", "technologies", technology)

    # --- 3. per-field merge under the requested mode ----------------------
    wrote_any = False
    for export_attr, subkey in _TECH_FIELD_MAP:
        solar_value = float(getattr(export, export_attr))
        path = base + (subkey,)
        label = f"generation.technologies.{technology}.{subkey}"
        scenario_value = _get_nested(patched, path)

        # The commercial nameplate is an IDENTITY, not a mode-dependent economics field:
        # a real capacity mismatch must fail loud in every mode (overwrite included),
        # because applying a wrong-sized export silently mis-books generation.
        if subkey == "capacity_mw" and scenario_value is not None:
            try:
                existing = float(scenario_value)
            except (TypeError, ValueError):
                raise SolarAdapterDriftError(
                    label,
                    solar_value,
                    scenario_value,
                    None,
                    tolerance_pct,
                    adapter_mode,
                )
            if _drift_pct(solar_value, existing) > 100.0 * _CAPACITY_IDENTITY_TOL:
                raise SolarAdapterDriftError(
                    label,
                    solar_value,
                    existing,
                    _drift_pct(solar_value, existing),
                    tolerance_pct,
                    adapter_mode,
                )
            # Identity holds — nothing to write (capacity is not resource-derived).
            continue

        if adapter_mode == "overwrite":
            _set_nested(patched, path, solar_value)
            wrote_any = True
            continue

        if scenario_value is None:
            if adapter_mode == "validate_only":
                raise SolarAdapterDriftError(
                    label, solar_value, None, None, tolerance_pct, adapter_mode
                )
            _set_nested(patched, path, solar_value)  # fill_if_absent: write
            wrote_any = True
            continue

        # Present in both fill_if_absent and validate_only — compare to tolerance.
        try:
            scenario_value_f = float(scenario_value)
        except (TypeError, ValueError):
            raise SolarAdapterDriftError(
                label, solar_value, scenario_value, None, tolerance_pct, adapter_mode
            )
        drift = _drift_pct(solar_value, scenario_value_f)
        if drift > tolerance_pct:
            raise SolarAdapterDriftError(
                label, solar_value, scenario_value_f, drift, tolerance_pct, adapter_mode
            )
        # Within tolerance — leave the scenario value (the YAML stays canonical).

    # --- 4. re-blend the project headline if any per-tech field changed ----
    # validate_only never writes economics; fill_if_absent only re-blends when it
    # actually filled a missing value; overwrite always re-blends.
    if adapter_mode != "validate_only" and wrote_any:
        _recompute_project_capacity_factor(patched)

    # --- 5. always write the solar_resource provenance metadata -----------
    # Even in validate_only this is metadata, not economics, so it does not violate the
    # "never writes economics" promise (which covers the fields cashflow_v14 bills off).
    solar_meta_existing = patched.get("solar_resource")
    if not isinstance(solar_meta_existing, dict):
        solar_meta_existing = {}
        patched["solar_resource"] = solar_meta_existing
    solar_meta_existing.update(
        {
            "source": "frozen_export",
            "scenario": export.scenario,
            "technology": export.technology,
            "net_aep_gwh": float(export.annual_energy_gwh),
            "capacity_factor_decimal": float(export.capacity_factor),
            "dc_capacity_mw": float(export.dc_capacity_mw),
            "adapter_mode": adapter_mode,
            "adapter_tolerance_pct": float(tolerance_pct),
        }
    )
    if export.specific_yield_kwh_per_kwp is not None:
        solar_meta_existing["specific_yield_kwh_per_kwp"] = float(
            export.specific_yield_kwh_per_kwp
        )

    return patched

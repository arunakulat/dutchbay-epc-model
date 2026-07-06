"""Single evaluation gateway for the design-stage grid interconnection study (#874).

This module is to the grid study what :func:`analytics.evaluation_v14.evaluate_with_overrides`
is to the finance pipeline: the ONE typed entry point analytics layers call to run the
study. It composes the D1 grid-strength (SCR@POC) screen and the D3 steady-state
reactive/voltage screen into a single :class:`analytics.contracts_v14.GridStudyResult`.

CCCDIR boundary
---------------
Analytics consumers import grid RESULT types ONLY from
:mod:`analytics.contracts_v14` (the centralised contract module) and reach the grid
ENGINE (the pandapower screens) ONLY through this gateway. This module therefore imports:

  * the frozen result contracts from ``analytics.contracts_v14``; and
  * the two screen entrypoints under ``analytics.grid.*``.

It does NOT import the finance engine (``finance.*``) or any ``analytics.pipeline_*``
module — the grid study is additive and default-off, never touching the finance path, so
committed scenarios stay byte-identical (KPI-neutral).

CESSPIT
-------
The study is DEFAULT-OFF: ``grid.study_enabled`` gates it. When the gate is off (or a
``grid`` block is absent) the gateway does no electrical work. When on, the config is the
strict source of truth (the D2 schema guard has already validated it upstream); the SCR
screen's inputs are read from the D1 flat core and the reactive screen's from the D2
structured block.

CASPER
------
The heavy library (``pandapower``) is guarded at call-time inside each screen
(:func:`analytics.grid.short_circuit._require_pandapower` /
:func:`analytics.grid.reactive_screen._require_pandapower`), never at import time, so this
gateway imports cleanly in a grid-free environment. When the extra is absent the screens
fall back to their closed-form paths (or, for SCR, the closed-form Thevenin fallback).
"""

from __future__ import annotations

from typing import Any, Mapping

from analytics.contracts_v14 import (
    GridStrengthResult,
    GridStudyResult,
    PowerFlowResult,
    ReactiveCapabilityResult,
)
from analytics.grid.reactive_screen import screen_reactive_capability
from analytics.grid.short_circuit import screen_grid_strength

_STUDY_PROVENANCE = (
    "In-house Python design-stage grid interconnection study (SCR@POC + steady-state "
    "reactive/voltage screen). ADVISORY only — NOT the utility-accepted bankable "
    "connection study (CEB/NSCC require PSS/E or PowerFactory against their "
    "confidential grid base case)."
)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _run_strength_screen(
    grid: Mapping[str, Any], *, use_pandapower: bool
) -> GridStrengthResult:
    """Run the D1 SCR@POC screen from the grid config's flat-core inputs."""
    return screen_grid_strength(
        poc_voltage_kv=float(grid["poc_voltage_kv"]),
        source_fault_level_mva=float(grid["source_fault_level_mva"]),
        source_rx=float(grid["source_rx"]),
        connection_r_ohm=float(grid["connection_r_ohm"]),
        connection_x_ohm=float(grid["connection_x_ohm"]),
        plant_rating_mva=float(grid["plant_rating_mva"]),
        use_pandapower=use_pandapower,
    )


def _poc_bus_name(grid: Mapping[str, Any]) -> str | None:
    poc = grid.get("poc")
    if isinstance(poc, Mapping):
        name = poc.get("bus_name")
        if isinstance(name, str) and name.strip():
            return name
    return None


def evaluate_grid(
    config: Mapping[str, Any],
    *,
    use_pandapower: bool = True,
    run_reactive: bool = True,
) -> GridStudyResult:
    """Evaluate the design-stage grid study for a scenario config and return a bundle.

    This is the CCCDIR gateway — analytics layers call THIS, never the screens directly,
    and consume only :mod:`analytics.contracts_v14` result types.

    Args:
        config: the full scenario config (or at least its top-level ``grid`` block). A
            missing ``grid`` block, or ``grid.study_enabled`` not True, means the study is
            OFF and this raises (the caller must gate on ``study_enabled`` first) — the
            gateway never silently no-ops a disabled study into a hollow bundle.
        use_pandapower: forwarded to both screens; when False (or pandapower absent) the
            screens use their closed-form fallbacks.
        run_reactive: when True (default) also run the D3 reactive/voltage screen; when
            False only the D1 SCR screen runs (``reactive`` / ``power_flow`` are None).

    Returns:
        GridStudyResult — the SCR screen + (optionally) the reactive + power-flow
        screens, all advisory (``bankable=False``), tied to one POC.
    """
    grid = config.get("grid") if isinstance(config, Mapping) else None
    if not isinstance(grid, Mapping):
        raise ValueError(
            "evaluate_grid requires a top-level 'grid' block. This is the grid-study "
            "gateway; call it only when a scenario declares a grid block."
        )
    study_enabled = grid.get("study_enabled")
    if study_enabled is not True:
        raise ValueError(
            "grid.study_enabled must be True to evaluate the grid study (default-off "
            f"gate). Got study_enabled={study_enabled!r}. Gate on it before calling."
        )

    strength = _run_strength_screen(grid, use_pandapower=use_pandapower)

    reactive: ReactiveCapabilityResult | None = None
    power_flow: PowerFlowResult | None = None
    if run_reactive:
        reactive, power_flow = screen_reactive_capability(
            grid, use_pandapower=use_pandapower
        )

    return GridStudyResult(
        strength=strength,
        reactive=reactive,
        power_flow=power_flow,
        study_enabled=True,
        poc_bus_name=_poc_bus_name(grid),
        bankable=False,
        provenance=_STUDY_PROVENANCE,
        notes=(
            "Composite advisory grid study (SCR + reactive). Design-stage — confirm the "
            "connection point and PQ requirement with the utility's base case."
        ),
    )


__all__ = ["evaluate_grid"]

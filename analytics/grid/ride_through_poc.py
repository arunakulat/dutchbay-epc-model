"""ANDES RMS low-voltage ride-through (LVRT) scaffold — SHIM (#872, #875).

.. deprecated:: D4a (#875)
   The dynamics logic moved to the shared, generalised core
   :mod:`analytics.grid.ride_through`, which runs LVRT **plus** HVRT and frequency
   ride-through from the D0 grid-code envelope. This module is now a thin backward-
   compatibility SHIM: :func:`run_lvrt_case` delegates to
   :func:`analytics.grid.ride_through.run_ride_through_case` (the ``"lvrt"`` case) and
   :func:`lvrt_enter_from_fixture` / :func:`_require_andes` re-export the core's
   equivalents. Prefer the shared core directly for new callers.

The original scaffold stood up ANDES on a small system with a generic WECC IBR, applied
an impedance bus fault, and confirmed the RMS solve converged — seeded from the redacted
D0 grid-code fixture (``tests/fixtures/grid/envision_enpcs01_gridcode.yaml``). That
behaviour is preserved through the delegation below.

CASPER: ``andes`` is an OPTIONAL dependency of the ``[grid]`` extra; the guard
:func:`_require_andes` (re-exported from the shared core) defers the import to call-time.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# SHIM: the dynamics core is the single source of truth (D4a, #875).
from analytics.grid.ride_through import _require_andes as _require_andes  # noqa: F401
from analytics.grid.ride_through import envelope_from_fixture, run_ride_through_case


def lvrt_enter_from_fixture(fixture_path: Path | str | None = None) -> float:
    """Read the LVRT entry threshold (pu) from the D0 grid-code fixture.

    Backward-compatible re-export: delegates to the shared core's envelope parser
    (:func:`analytics.grid.ride_through.envelope_from_fixture`) and returns its
    ``lvrt_enter_pu`` — falling back to 0.9 pu when the fixture / key is absent.
    """
    return envelope_from_fixture(fixture_path).lvrt_enter_pu


@dataclass(frozen=True)
class LvrtScaffoldResult:
    """Outcome of the ANDES LVRT scaffold run (screening-grade dynamics smoke test).

    Retained for backward compatibility; :func:`run_lvrt_case` adapts the shared core's
    :class:`analytics.contracts_v14.RideThroughResult` (the ``"lvrt"`` case) into this
    legacy shape.
    """

    ran: bool
    lvrt_enter_pu: float
    detail: str
    n_devices: int = 0
    min_bus_voltage_pu: float | None = None


def run_lvrt_case(
    *,
    lvrt_enter_pu: float | None = None,
    fault_bus: int = 4,
    fault_start_s: float = 1.0,
    fault_clear_s: float = 1.1,
    fault_x_pu: float = 0.05,
    fixture_path: Path | str | None = None,
) -> LvrtScaffoldResult:
    """Run one ANDES RMS LVRT case and report whether the TDS converged.

    SHIM: delegates to :func:`analytics.grid.ride_through.run_ride_through_case` with
    ``kind="lvrt"`` and ``run_dynamics=True`` (this legacy entrypoint always runs the
    dynamics solve), then adapts the returned
    :class:`analytics.contracts_v14.RideThroughResult` into the legacy
    :class:`LvrtScaffoldResult` shape.

    Args:
        lvrt_enter_pu: retained for signature compatibility; when ``None`` the entry
            threshold is resolved from the D0 fixture via the shared core (the fixture is
            the source of truth). When supplied it is reported back on the result.
        fault_bus / fault_start_s / fault_clear_s / fault_x_pu: impedance-fault params.
        fixture_path: override for the grid-code fixture (tests inject a path).
    """
    # This legacy entrypoint always runs the dynamics solve (run_dynamics=True), so the
    # delegated call requires the [grid] extra (andes) — the whole body is andes-only and
    # is exercised by the grid-marked test_ride_through_dynamics.py, mirroring the CASPER
    # coverage pattern (the grid-free lane covers the shared core + the gate-off path).
    result = run_ride_through_case(  # pragma: no cover - requires [grid] extra
        "lvrt",
        run_dynamics=True,
        fixture_path=fixture_path,
        fault_bus=fault_bus,
        fault_start_s=fault_start_s,
        fault_clear_s=fault_clear_s,
        lvrt_fault_x_pu=fault_x_pu,
    )
    enter_pu = (  # pragma: no cover - requires [grid] extra
        float(lvrt_enter_pu)
        if lvrt_enter_pu is not None
        else (result.target_pu if result.target_pu is not None else 0.9)
    )
    return LvrtScaffoldResult(  # pragma: no cover - requires [grid] extra
        ran=result.ran,
        lvrt_enter_pu=enter_pu,
        detail=result.detail,
        n_devices=result.n_devices,
        min_bus_voltage_pu=result.min_voltage_pu,
    )


__all__ = ["LvrtScaffoldResult", "run_lvrt_case", "lvrt_enter_from_fixture"]

"""Short-circuit ratio (SCR) at the POC — the pivotal grid-strength screen (#872).

SCR = S_sc(POC) / S_plant decides whether a grid-following (GFL) inverter is viable or
a grid-forming (GFM) unit is needed. This module builds a minimal
``source -> connection -> POC`` network in **pandapower** and computes the fault level
at the POC via **IEC 60909** (both the MIN and MAX cases), then hands the MIN-case SCR
to :class:`analytics.contracts_v14.GridStrengthResult` for banding + the bankability/EMT
caveat. When pandapower is not installed a closed-form Thevenin fallback is used so the
screen still runs (flagged as ``method="closed_form"``).

SCREENING ONLY — design-stage. NOT the utility-accepted bankable connection study
(CEB/NSCC require PSS/E or PowerFactory against their confidential grid base case).

CASPER: ``pandapower`` is an OPTIONAL dependency of the ``[grid]`` extra. It is NEVER
imported at module-import time; the import is deferred to :func:`_require_pandapower`,
which raises an actionable ImportError at call-time if the extra is absent. The default
(grid-free) install imports this module cleanly and uses the closed-form fallback.
"""

from __future__ import annotations

import math
from typing import Any

from analytics.contracts_v14 import (
    GRID_EMT_CONFIRMATION_SCR,
    GRID_SCR_STRONG_ABOVE,
    GRID_SCR_WEAK_BELOW,
    GridStrengthResult,
)

_SCREENING_PROVENANCE = (
    "In-house Python design-stage screen (pandapower IEC 60909; SCR@POC). "
    "NOT the utility-accepted bankable grid-connection study — CEB/NSCC require "
    "PSS/E or PowerFactory against their confidential grid base case."
)


def _require_pandapower() -> Any:
    """Return the ``pandapower`` module or raise an actionable CASPER error if absent."""
    try:
        import pandapower  # noqa: F401

        return pandapower
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "Grid short-circuit screening requires the [grid] extra: "
            "pip install 'pandapower>=3.3,<3.4'  (or  PIP_CONSTRAINT=constraints.txt "
            "pip install -e '.[grid]'). It is an OPTIONAL dependency — the base finance "
            "install never needs it (a closed-form fallback is used instead)."
        ) from exc


def _closed_form_fault_level_mva(
    *,
    poc_voltage_kv: float,
    source_fault_level_mva: float,
    connection_r_ohm: float,
    connection_x_ohm: float,
) -> float:
    """Closed-form Thevenin fault level at the POC (MVA).

    Series-adds the source Thevenin impedance (from its own fault level) and the
    connection impedance, both referred to the POC voltage, then
    S_sc(POC) = V_poc^2 / |Z_total|. Used when pandapower is unavailable so the screen
    still runs. Magnitude-only (an RX-consistent approximation adequate for screening).
    """
    if source_fault_level_mva <= 0.0 or poc_voltage_kv <= 0.0:
        return 0.0
    # Source Thevenin magnitude referred to POC voltage: |Z_src| = V^2 / S_sc.
    z_src = (poc_voltage_kv**2) / source_fault_level_mva
    z_conn = math.hypot(connection_r_ohm, connection_x_ohm)
    z_total = z_src + z_conn
    if z_total <= 0.0:
        return float("inf")
    return (poc_voltage_kv**2) / z_total


def _pandapower_fault_level_mva(
    pp: Any,
    *,
    poc_voltage_kv: float,
    source_fault_level_mva: float,
    source_rx: float,
    connection_r_ohm: float,
    connection_x_ohm: float,
    plant_rating_mva: float,
    case: str,
) -> float:
    """Fault level at the POC (MVA) via pandapower IEC 60909, for ``case`` in {min,max}."""
    import pandapower.shortcircuit as sc

    net = pp.create_empty_network(sn_mva=max(plant_rating_mva, 1.0))
    b_src = pp.create_bus(net, vn_kv=poc_voltage_kv, name="SRC")
    b_poc = pp.create_bus(net, vn_kv=poc_voltage_kv, name="POC")
    # Upstream grid Thevenin equivalent (its own short-circuit level). For the MIN
    # case pandapower needs the *_min short-circuit inputs; supply the same nominal
    # level to both so the min case is a genuine (weakest-credible) lower bound.
    pp.create_ext_grid(
        net,
        b_src,
        vm_pu=1.0,
        s_sc_max_mva=source_fault_level_mva,
        s_sc_min_mva=source_fault_level_mva,
        rx_max=source_rx,
        rx_min=source_rx,
    )
    # Connection impedance source -> POC (line + interconnection transformer lumped),
    # ohms referred to the POC voltage. ``endtemp_degree`` (conductor end-temperature,
    # deg C) is REQUIRED by IEC 60909 for the MIN case: it applies the R-temperature
    # correction that makes the min-case fault level a genuine (weakest) lower bound.
    # 80 deg C is the IEC default maximum operating temperature for standard conductors.
    pp.create_line_from_parameters(
        net,
        from_bus=b_src,
        to_bus=b_poc,
        length_km=1.0,
        r_ohm_per_km=connection_r_ohm,
        x_ohm_per_km=connection_x_ohm,
        c_nf_per_km=0.0,
        max_i_ka=10.0,
        endtemp_degree=80.0,
    )
    sc.calc_sc(net, case=case, ip=False, ith=False, branch_results=False)
    ikss_ka = float(net.res_bus_sc.at[b_poc, "ikss_ka"])
    return math.sqrt(3.0) * poc_voltage_kv * ikss_ka


def screen_grid_strength(
    *,
    poc_voltage_kv: float,
    source_fault_level_mva: float,
    source_rx: float,
    connection_r_ohm: float,
    connection_x_ohm: float,
    plant_rating_mva: float,
    scr_weak_below: float = GRID_SCR_WEAK_BELOW,
    scr_strong_above: float = GRID_SCR_STRONG_ABOVE,
    emt_confirmation_scr: float = GRID_EMT_CONFIRMATION_SCR,
    use_pandapower: bool = True,
    provenance: str = _SCREENING_PROVENANCE,
) -> GridStrengthResult:
    """Screen grid strength at the POC and return the advisory contract.

    Builds a ``source -> connection -> POC`` Thevenin network and computes the IEC 60909
    fault level at the POC. The BANKABLE-governing SCR is taken from the IEC 60909 MIN
    case (weakest credible grid); the MAX case is reported for context only. The result
    is an ADVISORY only — it never feeds the finance engine.

    Args:
        poc_voltage_kv: Point-of-connection nominal voltage (kV).
        source_fault_level_mva: Short-circuit level at the upstream (source) busbar (MVA).
        source_rx: R/X ratio of the source Thevenin equivalent.
        connection_r_ohm: Connection (line + interconnection TX) resistance, ohms @ POC kV.
        connection_x_ohm: Connection reactance, ohms @ POC kV.
        plant_rating_mva: Aggregate plant rating (MVA) — the SCR denominator.
        scr_weak_below / scr_strong_above: SCR band thresholds (config-overridable).
        emt_confirmation_scr: SCR below which an EMT confirmation is mandated.
        use_pandapower: When True (default) use pandapower IEC 60909; when False (or when
            pandapower is absent) use the closed-form Thevenin fallback.

    Returns:
        GridStrengthResult — advisory SCR/band/GFL-GFM/EMT screen (``bankable=False``).
    """
    if plant_rating_mva <= 0.0:
        raise ValueError("plant_rating_mva must be > 0 to compute an SCR.")

    method = "closed_form"
    fault_min_mva: float
    fault_max_mva: float | None

    if use_pandapower:
        try:
            pp = _require_pandapower()
        except ImportError:
            pp = None
        if pp is not None:
            fault_min_mva = _pandapower_fault_level_mva(
                pp,
                poc_voltage_kv=poc_voltage_kv,
                source_fault_level_mva=source_fault_level_mva,
                source_rx=source_rx,
                connection_r_ohm=connection_r_ohm,
                connection_x_ohm=connection_x_ohm,
                plant_rating_mva=plant_rating_mva,
                case="min",
            )
            fault_max_mva = _pandapower_fault_level_mva(
                pp,
                poc_voltage_kv=poc_voltage_kv,
                source_fault_level_mva=source_fault_level_mva,
                source_rx=source_rx,
                connection_r_ohm=connection_r_ohm,
                connection_x_ohm=connection_x_ohm,
                plant_rating_mva=plant_rating_mva,
                case="max",
            )
            method = "pandapower_iec60909"
        else:
            fault_min_mva = _closed_form_fault_level_mva(
                poc_voltage_kv=poc_voltage_kv,
                source_fault_level_mva=source_fault_level_mva,
                connection_r_ohm=connection_r_ohm,
                connection_x_ohm=connection_x_ohm,
            )
            fault_max_mva = None
    else:
        fault_min_mva = _closed_form_fault_level_mva(
            poc_voltage_kv=poc_voltage_kv,
            source_fault_level_mva=source_fault_level_mva,
            connection_r_ohm=connection_r_ohm,
            connection_x_ohm=connection_x_ohm,
        )
        fault_max_mva = None

    scr_min = fault_min_mva / plant_rating_mva

    return GridStrengthResult.from_screen(
        scr_min=scr_min,
        fault_level_poc_min_mva=fault_min_mva,
        plant_rating_mva=plant_rating_mva,
        fault_level_poc_max_mva=fault_max_mva,
        method=method,
        provenance=provenance,
        weak_below=scr_weak_below,
        strong_above=scr_strong_above,
        emt_confirmation_scr=emt_confirmation_scr,
        notes=(
            "SCR from the IEC 60909 MIN case (weakest credible grid). "
            "Design-stage screen — confirm the connection point with the TSO base case."
        ),
    )


__all__ = ["screen_grid_strength"]

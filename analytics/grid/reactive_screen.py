"""Steady-state reactive / voltage screen at the POC (#874).

Answers the reactive-capability question the SCR screen (:mod:`analytics.grid.short_circuit`)
does not: *can the plant hold the POC power factor / voltage inside the grid-code PQ box
across the P × grid-voltage operating envelope, and if not, how many Mvar short is it?*

The screen builds a minimal ``ext_grid → POC transformer → collector bus → resources``
network in **pandapower** and runs an AC load-flow (``runpp``) over a sweep of active
power (0 → rated) × grid voltage (across the grid-code voltage window). At each operating
point it commands each converter-interfaced resource to the reactive limit that best
serves the grid-code requirement (Q-limits taken from the resource's reactive-capability
curve), reads the achieved POC power factor / voltage, and measures any Mvar shortfall
against the grid-code PQ box. The governing (worst) operating point sets the reported
shortfall + PQ-box verdict.

SCREENING ONLY — design-stage. NOT the utility-accepted bankable connection study
(CEB/NSCC require PSS/E or PowerFactory against their confidential grid base case).

CASPER: ``pandapower`` is an OPTIONAL dependency of the ``[grid]`` extra. It is NEVER
imported at module-import time; the import is deferred to :func:`_require_pandapower`
(mirroring :mod:`analytics.grid.short_circuit`), which raises an actionable ImportError
at call-time if the extra is absent. The default (grid-free) install imports this module
cleanly; the base finance engine never needs it.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from analytics.contracts_v14 import PowerFlowResult, ReactiveCapabilityResult

#: Provenance stamped on the reactive/power-flow screen results. Mirrors the string the
#: contract dataclasses default to; kept here so the screen module owns its own provenance.
_REACTIVE_SCREEN_PROVENANCE = (
    "In-house Python design-stage reactive/voltage screen (pandapower AC load-flow; "
    "POC transformer + collector equivalent; per-resource Q-limits from the reactive-"
    "capability curve). NOT the utility-accepted bankable grid-connection study — "
    "CEB/NSCC require PSS/E or PowerFactory against their confidential grid base case."
)

#: Default grid-code voltage window (pu) when a config does not declare one. The IEC /
#: SLSEA steady-state operating window at HV connection points is conventionally ±10 %.
DEFAULT_GRID_VOLTAGE_WINDOW_PU: tuple[float, float] = (0.9, 1.1)

#: Number of active-power steps in the P sweep (0 → rated, inclusive of both ends).
_DEFAULT_P_STEPS = 5


def _require_pandapower() -> Any:
    """Return the ``pandapower`` module or raise an actionable CASPER error if absent."""
    try:
        import pandapower  # noqa: F401

        return pandapower  # pragma: no cover - requires [grid] extra
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "Grid reactive/voltage screening requires the [grid] extra: "
            "pip install 'pandapower>=3.3,<3.4'  (or  PIP_CONSTRAINT=constraints.txt "
            "pip install -e '.[grid]'). It is an OPTIONAL dependency — the base finance "
            "install never needs it."
        ) from exc


def pf_to_qp_ratio(power_factor: float) -> float:
    """Return |Q|/P (``tan(acos(pf))``) for a power-factor magnitude in (0, 1].

    A pf of 0.95 → 0.3287 Mvar per MW. The sign convention (lagging/leading) is carried
    by the caller; this returns the magnitude ratio only.
    """
    pf = abs(float(power_factor))
    if pf <= 0.0 or pf > 1.0:
        raise ValueError(
            f"power_factor magnitude must be in (0, 1], got {power_factor!r}."
        )
    return math.tan(math.acos(pf))


def _resource_q_limits_mvar(resource: Mapping[str, Any]) -> tuple[float, float]:
    """Resolve (min_q_mvar, max_q_mvar) for one resource from its reactive-capability curve.

    Accepts either an explicit ``reactive_capability: {min_q_mvar, max_q_mvar}`` block or
    a ``pf_range: [pf_lag, pf_lead]`` + ``rated_mva`` pair (the OEM grid-code envelope,
    e.g. the Envision ENPCS01 fixture's ``pf_range: [-0.95, 0.95]``), from which the ±Q
    headroom is Q = P·tan(acos(pf)) evaluated at the resource rating. Strict (CESSPIT):
    an unusable/absent curve raises rather than silently assuming full capability.
    """
    cap = resource.get("reactive_capability")
    if isinstance(cap, Mapping) and "min_q_mvar" in cap and "max_q_mvar" in cap:
        min_q = float(cap["min_q_mvar"])
        max_q = float(cap["max_q_mvar"])
        if min_q > max_q:
            raise ValueError(
                f"reactive_capability min_q_mvar ({min_q}) must be <= max_q_mvar ({max_q})."
            )
        return min_q, max_q

    pf_range = resource.get("pf_range")
    rated_mva = resource.get("rated_mva")
    if (
        isinstance(pf_range, Sequence)
        and not isinstance(pf_range, (str, bytes))
        and len(pf_range) == 2
        and isinstance(rated_mva, (int, float))
        and not isinstance(rated_mva, bool)
        and float(rated_mva) > 0.0
    ):
        pf_lag, pf_lead = float(pf_range[0]), float(pf_range[1])
        # |Q| headroom at rated MW ≈ rated_mva · tan(acos(pf)) (P ≈ rated at pf near 1).
        q_lag = float(rated_mva) * pf_to_qp_ratio(pf_lag)
        q_lead = float(rated_mva) * pf_to_qp_ratio(pf_lead)
        return -abs(q_lag), abs(q_lead)

    raise ValueError(
        "resource reactive capability is undetermined — supply either "
        "reactive_capability {min_q_mvar, max_q_mvar} or pf_range [lag, lead] + rated_mva."
    )


def _required_mvar_at_p(p_mw: float, pf_required: float) -> float:
    """Mvar the grid code demands at active power ``p_mw`` for a required pf magnitude."""
    return abs(p_mw) * pf_to_qp_ratio(pf_required)


def _pf_from_pq(p_mw: float, q_mvar: float) -> float:
    """Signed power factor from (P, Q): sign follows Q (positive Q → leading, +pf)."""
    s = math.hypot(p_mw, q_mvar)
    if s <= 0.0:
        return 1.0
    pf = abs(p_mw) / s
    return math.copysign(pf, q_mvar) if q_mvar != 0.0 else 1.0


def _grid_voltage_window(grid: Mapping[str, Any]) -> tuple[float, float]:
    """Resolve the grid-code steady-state voltage window (pu) from config, default ±10 %."""
    gridcode = grid.get("gridcode")
    if isinstance(gridcode, Mapping):
        window = gridcode.get("voltage_window_pu")
        if (
            isinstance(window, Sequence)
            and not isinstance(window, (str, bytes))
            and len(window) == 2
        ):
            lo, hi = float(window[0]), float(window[1])
            if lo < hi:
                return lo, hi
    return DEFAULT_GRID_VOLTAGE_WINDOW_PU


def _required_pf_magnitude(grid: Mapping[str, Any]) -> tuple[float, float, float]:
    """Return (pf_required_magnitude, pf_required_min, pf_required_max) from ``gridcode``.

    The binding requirement magnitude is the tighter (closer to 1 in absolute terms is
    *looser*; further from 1 is *tighter*) of the signed pf_range endpoints. Strict: an
    absent/ill-formed ``gridcode.pf_range`` raises (CESSPIT — no silent full-capability).
    """
    gridcode = grid.get("gridcode")
    pf_range = gridcode.get("pf_range") if isinstance(gridcode, Mapping) else None
    if (
        not isinstance(pf_range, Sequence)
        or isinstance(pf_range, (str, bytes))
        or len(pf_range) != 2
    ):
        raise ValueError(
            "grid.gridcode.pf_range [pf_lag, pf_lead] is required for the reactive screen "
            "(the grid-code power-factor envelope the plant must hold at the POC)."
        )
    pf_min, pf_max = float(pf_range[0]), float(pf_range[1])
    # The binding pf magnitude is the smaller |pf| (the tighter reactive demand).
    pf_required = min(abs(pf_min), abs(pf_max))
    if pf_required <= 0.0 or pf_required > 1.0:
        raise ValueError(
            f"grid.gridcode.pf_range endpoints must have magnitude in (0, 1], got {pf_range!r}."
        )
    return pf_required, pf_min, pf_max


def _iter_resources(grid: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return the per-resource reactive descriptors for the screen.

    Prefers an explicit ``grid.resources`` list; otherwise synthesises a single aggregate
    resource from the POC rating + the grid-code pf_range (so a config that only declares
    the flat block still screens the aggregate plant).
    """
    resources = grid.get("resources")
    if isinstance(resources, Sequence) and not isinstance(resources, (str, bytes)):
        out = [r for r in resources if isinstance(r, Mapping)]
        if out:
            return out

    poc = grid.get("poc")
    plant_mva = None
    if isinstance(poc, Mapping):
        plant_mva = poc.get("plant_rated_mva")
    if plant_mva is None:
        plant_mva = grid.get("plant_rating_mva")
    gridcode = grid.get("gridcode")
    pf_range = gridcode.get("pf_range") if isinstance(gridcode, Mapping) else None
    if plant_mva is not None and pf_range is not None:
        return [
            {
                "name": "aggregate_plant",
                "rated_mva": float(plant_mva),
                "pf_range": list(pf_range),
            }
        ]
    raise ValueError(
        "reactive screen has no resources — supply grid.resources [...] or a "
        "grid.poc.plant_rated_mva + grid.gridcode.pf_range aggregate."
    )


def _build_network(  # pragma: no cover - requires [grid] extra
    pp: Any,
    *,
    poc_kv: float,
    p_mw: float,
    q_mvar_total: float,
    grid_v_pu: float,
    poc_transformer: Mapping[str, Any] | None,
    collector: Mapping[str, Any] | None,
) -> tuple[Any, int, int]:
    """Build ext_grid → POC transformer → collector bus network with the plant injection.

    Returns ``(net, poc_bus, collector_bus)``. The aggregate plant injection is modelled
    as a negative load (generation) of (``p_mw``, ``q_mvar_total``) at the collector bus;
    the collector-equivalent series impedance and POC transformer are taken from config
    when present, else a light default (screening-grade).
    """
    net = pp.create_empty_network(sn_mva=max(abs(p_mw), 1.0))
    b_grid = pp.create_bus(net, vn_kv=poc_kv, name="GRID")
    b_poc = pp.create_bus(net, vn_kv=poc_kv, name="POC")

    collector_kv = (
        float(collector.get("nominal_kv", poc_kv))
        if isinstance(collector, Mapping)
        else poc_kv
    )
    b_coll = pp.create_bus(net, vn_kv=collector_kv, name="COLLECTOR")

    pp.create_ext_grid(net, b_grid, vm_pu=grid_v_pu, name="upstream")

    # POC interconnection transformer: series R/X (ohms @ poc_kv) if declared, else a
    # light coupling reactance so the POC is a distinct electrical node.
    tx_r = (
        float(poc_transformer.get("r_ohm", 0.0))
        if isinstance(poc_transformer, Mapping)
        else 0.0
    )
    tx_x = (
        float(poc_transformer.get("x_ohm", 0.5))
        if isinstance(poc_transformer, Mapping)
        else 0.5
    )
    pp.create_line_from_parameters(
        net,
        from_bus=b_grid,
        to_bus=b_poc,
        length_km=1.0,
        r_ohm_per_km=max(tx_r, 0.0),
        x_ohm_per_km=max(tx_x, 1e-6),
        c_nf_per_km=0.0,
        max_i_ka=10.0,
    )

    # Collector equivalent: series R/X (ohms @ collector_kv) POC → collector bus.
    coll_r = (
        float(collector.get("r_ohm", 0.05)) if isinstance(collector, Mapping) else 0.05
    )
    coll_x = (
        float(collector.get("x_ohm", 0.2)) if isinstance(collector, Mapping) else 0.2
    )
    pp.create_line_from_parameters(
        net,
        from_bus=b_poc,
        to_bus=b_coll,
        length_km=1.0,
        r_ohm_per_km=max(coll_r, 0.0),
        x_ohm_per_km=max(coll_x, 1e-6),
        c_nf_per_km=0.0,
        max_i_ka=10.0,
    )

    # Aggregate plant injection at the collector bus (generation = negative load).
    pp.create_load(
        net, b_coll, p_mw=-float(p_mw), q_mvar=-float(q_mvar_total), name="plant"
    )
    return net, b_poc, b_coll


def _poc_pf_and_voltage(  # pragma: no cover - requires [grid] extra
    pp: Any, net: Any, poc_bus: int
) -> tuple[bool, float, float, float]:
    """Run ``runpp`` and read (converged, poc_v_pu, poc_p_mw, poc_q_mvar) at the POC.

    The POC P/Q are read from the line feeding the POC from the grid (the ext_grid
    injection through the transformer), so the pf is the pf *seen by the grid* at the POC.
    """
    try:
        pp.runpp(net, calculate_voltage_angles=True, init="flat")
    except Exception:  # pragma: no cover - non-convergence path
        return False, float("nan"), 0.0, 0.0
    if not bool(net["converged"]):
        return False, float("nan"), 0.0, 0.0
    poc_v = float(net.res_bus.at[poc_bus, "vm_pu"])
    # Line 0 is GRID → POC; its to-bus (POC) P/Q gives the flow arriving at the POC.
    p_poc = float(net.res_line.at[0, "p_to_mw"])
    q_poc = float(net.res_line.at[0, "q_to_mvar"])
    return True, poc_v, p_poc, q_poc


def screen_reactive_capability(
    grid: Mapping[str, Any],
    *,
    p_steps: int = _DEFAULT_P_STEPS,
    use_pandapower: bool = True,
    provenance: str = _REACTIVE_SCREEN_PROVENANCE,
) -> tuple[ReactiveCapabilityResult, PowerFlowResult | None]:
    """Screen the plant's reactive capability at the POC over a P × grid-voltage sweep.

    Args:
        grid: the top-level ``grid`` config block (D2 structured schema). Reads
            ``poc`` (nominal_kv, plant_rated_mva), ``gridcode.pf_range`` (required),
            ``gridcode.voltage_window_pu`` (optional, default ±10 %), and the optional
            ``poc_transformer`` / ``collector_equivalent`` / ``resources`` descriptors.
        p_steps: number of active-power steps in the 0 → rated sweep.
        use_pandapower: when True (default) run the pandapower AC load-flow; when False
            (or pandapower absent) fall back to a closed-form reactive-headroom screen.

    Returns:
        ``(ReactiveCapabilityResult, PowerFlowResult | None)`` — the reactive verdict at
        the governing (worst) operating point plus the load-flow snapshot there
        (``None`` in the closed-form fallback). Both are advisory (``bankable=False``).
    """
    poc = grid.get("poc")
    poc_kv = None
    plant_mva = None
    if isinstance(poc, Mapping):
        poc_kv = poc.get("nominal_kv")
        plant_mva = poc.get("plant_rated_mva")
    if poc_kv is None:
        poc_kv = grid.get("poc_voltage_kv")
    if plant_mva is None:
        plant_mva = grid.get("plant_rating_mva")
    if not isinstance(poc_kv, (int, float)) or float(poc_kv) <= 0.0:
        raise ValueError("reactive screen requires grid.poc.nominal_kv (kV; > 0).")
    if not isinstance(plant_mva, (int, float)) or float(plant_mva) <= 0.0:
        raise ValueError(
            "reactive screen requires grid.poc.plant_rated_mva (MVA; > 0)."
        )
    poc_kv = float(poc_kv)
    plant_mva = float(plant_mva)

    pf_required, pf_min, pf_max = _required_pf_magnitude(grid)
    v_lo, v_hi = _grid_voltage_window(grid)
    resources = _iter_resources(grid)

    # Aggregate reactive headroom (Mvar) available = sum of per-resource +Q limits
    # (leading; the direction the grid code typically demands at max export). The
    # capability box is symmetric enough for a screen; the tighter side governs.
    q_limits = [_resource_q_limits_mvar(r) for r in resources]
    mvar_available = sum(max_q for (_min_q, max_q) in q_limits)
    mvar_available_lag = sum(-min_q for (min_q, _max_q) in q_limits)
    # The binding available headroom is the smaller of the two directions.
    mvar_available = min(mvar_available, mvar_available_lag)

    p_steps = max(2, int(p_steps))
    p_points = [plant_mva * i / (p_steps - 1) for i in range(p_steps)]
    v_points = [v_lo, 1.0, v_hi]

    pp = None
    if use_pandapower:
        try:
            pp = _require_pandapower()
        except ImportError:
            pp = None

    poc_transformer = grid.get("poc_transformer")
    collector = grid.get("collector_equivalent")

    worst_shortfall = -1.0
    governing_p: float | None = None
    governing_v: float | None = None
    governing_pf_poc = 1.0
    governing_mvar_req = 0.0
    governing_converged = True
    governing_pf_result: PowerFlowResult | None = None
    method = "pandapower_runpp" if pp is not None else "closed_form"

    for p_mw in p_points:
        mvar_req = _required_mvar_at_p(p_mw, pf_required)
        # Command the aggregate plant to the reactive limit that best serves the code:
        # supply up to the available headroom (leading), capped at what's demanded.
        q_cmd = min(mvar_available, mvar_req)
        shortfall = max(0.0, mvar_req - mvar_available)

        if pp is not None:  # pragma: no cover - requires [grid] extra
            for grid_v in v_points:
                net, poc_bus, _coll = _build_network(
                    pp,
                    poc_kv=poc_kv,
                    p_mw=p_mw,
                    q_mvar_total=q_cmd,
                    grid_v_pu=grid_v,
                    poc_transformer=(
                        poc_transformer
                        if isinstance(poc_transformer, Mapping)
                        else None
                    ),
                    collector=collector if isinstance(collector, Mapping) else None,
                )
                converged, poc_v, p_poc, q_poc = _poc_pf_and_voltage(pp, net, poc_bus)
                pf_poc = _pf_from_pq(p_poc, q_poc)
                # A non-converged corner is treated as a binding failure (screen can't
                # place the operating point) so it surfaces rather than passing silently.
                effective_shortfall = (
                    shortfall if converged else max(shortfall, mvar_req)
                )
                if effective_shortfall > worst_shortfall:
                    worst_shortfall = effective_shortfall
                    governing_p = p_mw
                    governing_v = grid_v
                    governing_pf_poc = pf_poc
                    governing_mvar_req = mvar_req
                    governing_converged = converged
                    governing_pf_result = PowerFlowResult(
                        converged=converged,
                        bus_voltages_pu=(
                            {
                                str(net.bus.at[i, "name"]): float(
                                    net.res_bus.at[i, "vm_pu"]
                                )
                                for i in net.bus.index
                            }
                            if converged
                            else {}
                        ),
                        poc_voltage_pu=poc_v if converged else float("nan"),
                        poc_pf=pf_poc,
                        governing_p_mw=p_mw,
                        governing_grid_v_pu=grid_v,
                        provenance=provenance,
                    )
        else:
            # Closed-form fallback: no load-flow; the shortfall is the P-swept reactive gap.
            if shortfall > worst_shortfall:
                worst_shortfall = shortfall
                governing_p = p_mw
                governing_v = None
                governing_mvar_req = mvar_req
                governing_pf_poc = _pf_from_pq(p_mw, min(mvar_available, mvar_req))

    reactive = ReactiveCapabilityResult.from_screen(
        pf_required_min=pf_min,
        pf_required_max=pf_max,
        mvar_required=governing_mvar_req,
        mvar_available=mvar_available,
        pf_at_poc=governing_pf_poc,
        governing_p_mw=governing_p,
        governing_grid_v_pu=governing_v,
        governing_converged=governing_converged,
        method=method,
        provenance=provenance,
        notes=(
            "Reactive screen over P(0→rated) × grid-V(code window). Mvar shortfall is the "
            "gap at the governing (worst) operating point — the STATCOM/MSC sizing figure. "
            "Design-stage screen — confirm with the utility's PQ requirement + base case."
        ),
    )
    return reactive, governing_pf_result


__all__ = [
    "screen_reactive_capability",
    "pf_to_qp_ratio",
    "DEFAULT_GRID_VOLTAGE_WINDOW_PU",
]

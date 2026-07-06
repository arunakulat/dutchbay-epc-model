"""SCR-coupled harmonics / flicker power-quality screen at the POC (D7, #883).

Answers the POWER-QUALITY question the SCR / reactive / ride-through screens do not: *at
the point of connection, does the plant's harmonic-current emission produce a harmonic
VOLTAGE distortion inside the IEEE 519:2022 limits, and is the IEC 61400-21 flicker Pst
inside the planning limit — GIVEN how stiff (or weak) the grid is?*

Explicitly SCR-coupled
----------------------
This screen is deliberately COUPLED to grid stiffness (the D1 SCR / POC short-circuit
level ``Ssc``). Two physical mechanisms make the power-quality verdict DEGRADE as the SCR
falls:

  1. **Harmonic voltage.** The harmonic voltage at the POC is ``V_h = |Zbus(h)| · I_h``: a
     harmonic current ``I_h`` injected into a grid of harmonic bus impedance ``Zbus(h)``
     lifts the bus voltage in proportion to that impedance. A WEAKER grid (lower ``Ssc``)
     has a LARGER Thevenin impedance, so the SAME emission current produces a LARGER
     harmonic voltage. The closed-form estimate refers the impedance to ``Ssc`` explicitly
     (``|Z1| = V_poc² / Ssc``), so ``V_h`` rises as the SCR drops.
  2. **Flicker.** IEC 61400-21 gives the POC short-term flicker as
     ``Pst = c(ψk,va) · S_rated / Ssc`` — inversely proportional to ``Ssc``. A weaker grid
     ⇒ a higher flicker Pst.

The IEEE 519:2022 CURRENT distortion (TDD) limit is itself a function of the ``Isc/IL``
ratio (short-circuit current ÷ plant load current) — a weaker grid allows LESS current
distortion — so the limit table is indexed by that ratio (which tracks the SCR).

Frequency-domain scan
---------------------
When the ``[grid]`` extra is present, the per-order harmonic bus impedance ``|Zbus(h)|``
is taken from a **pandapower** frequency-domain bus-impedance scan of a minimal
``source → connection → POC`` network across the emission spectrum's harmonic orders
(the collector-cable capacitance + line/transformer reactance can resonate at a harmonic
order, lifting ``|Zbus(h)|`` well above the ``h × X1`` inductive estimate). When
pandapower is absent, a closed-form inductive estimate (``|Zbus(h)| ≈ h · |Z1|``, referred
to ``Ssc``) is used so the screen still runs (flagged ``method="closed_form"``).

SCREENING APPROXIMATION — NOT a standalone pass/fail
----------------------------------------------------
Every result is design-stage ADVISORY (``bankable=False``) and DEGRADES as the SCR falls.
A true harmonic / flicker compliance study is a frequency-domain PSS/E or PowerFactory
harmonic scan against the utility's confidential harmonic base case with the OEM
current-emission spectra and the full collector-network model. Nothing here feeds the
finance engine (committed scenarios stay byte-identical / KPI-neutral).

CASPER
------
``pandapower`` is an OPTIONAL dependency of the ``[grid]`` extra. It is NEVER imported at
module-import time; the import is deferred to :func:`_require_pandapower` (mirroring
:mod:`analytics.grid.short_circuit`), which raises an actionable ImportError at call-time
if the extra is absent. The default (grid-free) install imports this module cleanly and
uses the closed-form fallback.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence, TypeGuard

from analytics.contracts_v14 import HarmonicComplianceResult
from analytics.grid.frequency_response import (
    FrequencyResponseHeadroom,
    size_frequency_response_headroom,
)

_HARMONIC_SCREEN_PROVENANCE = (
    "In-house Python design-stage harmonics/flicker screen (SCR-coupled Zbus(h) "
    "harmonic-voltage estimate vs IEEE 519:2022 limits indexed by Isc/IL; IEC 61400-21 "
    "flicker Pst from POC Ssc). SCREENING APPROXIMATION that DEGRADES as SCR falls — NOT "
    "a standalone pass/fail and NOT the utility-accepted bankable study."
)

#: IEEE 519:2022 Table 1 — voltage-distortion limits (individual-harmonic %, THD_v %)
#: keyed by the nominal bus voltage band (kV). The screen picks the row for the plant's
#: POC voltage. These are the VOLTAGE-side compliance yardsticks (the current-side TDD
#: limit is indexed by Isc/IL separately, in ``_IEEE519_CURRENT_TDD``).
_IEEE519_VOLTAGE_LIMITS: tuple[tuple[float, float, float], ...] = (
    # (upper_kv_inclusive, individual_harmonic_pct, thd_v_pct)
    (1.0, 5.0, 8.0),  # V <= 1 kV
    (69.0, 3.0, 5.0),  # 1 kV < V <= 69 kV
    (161.0, 1.5, 2.5),  # 69 kV < V <= 161 kV
    (float("inf"), 1.0, 1.5),  # V > 161 kV
)

#: IEEE 519:2022 Table 2 — total demand distortion (TDD) current limit (%) as a function
#: of the Isc/IL ratio, for the general (odd-harmonic) case. A WEAKER grid (lower Isc/IL)
#: allows LESS current distortion — the SCR coupling on the current side. Rows are
#: ``(isc_il_below, tdd_limit_pct)``: the first row whose threshold the ratio is under wins.
_IEEE519_CURRENT_TDD: tuple[tuple[float, float], ...] = (
    (20.0, 5.0),  # Isc/IL < 20
    (50.0, 8.0),  # 20 <= Isc/IL < 50
    (100.0, 12.0),  # 50 <= Isc/IL < 100
    (1000.0, 15.0),  # 100 <= Isc/IL < 1000
    (float("inf"), 20.0),  # Isc/IL >= 1000
)

#: IEC 61000-3-7 / conventional HV flicker Pst planning limit at the POC. 0.35 is the
#: conventional HV/EHV short-term flicker planning level.
DEFAULT_FLICKER_PST_LIMIT = 0.35

#: Conventional IEC 61400-21 flicker coefficient c(ψk, va) for a modern converter-
#: interfaced plant when the config declares none. Modern IBRs are low-flicker; 4.0 is a
#: conservative continuous-operation screening value.
DEFAULT_FLICKER_COEFFICIENT = 4.0


def _require_pandapower() -> Any:
    """Return the ``pandapower`` module or raise an actionable CASPER error if absent."""
    try:
        import pandapower  # noqa: F401

        return pandapower  # pragma: no cover - requires [grid] extra
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "Grid harmonics screening requires the [grid] extra: "
            "pip install 'pandapower>=3.3,<3.4'  (or  PIP_CONSTRAINT=constraints.txt "
            "pip install -e '.[grid]'). It is an OPTIONAL dependency — the base finance "
            "install never needs it (a closed-form fallback is used instead)."
        ) from exc


def _is_number(value: Any) -> TypeGuard[int | float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def ieee519_voltage_limits(poc_voltage_kv: float) -> tuple[float, float]:
    """(individual-harmonic %, THD_v %) IEEE 519:2022 voltage limits for a POC kV.

    Picks the first row whose upper-kV bound the POC voltage does not exceed. A weaker
    (higher-kV transmission) connection gets a TIGHTER limit — the tables reflect that
    distortion is less tolerable up the voltage hierarchy.
    """
    if poc_voltage_kv <= 0.0:
        raise ValueError(f"poc_voltage_kv must be > 0, got {poc_voltage_kv!r}.")
    for upper_kv, individual_pct, thd_pct in _IEEE519_VOLTAGE_LIMITS:
        if poc_voltage_kv <= upper_kv:
            return individual_pct, thd_pct
    # Unreachable: the last row's bound is +inf. Kept explicit for total-function clarity.
    return (  # pragma: no cover - the +inf sentinel row always matches first
        _IEEE519_VOLTAGE_LIMITS[-1][1],
        _IEEE519_VOLTAGE_LIMITS[-1][2],
    )


def ieee519_current_tdd_limit(isc_il_ratio: float) -> float:
    """IEEE 519:2022 current TDD limit (%) indexed by the Isc/IL ratio (SCR-coupled).

    Lower Isc/IL (weaker grid) ⇒ a LOWER allowed current TDD. Raises on a non-positive
    ratio (CESSPIT — a zero/negative Isc/IL is a mis-specified screen, not a silent 20 %).
    """
    if isc_il_ratio <= 0.0:
        raise ValueError(
            f"isc_il_ratio must be > 0 to index the IEEE 519 TDD table, got {isc_il_ratio!r}."
        )
    for isc_il_below, tdd_pct in _IEEE519_CURRENT_TDD:
        if isc_il_ratio < isc_il_below:
            return tdd_pct
    return _IEEE519_CURRENT_TDD[-1][1]  # pragma: no cover - +inf sentinel matches first


def poc_ssc_mva(scr: float, plant_rating_mva: float) -> float:
    """POC short-circuit apparent power ``Ssc = SCR × S_plant`` (MVA) — the coupling term.

    The SCR is ``Ssc / S_plant`` by definition, so ``Ssc = SCR · S_plant``. This is the
    single quantity that couples harmonic voltage + flicker to grid stiffness: as it drops
    (weaker grid), both worsen. Raises on non-positive inputs (a zero Ssc would divide by
    zero downstream — surface it, don't silently pass).
    """
    if scr <= 0.0 or plant_rating_mva <= 0.0:
        raise ValueError(
            "poc_ssc_mva requires scr > 0 and plant_rating_mva > 0 "
            f"(got scr={scr!r}, plant_rating_mva={plant_rating_mva!r})."
        )
    return scr * plant_rating_mva


def isc_il_ratio(scr: float) -> float:
    """The IEEE 519 Isc/IL ratio ≈ the SCR.

    ``Isc`` is the POC short-circuit current and ``IL`` the plant maximum-demand (load)
    current; at the POC both are referred to the same voltage so ``Isc/IL = Ssc/S_plant =
    SCR``. This makes the coupling explicit: the current-distortion limit is indexed by the
    SCR. Raises on a non-positive SCR.
    """
    if scr <= 0.0:
        raise ValueError(f"isc_il_ratio requires scr > 0, got {scr!r}.")
    return scr


def _harmonic_spectrum(
    grid: Mapping[str, Any],
) -> list[tuple[int, float]]:
    """Resolve the per-order harmonic CURRENT-emission spectrum (order, % of IL).

    Reads ``grid.harmonic_spectrum`` (or ``gridcode.harmonic_spectrum``) as either a
    mapping ``{order: pct_of_IL}`` or a list of ``[order, pct_of_IL]`` pairs — the OEM
    current-emission spectrum expressed as a percentage of the plant's rated (demand)
    current. Returns the parsed ``(order, pct)`` pairs sorted by order, or an empty list
    when no spectrum is declared (the caller then reports the harmonic domain NOT-RUN
    rather than assuming a spurious pass).
    """
    spectrum = grid.get("harmonic_spectrum")
    if spectrum is None:
        gridcode = grid.get("gridcode")
        if isinstance(gridcode, Mapping):
            spectrum = gridcode.get("harmonic_spectrum")

    pairs: list[tuple[int, float]] = []
    if isinstance(spectrum, Mapping):
        for order, pct in spectrum.items():
            if _is_number(order) and _is_number(pct):
                h = int(order)
                if h >= 1:
                    pairs.append((h, float(pct)))
    elif isinstance(spectrum, Sequence) and not isinstance(spectrum, (str, bytes)):
        for row in spectrum:
            if (
                isinstance(row, Sequence)
                and not isinstance(row, (str, bytes))
                and len(row) == 2
                and _is_number(row[0])
                and _is_number(row[1])
            ):
                h = int(row[0])
                if h >= 1:
                    pairs.append((h, float(row[1])))
    return sorted(pairs, key=lambda t: t[0])


def closed_form_zbus_shape(order: int) -> float:
    """Closed-form per-order harmonic bus-impedance SHAPE at order ``h`` (normalised to h=1).

    For a purely inductive Thevenin grid the harmonic impedance scales linearly with
    frequency, so the shape (impedance ÷ fundamental impedance) is simply ``h``. The caller
    multiplies this by the plant-base fundamental impedance ``1/SCR`` to get the SCR-coupled
    ``|Zbus(h)|_plant``. A resonant collector network can push the real shape ABOVE this
    inductive value — the pandapower frequency scan captures that; this closed form is the
    conservative inductive estimate (it never sees the resonance peak).
    """
    if order < 1:
        raise ValueError(f"harmonic order must be >= 1, got {order!r}.")
    return float(order)


def harmonic_voltages_pct(
    spectrum: Sequence[tuple[int, float]],
    *,
    z1_pu_plant_base: float,
    zbus_shape_by_order: Mapping[int, float],
) -> list[tuple[int, float]]:
    """Per-order harmonic VOLTAGE distortion (order, % of nominal) — EXPLICITLY SCR-coupled.

    Physics: the harmonic voltage at the POC as a fraction of nominal is

        ``V_h[pu of nominal] = |Zbus(h)|[pu on plant base] · I_h[pu of plant demand]``,

    so in the screen's percentage units ``V_h[%] = |Zbus(h)|_plant · i_h[% of IL]``. The
    plant-base fundamental Thevenin impedance is ``|Z1|_plant = S_plant / Ssc = 1 / SCR`` —
    THIS is the SCR-coupling term: a weaker grid (lower SCR) has a LARGER ``1/SCR``, so the
    SAME emission current ``i_h`` produces a LARGER harmonic voltage. ``zbus_shape_by_order``
    is the per-order impedance SHAPE normalised to the fundamental (``h→1.0`` for a purely
    inductive grid ⇒ ``|Zbus(h)|_plant = h · z1``; a resonant collector network from the
    pandapower scan can push a shape value above ``h``). The ORDER-1 fundamental is EXCLUDED
    (it is not a distortion component — distortion counts harmonics ``h ≥ 2`` only).

    Args:
        spectrum: the ``(order, i_pct)`` current-emission spectrum (% of IL).
        z1_pu_plant_base: the plant-base fundamental Thevenin magnitude ``1/SCR``
            (the SCR coupling term; must be > 0).
        zbus_shape_by_order: per-order impedance shape normalised to the fundamental.

    Returns:
        The per-order ``(order, V_h_pct)`` list for harmonic orders ``h ≥ 2`` only.
    """
    if z1_pu_plant_base <= 0.0:
        raise ValueError(
            f"z1_pu_plant_base (=1/SCR) must be > 0, got {z1_pu_plant_base!r}."
        )
    out: list[tuple[int, float]] = []
    for order, i_pct in spectrum:
        if order < 2:
            continue  # fundamental is not a distortion component
        shape = zbus_shape_by_order.get(order)
        if shape is None:
            continue
        z_plant = z1_pu_plant_base * abs(shape)
        out.append((order, z_plant * abs(i_pct)))
    return out


def total_harmonic_distortion_pct(per_order_pct: Sequence[tuple[int, float]]) -> float:
    """Total harmonic (voltage or current) distortion = RSS of the per-order magnitudes."""
    return math.sqrt(sum(v * v for (_order, v) in per_order_pct))


def flicker_pst(
    *,
    flicker_coefficient: float,
    plant_rating_mva: float,
    poc_ssc_mva_value: float,
) -> float:
    """IEC 61400-21 short-term flicker severity at the POC (SCR-coupled).

    ``Pst = c(ψk, va) · S_rated / Ssc`` — a single-plant continuous-operation estimate. It
    is INVERSELY proportional to ``Ssc``: a weaker grid (lower ``Ssc``) ⇒ a higher flicker.
    Raises on a non-positive ``Ssc`` (division by zero would otherwise hide the coupling).
    """
    if poc_ssc_mva_value <= 0.0:
        raise ValueError(
            f"flicker_pst requires poc_ssc_mva_value > 0, got {poc_ssc_mva_value!r}."
        )
    if flicker_coefficient < 0.0 or plant_rating_mva < 0.0:
        raise ValueError(
            "flicker_pst requires non-negative flicker_coefficient and plant_rating_mva "
            f"(got c={flicker_coefficient!r}, S={plant_rating_mva!r})."
        )
    return flicker_coefficient * plant_rating_mva / poc_ssc_mva_value


def _flicker_coefficient(grid: Mapping[str, Any]) -> float | None:
    """Resolve the IEC 61400-21 flicker coefficient c(ψk, va) from config, else default.

    Reads ``grid.flicker_coefficient`` or ``gridcode.flicker_coefficient``. Returns the
    :data:`DEFAULT_FLICKER_COEFFICIENT` when neither is present (a conservative screening
    coefficient — flicker is always at least screened, never silently skipped for a
    converter plant). Returns ``None`` only when a coefficient is explicitly declared as a
    non-positive/invalid value that disables the flicker screen (an explicit opt-out).
    """
    for container_key in ("flicker_coefficient",):
        val = grid.get(container_key)
        if val is None:
            gridcode = grid.get("gridcode")
            if isinstance(gridcode, Mapping):
                val = gridcode.get(container_key)
        if val is not None:
            if _is_number(val) and float(val) >= 0.0:
                return float(val)
            # An explicitly invalid (negative / non-numeric) coefficient disables flicker.
            return None
    return DEFAULT_FLICKER_COEFFICIENT


def _pandapower_zbus_pu_by_order(  # pragma: no cover - requires [grid] extra
    pp: Any,
    orders: Sequence[int],
    *,
    poc_voltage_kv: float,
    poc_ssc_mva_value: float,
    source_rx: float,
    connection_r_ohm: float,
    connection_x_ohm: float,
    collector_c_nf: float,
) -> dict[int, float]:
    """Per-order ``|Zbus(h)|`` (pu on the Ssc base) from a pandapower frequency scan.

    Builds a minimal ``source → connection → POC`` network — the upstream Thevenin (sized
    from ``Ssc``), the connection line/transformer R+X, and the collector-cable shunt
    capacitance (``collector_c_nf``) that can RESONATE with the line reactance at a
    harmonic order — then, for each harmonic order ``h``, injects a 1 A current at the POC
    at frequency ``h·50`` Hz and reads the driving-point impedance ``|V/I|`` at the POC.
    Frequencies are represented by scaling the reactance / susceptance by ``h`` (an
    inductor's X and a capacitor's B both scale linearly with frequency), so the standard
    50 Hz ``runpp`` sees the h-th-harmonic network. The result is normalised to the
    fundamental driving-point impedance so it is returned in per-unit on the ``Ssc`` base.
    """
    # Fundamental Thevenin ohms referred to the POC voltage from Ssc.
    z1_ohm = (poc_voltage_kv**2) / poc_ssc_mva_value
    x1_src = z1_ohm / math.sqrt(1.0 + source_rx**2)
    r1_src = x1_src * source_rx

    z_by_order: dict[int, float] = {}
    base_dp = None
    for h in [1] + [o for o in sorted(set(orders)) if o != 1]:
        net = pp.create_empty_network(sn_mva=max(poc_ssc_mva_value, 1.0))
        b_src = pp.create_bus(net, vn_kv=poc_voltage_kv, name="SRC")
        b_poc = pp.create_bus(net, vn_kv=poc_voltage_kv, name="POC")
        # Source Thevenin at harmonic h: R constant, X scales with h.
        pp.create_ext_grid(net, b_src, vm_pu=1.0)
        pp.create_line_from_parameters(
            net,
            from_bus=b_src,
            to_bus=b_poc,
            length_km=1.0,
            r_ohm_per_km=r1_src + connection_r_ohm,
            x_ohm_per_km=h * (x1_src + connection_x_ohm),
            # Shunt capacitance scales its susceptance with h — the resonance term.
            c_nf_per_km=collector_c_nf * h,
            max_i_ka=10.0,
        )
        # 1 MW-equivalent probe injection at the POC as a load; the driving-point
        # impedance is read as the POC voltage deviation per unit injected current.
        pp.create_load(net, b_poc, p_mw=0.0, q_mvar=1.0, name="probe")
        pp.runpp(net, calculate_voltage_angles=True, init="flat")
        v_poc = float(net.res_bus.at[b_poc, "vm_pu"])
        # Driving-point proxy: the pu voltage change under the fixed probe is proportional
        # to |Zbus(h)|. Normalise to the fundamental to get a per-unit-on-Ssc impedance.
        dp = abs(1.0 - v_poc)
        if h == 1:
            base_dp = dp if dp > 0.0 else 1.0
            z_by_order[1] = 1.0
        else:
            z_by_order[h] = (dp / base_dp) if base_dp else float(h)
    return z_by_order


def screen_harmonics(
    grid: Mapping[str, Any],
    *,
    scr: float,
    plant_rating_mva: float | None = None,
    poc_voltage_kv: float | None = None,
    capacity_factor: float = 0.0,
    use_pandapower: bool = True,
    provenance: str = _HARMONIC_SCREEN_PROVENANCE,
) -> HarmonicComplianceResult:
    """Screen POC harmonics + flicker (SCR-coupled) and size frequency-response headroom.

    The screen is COUPLED to the D1 SCR: it derives the POC short-circuit power
    ``Ssc = SCR · S_plant``, refers the harmonic bus impedance and the flicker to it, and
    indexes the IEEE 519 current-TDD limit by the ``Isc/IL`` (= SCR) ratio — so the whole
    verdict DEGRADES as the SCR falls.

    Args:
        grid: the top-level ``grid`` config block. Reads ``poc`` (nominal_kv,
            plant_rated_mva) / the D1 flat core, the optional ``harmonic_spectrum`` (OEM
            current-emission spectrum, % of IL), the optional ``flicker_coefficient``, the
            optional ``collector_equivalent.c_nf`` (resonance term for the scan), and
            ``gridcode`` (frequency band + droop for the headroom sizing).
        scr: the SCR from the D1 grid-strength screen (the coupling term; must be > 0).
        plant_rating_mva / poc_voltage_kv: overrides; default to the config's POC values.
        capacity_factor: plant capacity factor (0 → 1) for the energy-foregone sizing.
        use_pandapower: when True (default) run the pandapower frequency-domain Zbus scan;
            when False (or pandapower absent) use the closed-form inductive estimate.

    Returns:
        HarmonicComplianceResult — the SCR-coupled harmonics/flicker screen +
        frequency-response headroom, advisory (``bankable=False``). The per-domain verdicts
        are ``None`` (NOT-RUN) when the relevant input (spectrum / flicker coefficient) is
        absent — never a spurious pass.
    """
    if scr <= 0.0:
        raise ValueError(f"screen_harmonics requires scr > 0 (the SCR), got {scr!r}.")

    poc = grid.get("poc")
    kv = poc_voltage_kv
    mva = plant_rating_mva
    if isinstance(poc, Mapping):
        if kv is None:
            kv = poc.get("nominal_kv")
        if mva is None:
            mva = poc.get("plant_rated_mva")
    if kv is None:
        kv = grid.get("poc_voltage_kv")
    if mva is None:
        mva = grid.get("plant_rating_mva")
    if not _is_number(kv) or float(kv) <= 0.0:
        raise ValueError("harmonics screen requires grid.poc.nominal_kv (kV; > 0).")
    if not _is_number(mva) or float(mva) <= 0.0:
        raise ValueError(
            "harmonics screen requires grid.poc.plant_rated_mva (MVA; > 0)."
        )
    kv = float(kv)
    mva = float(mva)

    ssc = poc_ssc_mva(scr, mva)
    ratio = isc_il_ratio(scr)
    individual_limit_pct, thd_v_limit_pct = ieee519_voltage_limits(kv)
    current_tdd_limit_pct = ieee519_current_tdd_limit(ratio)

    spectrum = _harmonic_spectrum(grid)

    # SCR coupling term: the plant-base fundamental Thevenin impedance is 1/SCR, so a weaker
    # grid (lower SCR) produces a proportionally larger harmonic voltage from the same I_h.
    z1_pu_plant_base = 1.0 / scr

    # Per-order harmonic bus-impedance SHAPE (normalised to the fundamental). Inductive
    # closed form: shape = h. The pandapower frequency scan can lift a shape above h at a
    # collector resonance. The SCR coupling lives in z1_pu_plant_base, not the shape.
    method = "closed_form"
    zbus_shape_by_order: dict[int, float]
    if spectrum:
        orders = [o for (o, _pct) in spectrum]
        pp = None
        if use_pandapower:
            try:
                pp = _require_pandapower()
            except ImportError:
                pp = None
        if pp is not None:  # pragma: no cover - requires [grid] extra
            collector = grid.get("collector_equivalent")
            collector_c_nf = (
                float(collector.get("c_nf", 0.0))
                if isinstance(collector, Mapping) and _is_number(collector.get("c_nf"))
                else 0.0
            )
            zbus_shape_by_order = _pandapower_zbus_pu_by_order(
                pp,
                orders,
                poc_voltage_kv=kv,
                poc_ssc_mva_value=ssc,
                source_rx=float(grid.get("source_rx", 0.1) or 0.1),
                connection_r_ohm=float(grid.get("connection_r_ohm", 0.0) or 0.0),
                connection_x_ohm=float(grid.get("connection_x_ohm", 0.0) or 0.0),
                collector_c_nf=collector_c_nf,
            )
            method = "pandapower_zbus"
        else:
            zbus_shape_by_order = {o: closed_form_zbus_shape(o) for o in orders}
    else:
        zbus_shape_by_order = {}

    # Harmonic voltages (% of nominal) and TDD_v (RSS). None when no spectrum was supplied.
    worst_order: int | None = None
    worst_v_pct: float | None = None
    thd_v_pct: float | None = None
    current_tdd_pct: float | None = None
    if spectrum:
        v_per_order = harmonic_voltages_pct(
            spectrum,
            z1_pu_plant_base=z1_pu_plant_base,
            zbus_shape_by_order=zbus_shape_by_order,
        )
        if v_per_order:
            worst_order, worst_v_pct = max(v_per_order, key=lambda t: t[1])
            thd_v_pct = total_harmonic_distortion_pct(v_per_order)
        # Current TDD = RSS of the emission spectrum (% of IL); order 1 is the fundamental,
        # excluded from distortion (TDD counts harmonics only).
        harmonics_only = [(o, p) for (o, p) in spectrum if o >= 2]
        current_tdd_pct = total_harmonic_distortion_pct(harmonics_only)

    # Flicker Pst (SCR-coupled). None when the flicker screen is explicitly disabled.
    coeff = _flicker_coefficient(grid)
    pst: float | None = None
    if coeff is not None:
        pst = flicker_pst(
            flicker_coefficient=coeff,
            plant_rating_mva=mva,
            poc_ssc_mva_value=ssc,
        )
    flicker_limit = grid.get("flicker_pst_limit")
    flicker_limit_val = (
        float(flicker_limit)
        if _is_number(flicker_limit) and float(flicker_limit) > 0.0
        else DEFAULT_FLICKER_PST_LIMIT
    )

    # Frequency-response de-load headroom + energy foregone (pure, always computed).
    headroom: FrequencyResponseHeadroom = size_frequency_response_headroom(
        rated_mw=mva,
        gridcode=(
            grid.get("gridcode") if isinstance(grid.get("gridcode"), Mapping) else None
        ),
        capacity_factor=max(0.0, min(1.0, float(capacity_factor))),
        droop=_config_droop(grid),
        mandated_reserve_fraction=_config_mandated_reserve(grid),
    )

    return HarmonicComplianceResult.from_screen(
        scr=scr,
        isc_il_ratio=ratio,
        worst_harmonic_order=worst_order,
        worst_harmonic_voltage_pct=worst_v_pct,
        harmonic_voltage_limit_pct=individual_limit_pct,
        thd_voltage_pct=thd_v_pct,
        thd_voltage_limit_pct=thd_v_limit_pct,
        current_tdd_pct=current_tdd_pct,
        current_tdd_limit_pct=current_tdd_limit_pct,
        flicker_pst=pst,
        flicker_pst_limit=flicker_limit_val,
        poc_ssc_mva=ssc,
        freq_response_headroom_mw=headroom.headroom_mw,
        energy_foregone_mwh_yr=headroom.energy_foregone_mwh_yr,
        method=method,
        provenance=provenance,
        notes=(
            "SCR-coupled harmonics/flicker screen: harmonic voltage V_h=Zbus(h)*I_h and "
            f"flicker Pst both scale inverse to Ssc={ssc:.1f} MVA (SCR={scr:.2f}); IEEE 519 "
            f"current-TDD limit indexed by Isc/IL={ratio:.2f}. Frequency-response headroom "
            f"{headroom.headroom_mw:.2f} MW ({headroom.source}). SCREENING approximation — "
            "DEGRADES as SCR falls; confirm with a frequency-domain harmonic study."
        ),
    )


def _config_droop(grid: Mapping[str, Any]) -> float | None:
    """Resolve a governor droop fraction from ``grid`` / ``gridcode``, else None (default)."""
    for val in (grid.get("droop"), _gridcode_get(grid, "droop")):
        if _is_number(val) and float(val) > 0.0:
            return float(val)
    return None


def _config_mandated_reserve(grid: Mapping[str, Any]) -> float:
    """Resolve a mandated frequency-reserve fraction from config, else 0.0."""
    for val in (
        grid.get("mandated_reserve_fraction"),
        _gridcode_get(grid, "mandated_reserve_fraction"),
    ):
        if _is_number(val) and 0.0 <= float(val) <= 1.0:
            return float(val)
    return 0.0


def _gridcode_get(grid: Mapping[str, Any], key: str) -> Any:
    gridcode = grid.get("gridcode")
    return gridcode.get(key) if isinstance(gridcode, Mapping) else None


__all__ = [
    "DEFAULT_FLICKER_PST_LIMIT",
    "DEFAULT_FLICKER_COEFFICIENT",
    "ieee519_voltage_limits",
    "ieee519_current_tdd_limit",
    "poc_ssc_mva",
    "isc_il_ratio",
    "closed_form_zbus_shape",
    "harmonic_voltages_pct",
    "total_harmonic_distortion_pct",
    "flicker_pst",
    "screen_harmonics",
]

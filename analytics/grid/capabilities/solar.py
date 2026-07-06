"""Solar PV grid-capability plug-in (D4c, #877).

Answers the converter-interface capability question for a SOLAR technology block: given
its DC nameplate, DC:AC ratio (ILR) and grid-code reactive envelope, what fault-current
and reactive (PQ) capability does the plant present at the point of connection?

Solar PV is a CURRENT-LIMITED, GRID-FOLLOWING source
----------------------------------------------------
A utility-scale PV plant is a fleet of voltage-source-converter (VSC) inverters that
TRACK the grid phasor via a PLL and hard-limit their output current. Under a fault it does
NOT behave like a synchronous machine: there is no sub-transient reactance feeding a large
(5-6x) fault current from stored rotor flux. The inverter simply rides its current limit,
so the fault infeed is small — conventionally ~**1.1 pu** of rated current (the firmware
over-current ceiling), and NEGLIGIBLE as a grid-strengthening contribution.

This is the load-bearing modelling rule of this plug-in: **solar MUST NOT be modelled as a
voltage source / synchronous machine.** Doing so would inject a spurious fault MVA at the
POC and OVERSTATE the short-circuit ratio (SCR) — exactly the optimism the D1 SCR screen
(:mod:`analytics.grid.short_circuit`) exists to avoid. The plug-in therefore reports the
plant's fault-current CONTRIBUTION as a current-limited infeed (≈ ``fault_current_pu`` ×
AC rating), flagged as a grid-following source that adds ~no meaningful fault level, so a
downstream SCR aggregation credits it as ~0 rather than as a machine.

DC:AC clipping WITHOUT double-counting the inverter loss
--------------------------------------------------------
The AC nameplate (the inverter/POC export cap) is ``dc_capacity_mw / dc_ac_ratio`` — a
pure GEOMETRIC relationship (the inverter saturates AC export at this cap). The energy /
efficiency loss of the inverter (the PVWatts inverter efficiency + the midday clip) is
ALREADY applied by the ``solar_resource`` pipeline: :func:`solar_resource.pv_producer`
calls ``pvlib.inverter.pvwatts(..., pdc0=ac_nameplate_w / inverter_eff_nom).clip(
upper=ac_nameplate_w)``. This plug-in therefore uses the DC:AC ratio ONLY to size the AC
export rating (the reactive-capability base MVA), and NEVER re-applies an inverter
efficiency derate — re-applying it would double-count the loss the resource model already
took.

Reactive / current capability (advisory)
----------------------------------------
The reactive capability is expressed against the AC POC rating over the grid-code
``pf_range`` (equivalently a ±Q(P) box), reusing the D3 reactive math
(:func:`analytics.grid.reactive_screen.pf_to_qp_ratio`) and the D3 advisory contract
(:class:`analytics.contracts_v14.ReactiveCapabilityResult`). It is a CLOSED-FORM headroom
screen (no load-flow) — the pandapower AC load-flow refinement lives in the D3 screen and
is reused there, not re-implemented here.

CASPER / KPI-neutral
--------------------
The capability MATH is pure Python (no ``pandapower`` / ``andes`` import). Every result is
ADVISORY (``bankable=False``) and never feeds the finance engine, so committed scenarios
stay byte-identical (KPI-neutral). Where an input is missing/ill-formed the plug-in raises
(CESSPIT) or returns an explicit NOT-RUN — never a defaulted pass (NO SPURIOUS PASS).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from analytics.contracts_v14 import ReactiveCapabilityResult
from analytics.grid.reactive_screen import pf_to_qp_ratio
from finance.tech_types import is_modelled_generation_type

#: The technology class this plug-in models.
SOLAR_TECH = "solar"

#: Conventional current-limited fault-current ceiling of a grid-following PV inverter, in
#: pu of rated current. Real firmware limits sit ~1.1-1.2 pu; 1.1 pu is the conservative
#: screening value. NOT a synchronous-machine sub-transient contribution (that would be
#: ~5-6 pu) — solar rides its current limit, so the fault infeed is small.
DEFAULT_FAULT_CURRENT_PU = 1.1

#: Provenance stamped on the solar capability screen results.
_SOLAR_CAPABILITY_PROVENANCE = (
    "In-house Python design-stage solar-PV grid-capability screen (current-limited "
    "grid-following inverter model; ~1.1 pu fault-current ceiling, negligible fault "
    "infeed — NOT a synchronous machine/voltage source; DC:AC clipping from the ILR, "
    "inverter efficiency NOT re-applied — it already lives in solar_resource). NOT the "
    "utility-accepted bankable grid-connection study — CEB/NSCC require PSS/E or "
    "PowerFactory against their confidential grid base case."
)


@dataclass(frozen=True)
class SolarFaultContribution:
    """The fault-current contribution a current-limited PV plant presents at the POC.

    Solar is a GRID-FOLLOWING, current-limited source: its fault infeed is a small
    multiple of rated current (``fault_current_pu``), NOT a synchronous-machine
    sub-transient contribution. ``is_synchronous`` is therefore always ``False`` and
    ``fault_mva_contribution`` is the current-limited apparent-power infeed (≈
    ``fault_current_pu`` × AC rating) — the figure a downstream SCR aggregation should
    credit (it does NOT strengthen the grid the way a machine would).

    Fields
        ac_rating_mva: the AC export rating (MVA) the contribution is scaled from.
        fault_current_pu: the current-limited fault-current ceiling (pu of rated current).
        fault_mva_contribution: the current-limited fault-power infeed (MVA) =
            ``fault_current_pu`` × ``ac_rating_mva``. Small by construction.
        is_synchronous: always ``False`` — solar is NOT a synchronous machine / voltage
            source; a screen that models it as one OVERSTATES grid strength.
        note: a human caveat (the load-bearing "do not model as a voltage source" rule).
    """

    ac_rating_mva: float
    fault_current_pu: float
    fault_mva_contribution: float
    is_synchronous: bool
    note: str


def is_solar_capability_tech(tech_name: Any) -> bool:
    """True iff ``tech_name`` is the solar class this plug-in models.

    Keyed on the :mod:`finance.tech_types` classification (single source of truth): solar
    is a MODELLED generation type (a real resource-backed capacity-factor source), so this
    reuses ``is_modelled_generation_type`` and additionally pins the name to ``solar`` (the
    other modelled generation type, wind, has its own plug-in).
    """
    if not is_modelled_generation_type(tech_name):
        return False
    return str(tech_name).strip().lower() == SOLAR_TECH


def ac_rating_from_dc(dc_capacity_mw: Any, dc_ac_ratio: Any) -> float:
    """AC export rating (MVA/MW) from the DC nameplate and the DC:AC ratio (ILR).

    Pure GEOMETRIC relationship: the inverter saturates AC export at
    ``dc_capacity_mw / dc_ac_ratio``. This is the inverter/POC export cap — the base the
    reactive capability is sized against. NO inverter efficiency derate is applied here:
    the efficiency/clip loss already lives in :mod:`solar_resource.pv_producer` (applying
    it again would double-count it).

    Raises:
        ValueError: for a non-positive DC nameplate or DC:AC ratio (CESSPIT — no silent
            default; a nonsensical rating must fail loud, never screen a spurious value).
    """
    if not _is_positive_number(dc_capacity_mw):
        raise ValueError(
            f"dc_capacity_mw must be a number > 0 (MWp), got {dc_capacity_mw!r}."
        )
    if not _is_positive_number(dc_ac_ratio):
        raise ValueError(
            f"dc_ac_ratio (ILR) must be a number > 0, got {dc_ac_ratio!r}."
        )
    return float(dc_capacity_mw) / float(dc_ac_ratio)


def solar_fault_contribution(
    ac_rating_mva: float,
    *,
    fault_current_pu: float = DEFAULT_FAULT_CURRENT_PU,
) -> SolarFaultContribution:
    """Fault-current contribution of a current-limited grid-following PV plant.

    Models solar as a CURRENT-LIMITED source riding its firmware over-current ceiling
    (``fault_current_pu``, ~1.1 pu of rated current) — NOT a synchronous machine. The
    reported ``fault_mva_contribution`` is therefore the small current-limited infeed
    (``fault_current_pu`` × ``ac_rating_mva``), and ``is_synchronous`` is always ``False``
    so a downstream SCR aggregation cannot credit solar with a machine's fault level.

    Raises:
        ValueError: for a non-positive AC rating or fault-current pu (CESSPIT).
    """
    if not _is_positive_number(ac_rating_mva):
        raise ValueError(
            f"ac_rating_mva must be a number > 0 (MVA), got {ac_rating_mva!r}."
        )
    if not _is_positive_number(fault_current_pu):
        raise ValueError(
            f"fault_current_pu must be a number > 0 (pu), got {fault_current_pu!r}."
        )
    ac = float(ac_rating_mva)
    ipu = float(fault_current_pu)
    return SolarFaultContribution(
        ac_rating_mva=ac,
        fault_current_pu=ipu,
        fault_mva_contribution=ipu * ac,
        is_synchronous=False,
        note=(
            "Current-limited grid-following inverter: fault infeed ≈ "
            f"{ipu:g} pu of rated current, NOT a synchronous-machine sub-transient "
            "contribution. Do NOT model as a voltage source / machine when aggregating "
            "SCR — it would overstate grid strength."
        ),
    )


def _pf_range_from_gridcode(grid_tech_block: Mapping[str, Any]) -> tuple[float, float]:
    """Resolve the grid-code (pf_lag, pf_lead) the plant must hold, from the tech block.

    Reads ``gridcode.pf_range`` (the OEM/grid-code reactive envelope, e.g. the Envision
    ENPCS01 ``pf_range: [-0.95, 0.95]``). Strict (CESSPIT): an absent/ill-formed pf_range
    raises rather than silently assuming full reactive capability.
    """
    gridcode = grid_tech_block.get("gridcode")
    pf_range = gridcode.get("pf_range") if isinstance(gridcode, Mapping) else None
    if (
        not isinstance(pf_range, (list, tuple))
        or len(pf_range) != 2
        or not all(_is_number(v) for v in pf_range)
    ):
        raise ValueError(
            "solar grid.gridcode.pf_range [pf_lag, pf_lead] is required for the reactive "
            "capability screen (the grid-code power-factor envelope the plant must hold)."
        )
    pf_lag, pf_lead = float(pf_range[0]), float(pf_range[1])
    for pf in (pf_lag, pf_lead):
        if not 0.0 < abs(pf) <= 1.0:
            raise ValueError(
                f"solar grid.gridcode.pf_range endpoints must have magnitude in (0, 1], "
                f"got {pf_range!r}."
            )
    return pf_lag, pf_lead


def screen_solar_capability(
    grid_tech_block: Mapping[str, Any],
    *,
    fault_current_pu: float = DEFAULT_FAULT_CURRENT_PU,
    provenance: str = _SOLAR_CAPABILITY_PROVENANCE,
) -> tuple[ReactiveCapabilityResult, SolarFaultContribution]:
    """Screen a solar block's reactive + fault-current capability at the POC (advisory).

    Reads a per-tech ``generation.technologies.solar.grid``-shaped block:

      * ``dc_capacity_mw`` + ``dc_ac_ratio`` — the DC nameplate and ILR → the AC export
        rating (:func:`ac_rating_from_dc`), the reactive-capability base (the inverter
        efficiency loss is NOT re-applied — it already lives in ``solar_resource``).
      * ``gridcode.pf_range`` — the grid-code reactive envelope the plant must hold.

    Computes, at the AC export rating:

      * the reactive HEADROOM the inverters can present, ``|Q| = P·tan(acos(pf))`` at the
        tighter (binding) pf endpoint (the deliverable ±Q capability); and
      * the reactive the grid code DEMANDS at that same pf — for a PV plant sized to
        deliver its own grid-code pf, these coincide at full export, so a pf-matched plant
        shows zero shortfall. A tighter DEMAND ``pf_required`` than the inverter's
        ``pf_capability`` surfaces a positive Mvar shortfall (the STATCOM/MSC sizing gap).

    Returns:
        ``(ReactiveCapabilityResult, SolarFaultContribution)`` — both ADVISORY
        (``bankable=False``); neither feeds the finance engine. The reactive result is a
        CLOSED-FORM headroom screen (``method="closed_form_solar"``); the fault
        contribution flags solar as a current-limited, non-synchronous source.

    Raises:
        ValueError: for a missing/ill-formed DC rating, ILR, or grid-code pf_range
            (CESSPIT — no silent defaults, NO SPURIOUS PASS).
    """
    dc_capacity_mw = grid_tech_block.get("dc_capacity_mw")
    dc_ac_ratio = grid_tech_block.get("dc_ac_ratio")
    ac_rating_mva = ac_rating_from_dc(dc_capacity_mw, dc_ac_ratio)
    # ac_rating_from_dc already validated both are positive numbers — coerce to concrete
    # floats for the notes string (mypy cannot narrow the config-sourced value).
    dc_mwp = _coerce_float(dc_capacity_mw)
    ilr = _coerce_float(dc_ac_ratio)

    pf_lag, pf_lead = _pf_range_from_gridcode(grid_tech_block)
    # The binding pf magnitude (the tighter reactive demand) is the smaller |pf|.
    pf_required = min(abs(pf_lag), abs(pf_lead))

    # The inverter's own reactive capability pf. Defaults to the grid-code requirement
    # (a PV plant is typically specified to deliver exactly the code pf); an explicit
    # ``pf_capability`` (a tighter inverter Q-envelope) overrides it when declared.
    pf_capability = grid_tech_block.get("pf_capability")
    pf_cap = pf_required
    if _is_number(pf_capability):
        pf_cap_candidate = abs(_coerce_float(pf_capability))
        if 0.0 < pf_cap_candidate <= 1.0:
            pf_cap = pf_cap_candidate

    # Reactive figures at the AC export rating (P ≈ AC rating at unity-ish export). The
    # DEMAND is Q at the required pf; the AVAILABLE headroom is Q at the inverter pf.
    mvar_required = ac_rating_mva * pf_to_qp_ratio(pf_required)
    mvar_available = ac_rating_mva * pf_to_qp_ratio(pf_cap)

    reactive = ReactiveCapabilityResult.from_screen(
        pf_required_min=pf_lag,
        pf_required_max=pf_lead,
        mvar_required=mvar_required,
        mvar_available=mvar_available,
        pf_at_poc=pf_cap,
        governing_p_mw=ac_rating_mva,
        governing_grid_v_pu=None,
        governing_converged=True,
        method="closed_form_solar",
        provenance=provenance,
        notes=(
            "Solar PV closed-form reactive-capability headroom at the AC export rating "
            f"({ac_rating_mva:g} MVA = DC {dc_mwp:g} MWp / ILR "
            f"{ilr:g}). Mvar shortfall is the gap between the grid-code "
            "reactive DEMAND and the inverter Q-envelope — the STATCOM/MSC sizing figure. "
            "Design-stage screen; confirm with the utility PQ requirement + base case."
        ),
    )
    fault = solar_fault_contribution(ac_rating_mva, fault_current_pu=fault_current_pu)
    return reactive, fault


def _coerce_float(value: Any) -> float:
    """Coerce a validated numeric config value to ``float`` (mypy-narrowing helper).

    Callers guard with :func:`_is_number` / :func:`_is_positive_number` first, so this is
    only reached for a real int/float; it exists to give mypy a concrete ``float`` from a
    config-sourced ``Any`` without scattering ``cast`` at each call site.
    """
    return float(value)


def _is_number(value: Any) -> bool:
    """True for a real int/float (never a bool)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_positive_number(value: Any) -> bool:
    """True for a real int/float strictly greater than zero."""
    return _is_number(value) and float(value) > 0.0


__all__ = [
    "SOLAR_TECH",
    "DEFAULT_FAULT_CURRENT_PU",
    "SolarFaultContribution",
    "is_solar_capability_tech",
    "ac_rating_from_dc",
    "solar_fault_contribution",
    "screen_solar_capability",
]

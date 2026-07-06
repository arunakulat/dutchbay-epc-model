"""Combined frequency-droop study for a hybrid plant, with an ENPPC-style controller (#881).

This is the D5c dolphin. Where the D7 closed-form sizer
(:mod:`analytics.grid.frequency_response`) answers *how much active-power headroom does the
droop obligation cost the plant?*, this module answers the COMBINED-FLEET, EVENT question:

    for a given frequency event Δf, how does a plant power controller SPLIT the required
    P(f) response across the multiple droop-capable groups behind ONE point of connection,
    is each group's share physically deliverable (a wind group's spinning/de-load headroom,
    a BESS group's SOC-limited discharge energy), and does the post-event settling frequency
    sit inside the grid-code ride-through band?

It GENERALISES the Envision ENPPC (plant power controller) 6-group logic. The real ENPPC is
a SUPERVISORY plant-level controller: it partitions the plant into up to 6 dispatch GROUPS
and, on a frequency excursion, meets a PLANT-LEVEL P(f) obligation by dispatching active-power
setpoints to the groups in a configured PRIORITY ORDER (the ``ldDDU`` de-load / PFRR / FSM /
LFSM-O/-U modes). We take that as three config keys — ``ppc.groups`` (the group list), each
group's ``freq_droop_pct``, and ``p_priority_order`` (the PPC dispatch order). This is a PPC
AGGREGATE-FILL model, NOT a set of independent per-turbine governors: a higher-priority group
may be dispatched up to its full HEADROOM (the PPC override) to cover the shortfall a
lower-priority group cannot deliver, so the priority order is genuinely load-bearing.

The plant obligation + priority fill (the load-bearing math)
------------------------------------------------------------
On ``R`` (fraction) droop, a per-unit frequency deviation ``Δf/f_n`` beyond the dead-band
commands a ``(Δf/f_n)/R`` per-unit change in active power. Each group's OWN droop share is
``ΔP_g = (Δf/f_n)/R_g · P_rated_g``; the PLANT OBLIGATION the PPC must meet is their SUM (the
aggregate droop command). The PPC then walks ``p_priority_order`` and dispatches each group up
to its physical HEADROOM against the running residual obligation — ``take = min(headroom_g,
residual)`` — so an earlier, high-headroom group absorbs what a later, headroom-limited group
cannot. The delivered response is the SUM of the dispatched ΔP; ADEQUACY is whether it meets
the plant obligation — derived from PHYSICAL headroom, NEVER from any solver flag.

The available headroom per group (the maximum the PPC could dispatch it to):
  * UNDER-frequency → UP-regulation: a wind/solar group can ramp from its current output up to
    its rating (spinning / de-load headroom = ``rated_mw − output``); a BESS group's discharge
    is that converter power headroom, further ENERGY-capped by its SOC over the sustain window.
  * OVER-frequency → DOWN-regulation: a group backs its output off toward zero (headroom =
    current output). A BESS group can additionally CHARGE, but this study sizes the
    DISCHARGE-direction frequency reserve only, mirroring D5a's ``frequency_mwh`` reserve.

Because the plant obligation is the SUM of the per-group droop shares and each group is
dispatched up to its HEADROOM, the priority order changes the split (who is pushed to their
cap, hence which BESS group is SOC-limited-out) whenever any group is headroom-limited — that
reallocation is exactly the PPC's job. A plant-level slack that exceeds the TOTAL headroom
cannot be conjured: the response is capped by the physical fleet headroom (NO SPURIOUS PASS).

SOC reuse — the ONE shared battery energy model (D5a)
-----------------------------------------------------
A BESS group does NOT re-derive its own energy accounting. Its up-regulation (discharge)
headroom for frequency response is taken from the D5a shared SOC model
(:func:`analytics.grid.capabilities.bess_soc.bess_soc_state`) and allocated through the D5a
:func:`~analytics.grid.capabilities.bess_soc.split_reserves` as the DISCHARGE-direction
``frequency_mwh`` reserve — honouring the no-double-count invariant (the same MWh cannot be
claimed by firming AND frequency). The energy required to SUSTAIN the group's converter power
headroom (the maximum the PPC could dispatch it to) over the mandated response window
(``sustain_s``) is converted to MWh (``MW · sustain_s / 3600``) and that is what the SOC model
must cover; a BESS group whose SOC cannot sustain that headroom is capped to the MW its
dischargeable energy supports (it is SOC-limited-out when the PPC actually dispatches it there).

The ANDES dynamic solve (call-time only)
----------------------------------------
The per-group split, the SOC integration and the adequacy verdict are ALL pure Python and
run in the default (grid-free) install. When a caller opts into the dynamic study
(``run_dynamics=True``), an ANDES RMS frequency-event solve is run through the SHARED D4a
ride-through machinery (:func:`analytics.grid.ride_through.run_ride_through_case`) to
measure the dynamic frequency nadir/zenith — but that dynamic nadir is NOT modelled by the
D4a core yet (a shunt fault cannot apply a frequency excursion), so it returns an explicit
NOT-RUN (``dynamic_nadir_hz=None``) rather than a fabricated value. The CLOSED-FORM
per-group split + band compliance are the real, physically-grounded deliverables here.

CASPER / CESSPIT / NO-SPURIOUS-PASS
-----------------------------------
* CASPER — the split MATH is pure Python and imports NO grid library at module scope;
  ``andes`` is reached ONLY through the D4a ``_require_andes`` at call-time. The module
  imports cleanly WITHOUT the ``[grid]`` extra.
* CESSPIT — every input (the group list, each group's rating + droop %, the priority order,
  the event Δf, the SOC window) is strict-validated with an actionable, field-naming
  message and NO silent default. NaN / inf / bool-as-number are rejected like D5a.
* NO SPURIOUS PASS — the band-compliance and adequacy verdicts derive ONLY from physical
  evidence (delivered MW vs commanded MW, settling frequency vs band). Where a quantity is
  not established (the un-modelled dynamic nadir, a gate-off run) an explicit ``None`` /
  NOT-RUN with a stated reason is returned, never a fabricated pass.

ADVISORY / KPI-neutral
----------------------
Every result is design-stage ADVISORY (``bankable=False``) and NEVER feeds the finance
engine, so committed scenarios stay byte-identical. Results are produced ONLY when the
hybrid dynamic frequency flags are set; with the gate off the study returns a NOT-RUN
advisory and touches nothing.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence, TypeGuard

from analytics.contracts_v14 import FreqResponseResult, GroupDroopContribution
from analytics.grid.capabilities.bess_soc import bess_soc_state, split_reserves
from analytics.grid.frequency_response import NOMINAL_FREQ_HZ, freq_band_from_gridcode

#: Provenance stamped on the frequency-response study results (kept identical to the
#: contract default so the emitter and the contract never drift).
_FREQ_RESPONSE_PROVENANCE = (
    "In-house Python design-stage COMBINED frequency-droop study with an ENPPC-style "
    "plant controller: a frequency event Δf is split across the droop-capable groups "
    "(per-group freq_droop_pct, dispatched in p_priority_order), each group's "
    "droop-commanded P(f) capped at its physical headroom (wind spinning/de-load; BESS via "
    "the ONE shared D5a SOC / frequency reserve — no double-count), and the settling "
    "frequency screened against the grid-code ride-through band. Closed-form per-group "
    "split + band compliance are physical; the ANDES dynamic nadir is NOT modelled yet "
    "(returned NOT-RUN). ADVISORY / design-stage ONLY — NOT a dynamic RMS/EMT "
    "primary-frequency-response study against the utility base case, and NOT bankable."
)

#: Group technology tokens the controller recognises. A wind/solar group contributes from
#: its spinning/de-load (or curtailment) headroom; a BESS group is SOC-energy-limited.
_STORAGE_TECH = "bess"

#: Default mandated sustain window (s) a primary-frequency-response contribution must be
#: held for — the energy horizon a BESS group's SOC must cover. 15 s is a conventional
#: fast-frequency-response floor; the mandated value is read from config when present.
_DEFAULT_SUSTAIN_S = 15.0

#: A hair of numerical tolerance so a delivered response that equals its command to within
#: floating-point round-off is not spuriously judged inadequate. One-sided slack only.
_MW_TOL = 1e-9


def _is_number(value: Any) -> TypeGuard[int | float]:
    """True iff ``value`` is a real, FINITE (non-bool, non-NaN/inf) int/float.

    Finiteness is part of the guard so NaN / ±inf are REJECTED at every input boundary: a
    NaN droop / rating / Δf silently passes ``<``/``>`` comparisons and would let a bogus
    request yield a spurious adequacy PASS. Rejecting it here keeps the split honest
    (NO SPURIOUS PASS) — same rule as the D5a SOC model.
    """
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _require_positive(value: Any, field: str) -> float:
    """Return ``value`` as a positive float or raise a CESSPIT config error."""
    if not _is_number(value) or float(value) <= 0.0:
        raise ValueError(
            f"hybrid frequency response requires {field} to be a number > 0, got {value!r}."
        )
    return float(value)


def _require_nonneg(value: Any, field: str) -> float:
    """Return ``value`` as a non-negative float or raise a CESSPIT config error."""
    if not _is_number(value) or float(value) < 0.0:
        raise ValueError(
            f"hybrid frequency response requires {field} to be a number >= 0, got {value!r}."
        )
    return float(value)


def _require_fraction(value: Any, field: str) -> float:
    """Return ``value`` as a fraction in [0, 1] or raise a CESSPIT config error."""
    if not _is_number(value) or float(value) < 0.0 or float(value) > 1.0:
        raise ValueError(
            f"hybrid frequency response requires {field} to be a fraction in [0, 1], "
            f"got {value!r}."
        )
    return float(value)


def _group_tech(group: Mapping[str, Any], index: int) -> str:
    """Resolve a group's technology token (strict — no silent guess)."""
    raw = group.get("tech", group.get("type"))
    tech = str(raw).strip().lower() if raw is not None else ""
    if not tech:
        raise ValueError(
            f"hybrid frequency response requires ppc.groups[{index}] to declare a tech/type "
            "token (e.g. wind | solar | bess) so the group's headroom is resolved from the "
            "right physical model."
        )
    return tech


def _iter_groups(ppc: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return the ENPPC dispatch groups (strict, 1..6 mappings).

    Reads ``ppc.groups`` — the plant-controller group list. Strict (CESSPIT): an absent /
    empty / non-mapping list RAISES; the ENPPC generalises up to SIX groups, so more than
    six is rejected as a mis-configuration rather than silently truncated.
    """
    groups = ppc.get("groups")
    if not isinstance(groups, Sequence) or isinstance(groups, (str, bytes)):
        raise ValueError(
            "hybrid frequency response requires ppc.groups — the list of ENPPC dispatch "
            "groups (each with a rating + freq_droop_pct)."
        )
    out = [g for g in groups if isinstance(g, Mapping)]
    if not out:
        raise ValueError(
            "hybrid frequency response requires at least one mapping in ppc.groups; got an "
            "empty / non-mapping list."
        )
    if len(out) > 6:
        raise ValueError(
            f"hybrid frequency response ENPPC supports up to 6 dispatch groups, got "
            f"{len(out)} — check ppc.groups (the controller partitions the plant into "
            "at most six groups)."
        )
    return out


def _resolve_priority_order(
    ppc: Mapping[str, Any], group_names: Sequence[str]
) -> list[str]:
    """Resolve ``p_priority_order`` to a validated, complete permutation of the group names.

    Strict (CESSPIT): the order must be a list naming EXACTLY the ENPPC groups once each —
    a name not in the groups, a missing group, or a duplicate RAISES. This is the ENPPC
    active-power dispatch order; a silent default (e.g. declaration order) would hide a
    mis-specified controller, so it is required and fully validated.
    """
    order = ppc.get("p_priority_order")
    if not isinstance(order, Sequence) or isinstance(order, (str, bytes)):
        raise ValueError(
            "hybrid frequency response requires ppc.p_priority_order — the ENPPC "
            "active-power dispatch order (a list of the group names)."
        )
    order_list = [str(name) for name in order]
    if sorted(order_list) != sorted(group_names):
        raise ValueError(
            "hybrid frequency response ppc.p_priority_order must name EXACTLY the "
            f"ppc.groups once each. Groups={sorted(group_names)!r}, "
            f"order={sorted(order_list)!r} (a name missing, extra, or duplicated is a "
            "mis-configured controller)."
        )
    return order_list


def _group_droop(group: Mapping[str, Any], index: int) -> float:
    """Resolve a group's governor droop FRACTION from ``freq_droop_pct`` (strict, > 0).

    ``freq_droop_pct`` is a PERCENT (e.g. 4.0 = 4 % droop); the fraction is ``pct / 100``.
    Strict: a missing / non-positive / non-finite value RAISES — a zero/negative droop is a
    division-by-zero (infinite gain) that would fabricate an unbounded command.
    """
    pct = group.get("freq_droop_pct")
    if not _is_number(pct) or float(pct) <= 0.0:
        raise ValueError(
            f"hybrid frequency response requires ppc.groups[{index}].freq_droop_pct to be a "
            f"percent > 0 (e.g. 4.0 for 4 % droop), got {pct!r}."
        )
    return float(pct) / 100.0


def _group_current_output_mw(
    group: Mapping[str, Any], index: int, rated_mw: float
) -> float:
    """Resolve a group's pre-event active-power output (MW) — the down-regulation base.

    Prefers an explicit ``output_mw``; otherwise a ``dispatch_fraction`` of the rating
    (a de-loaded group runs below rating so it has UP-regulation spinning headroom). Strict:
    an ill-formed value RAISES; the output must lie within [0, rated_mw] (a group cannot
    export above its rating or below zero in this active-power screen). Defaults to full
    output (``rated_mw``) when NEITHER key is present — an explicit, documented "running at
    rating" declaration (the binding UP-regulation case: no spinning headroom), disclosed in
    the notes, not a silent pass.
    """
    output = group.get("output_mw")
    if _is_number(output):
        out = float(output)
    else:
        frac = group.get("dispatch_fraction")
        if frac is None:
            return rated_mw
        out = (
            _require_fraction(frac, f"ppc.groups[{index}].dispatch_fraction") * rated_mw
        )
    if out < 0.0 or out > rated_mw + _MW_TOL:
        raise ValueError(
            f"hybrid frequency response ppc.groups[{index}] output {out} MW is outside "
            f"[0, rated {rated_mw}] — an active-power output cannot exceed the rating or be "
            "negative."
        )
    return min(out, rated_mw)


def _droop_commanded_mw(
    *, abs_deviation_hz: float, droop: float, rated_mw: float, nominal_hz: float
) -> float:
    """The droop-implied |ΔP| (MW) a group is commanded for a |Δf| deviation.

    ``ΔP = (|Δf|/f_n)/R · P_rated`` — the exact per-group split a droop controller produces
    for a known frequency deviation. A positive magnitude (the direction is applied by the
    caller). Pure arithmetic; no clamping (headroom capping happens in the dispatch).
    """
    return (abs_deviation_hz / nominal_hz) / droop * rated_mw


def _bess_soc_supported_mw(
    group: Mapping[str, Any],
    *,
    power_headroom_mw: float,
    sustain_s: float,
    reference_year: int | None,
) -> tuple[float, bool]:
    """MW a BESS group can SUSTAIN as frequency reserve, via the ONE shared D5a SOC model.

    Under the PPC aggregate-fill model (Option B) the plant controller can dispatch a group
    up to its full CONVERTER POWER headroom (``power_headroom_mw`` = rating − current
    discharge output) to cover the plant obligation — not merely its own local droop share.
    So the SOC-energy limit is sized against that MAXIMUM the PPC could ask: sustaining
    ``power_headroom_mw`` for ``sustain_s`` seconds needs ``power_headroom_mw · sustain_s /
    3600`` MWh of DISCHARGE energy. That energy is requested from the D5a shared SOC model as
    the DISCHARGE-direction ``frequency_mwh`` reserve
    (:func:`analytics.grid.capabilities.bess_soc.split_reserves`) — honouring the
    no-double-count invariant, so the SAME MWh is never claimed by firming AND frequency.

    The MW the SOC can support is the ALLOCATED frequency energy back-converted over the
    window (``allocated_mwh · 3600 / sustain_s``); the group is SOC-BOUND when that is
    strictly below its converter power headroom (the SOC energy is the binding cap, not the
    power rating). We do NOT re-derive any battery energy accounting here — the usable-energy
    / dischargeable-headroom numbers come entirely from the shared D5a
    :func:`~analytics.grid.capabilities.bess_soc.bess_soc_state`.

    Returns ``(soc_supported_mw, soc_bound)`` where ``soc_bound`` is True iff the SOC energy
    caps the headroom below the converter power headroom.
    """
    soc_fraction = _require_fraction(
        group.get("soc_fraction"), "ppc.groups[].soc_fraction"
    )
    soc = bess_soc_state(
        group, soc_fraction=soc_fraction, reference_year=reference_year
    )
    energy_needed_mwh = power_headroom_mw * sustain_s / 3600.0
    # Request the sustain energy as the DISCHARGE-direction frequency reserve; any
    # concurrent firming reserve the group declares is charged to the SAME headroom, so the
    # allocation honours the no-double-count invariant (a frequency claim cannot borrow MWh
    # already committed to firming).
    firming_mwh = _require_nonneg(
        group.get("firming_reserve_mwh", 0.0), "ppc.groups[].firming_reserve_mwh"
    )
    split = split_reserves(
        soc,
        firming_mwh=firming_mwh,
        frequency_mwh=energy_needed_mwh,
        curtailment_mwh=0.0,
    )
    allocated_mwh = split.frequency_allocated_mwh
    soc_supported_mw = allocated_mwh * 3600.0 / sustain_s
    soc_bound = soc_supported_mw + _MW_TOL < power_headroom_mw
    return soc_supported_mw, soc_bound


def _group_headroom_mw(
    group: Mapping[str, Any],
    index: int,
    *,
    tech: str,
    rated_mw: float,
    over_frequency: bool,
    sustain_s: float,
    reference_year: int | None,
) -> tuple[float, bool]:
    """Physically-available |ΔP| (MW) a group can deliver in the event direction.

    This is the MAXIMUM the PPC could dispatch this group to cover the plant obligation
    (Option B), NOT the group's own local droop share:

    * OVER-frequency (``over_frequency=True``) → DOWN-regulation: the group backs its output
      off toward zero, so its headroom is its current output MW (the most it can shed). A
      BESS group's charge-direction absorption is out of scope for this discharge-reserve
      study, so it too is limited to backing off its current discharge output.
    * UNDER-frequency → UP-regulation: a wind/solar group can ramp from its current output up
      to its rating (its spinning / de-load headroom = ``rated_mw − output``). A BESS group's
      up-regulation is a DISCHARGE whose converter power headroom (``rated_mw − output``) is
      further energy-capped by its SOC via the shared D5a model.

    Returns ``(headroom_mw, soc_bound)`` — ``soc_bound`` True only when a BESS group's SOC
    ENERGY caps the up-regulation headroom below its converter power headroom.
    """
    output_mw = _group_current_output_mw(group, index, rated_mw)
    if over_frequency:
        # DOWN-regulation: shed generation down to zero — headroom is the current output.
        return output_mw, False
    # UP-regulation.
    power_headroom_mw = max(0.0, rated_mw - output_mw)
    if tech == _STORAGE_TECH:
        soc_supported_mw, soc_bound = _bess_soc_supported_mw(
            group,
            power_headroom_mw=power_headroom_mw,
            sustain_s=sustain_s,
            reference_year=reference_year,
        )
        # The binding cap is the SMALLER of the SOC-energy MW and the converter power
        # headroom; ``soc_bound`` records when the SOC energy is the binding constraint.
        return min(soc_supported_mw, power_headroom_mw), soc_bound
    # Wind / solar / other generation: spinning / de-load headroom up to the rating.
    return power_headroom_mw, False


def compute_group_droop_split(
    ppc: Mapping[str, Any],
    *,
    deviation_hz: float,
    gridcode: Mapping[str, Any] | None = None,
    nominal_hz: float = NOMINAL_FREQ_HZ,
    sustain_s: float = _DEFAULT_SUSTAIN_S,
    reference_year: int | None = None,
) -> tuple[list[GroupDroopContribution], float, float]:
    """Split a frequency event's P(f) response across the ENPPC groups (PURE — grid-free).

    This is the load-bearing ENPPC / PPC aggregate-fill math. For a signed frequency
    deviation ``deviation_hz`` (``Δf = f_event − f_n``; negative = under-frequency →
    up-regulation, positive = over-frequency → down-regulation):

      1. each group's OWN droop share is ``(|Δf|/f_n)/R_g · P_rated_g``; the PLANT OBLIGATION
         the PPC must meet is their SUM (the aggregate droop command);
      2. each group's physically-available HEADROOM (the maximum the PPC could dispatch it to)
         in the required direction is resolved (wind spinning/de-load; BESS via the shared D5a
         SOC — energy-limited);
      3. the PPC walks ``ppc.p_priority_order`` and dispatches each group up to its HEADROOM
         against the running residual obligation (``take = min(headroom_g, residual)``), so a
         higher-priority group with spare headroom covers the shortfall a lower-priority group
         cannot — the priority order is LOAD-BEARING (it changes who is pushed to their cap and
         hence which BESS group is SOC-limited-out whenever any group is headroom-limited).

    Args:
        ppc: the ENPPC block (``groups`` + ``p_priority_order``).
        deviation_hz: the SIGNED frequency deviation Δf (Hz) of the event.
        gridcode: the grid-code block (unused here; the band screen reads it separately).
        nominal_hz: nominal system frequency (Hz; > 0).
        sustain_s: the mandated response sustain window (s) a BESS group's SOC must cover.
        reference_year: the BESS SoH evaluation year (``None`` = end-of-life, binding case).

    Returns:
        ``(contributions, total_commanded_mw, total_delivered_mw)`` — the per-group line
        items (in ``p_priority_order``) and the aggregate plant obligation vs delivered |ΔP|.

    Raises:
        ValueError: on any strict input failure (CESSPIT — no silent defaults).
    """
    if nominal_hz <= 0.0:
        raise ValueError(f"nominal_hz must be > 0, got {nominal_hz!r}.")
    if not _is_number(deviation_hz):
        raise ValueError(
            f"hybrid frequency response requires deviation_hz to be a finite number, got "
            f"{deviation_hz!r}."
        )
    if float(sustain_s) <= 0.0:
        raise ValueError(f"sustain_s must be > 0 (seconds), got {sustain_s!r}.")

    groups = _iter_groups(ppc)
    resolved: list[dict[str, Any]] = []
    names: list[str] = []
    for index, group in enumerate(groups):
        name = str(group.get("name", f"group_{index}"))
        tech = _group_tech(group, index)
        rated_mw = _require_positive(
            group.get("rated_mw", group.get("rated_mva")),
            f"ppc.groups[{index}].rated_mw",
        )
        droop = _group_droop(group, index)
        resolved.append(
            {
                "name": name,
                "tech": tech,
                "rated_mw": rated_mw,
                "droop": droop,
                "raw": group,
                "index": index,
            }
        )
        names.append(name)

    order = _resolve_priority_order(ppc, names)
    by_name = {r["name"]: r for r in resolved}

    abs_dev = abs(float(deviation_hz))
    over_frequency = float(deviation_hz) > 0.0

    # First pass: each group's OWN droop command (its share of the aggregate plant
    # obligation) + its physical headroom (the MAXIMUM the PPC could dispatch it to). Both
    # are independent of the priority order.
    commanded: dict[str, float] = {}
    headroom: dict[str, float] = {}
    soc_bound: dict[str, bool] = {}
    for r in resolved:
        cmd = _droop_commanded_mw(
            abs_deviation_hz=abs_dev,
            droop=r["droop"],
            rated_mw=r["rated_mw"],
            nominal_hz=nominal_hz,
        )
        hr, sb = _group_headroom_mw(
            r["raw"],
            r["index"],
            tech=r["tech"],
            rated_mw=r["rated_mw"],
            over_frequency=over_frequency,
            sustain_s=sustain_s,
            reference_year=reference_year,
        )
        commanded[r["name"]] = cmd
        headroom[r["name"]] = hr
        soc_bound[r["name"]] = sb

    # The PLANT obligation is the aggregate droop command (Σ per-group droop shares). The PPC
    # meets it by dispatching groups in PRIORITY ORDER, each group covering up to its full
    # HEADROOM of the residual — NOT merely its own droop share. So a high-priority group with
    # spare headroom absorbs the shortfall a lower-priority group cannot deliver, and the
    # order is LOAD-BEARING: promoting a high-headroom group ahead of a headroom-limited one
    # changes who is dispatched to their cap (e.g. which BESS group gets SOC-limited-out).
    total_commanded = sum(commanded.values())
    residual = total_commanded
    delivered: dict[str, float] = {}
    for name in order:
        take = max(0.0, min(headroom[name], residual))
        delivered[name] = take
        residual -= take

    contributions = [
        GroupDroopContribution(
            name=by_name[name]["name"],
            tech=by_name[name]["tech"],
            rated_mw=by_name[name]["rated_mw"],
            droop=by_name[name]["droop"],
            commanded_mw=commanded[name],
            headroom_mw=headroom[name],
            delivered_mw=delivered[name],
            # A BESS group is SOC-LIMITED-OUT when the PPC actually dispatched it up to its
            # SOC-bound headroom (the SOC energy — not the power rating — capped what it could
            # deliver). A group the PPC never pushed to its cap is NOT reported SOC-limited
            # even if its SOC would have bound at higher demand (physical evidence only).
            soc_limited=soc_bound[name]
            and delivered[name] + _MW_TOL >= headroom[name]
            and headroom[name] > 0.0,
        )
        for name in order
    ]
    total_delivered = sum(c.delivered_mw for c in contributions)
    return contributions, total_commanded, total_delivered


def _settling_frequency_hz(
    *,
    deviation_hz: float,
    total_commanded_mw: float,
    total_delivered_mw: float,
    nominal_hz: float,
) -> float | None:
    """Estimate the post-response SETTLING frequency (Hz) from the delivered response.

    A closed-form quasi-steady estimate: the plant's aggregate droop restores frequency in
    proportion to the FRACTION of the commanded response it actually delivered. If it
    delivers the full command, the frequency returns from the event deviation back toward
    nominal by the full droop correction; a partial delivery leaves a proportional residual
    deviation. Returns ``None`` when there is no command to respond to (a zero-deviation /
    zero-command event has no settling point to estimate — an honest NOT-RUN, not 50 Hz by
    fiat).
    """
    if total_commanded_mw <= _MW_TOL:
        return None
    delivered_fraction = max(0.0, min(1.0, total_delivered_mw / total_commanded_mw))
    residual_deviation = float(deviation_hz) * (1.0 - delivered_fraction)
    return nominal_hz + residual_deviation


def run_hybrid_frequency_response(
    config: Mapping[str, Any],
    *,
    deviation_hz: float | None = None,
    run_dynamics: bool = False,
    nominal_hz: float = NOMINAL_FREQ_HZ,
    reference_year: int | None = None,
    provenance: str | None = None,
) -> FreqResponseResult:
    """Run the combined frequency-droop study for a hybrid plant and emit the advisory result.

    Reads the ENPPC block from ``config['grid']['ppc']`` (or a bare ``grid`` block), the
    grid-code frequency band, and the event Δf, then:

      1. splits the event's P(f) response across the groups (:func:`compute_group_droop_split`)
         — the per-group droop command capped at each group's physical headroom (BESS via the
         shared D5a SOC), dispatched in ``p_priority_order``;
      2. estimates the SETTLING frequency from the delivered fraction and screens it against
         the grid-code continuous ride-through band → a ``band_compliant`` verdict;
      3. judges ADEQUACY: whether the delivered response met the aggregate droop command.

    Both verdicts derive from PHYSICAL evidence (delivered vs commanded MW, settling
    frequency vs band), NEVER from a solver flag.

    Args:
        config: the scenario config (or its ``grid`` block). Reads ``grid.ppc`` (the ENPPC
            groups + priority order), the grid-code frequency band, ``grid.freq_event_hz``
            (the event frequency, used when ``deviation_hz`` is not passed), and
            ``grid.freq_response_sustain_s`` (the mandated sustain window).
        deviation_hz: the SIGNED event deviation Δf (Hz); when ``None`` it is derived from
            ``grid.freq_event_hz − nominal_hz`` (a config key is required — no silent event).
        run_dynamics: opt into the ANDES dynamic solve (default off). Even when on, the
            dynamic frequency nadir is NOT modelled by the D4a core yet, so it is reported
            NOT-RUN (``dynamic_nadir_hz=None``) — never a fabricated value.
        nominal_hz: nominal system frequency (Hz; > 0).
        reference_year: the BESS SoH evaluation year (``None`` = end-of-life, binding case).
        provenance: override the stamped provenance string.

    Returns:
        :class:`analytics.contracts_v14.FreqResponseResult` — ADVISORY (``bankable=False``);
        never feeds the finance engine (KPI-neutral).

    Raises:
        ValueError: on an absent ``grid`` / ``ppc`` block, an absent event deviation, or any
            strict per-group / priority-order input failure (CESSPIT — no silent defaults).
    """
    grid = _resolve_grid_block(config)
    ppc = grid.get("ppc")
    if not isinstance(ppc, Mapping):
        raise ValueError(
            "run_hybrid_frequency_response requires a grid.ppc block — the ENPPC plant "
            "controller (groups + p_priority_order); the study is meaningless without it."
        )

    dev_hz = _resolve_deviation_hz(grid, deviation_hz, nominal_hz)
    sustain_s = _resolve_sustain_s(grid)

    contributions, total_commanded, total_delivered = compute_group_droop_split(
        ppc,
        deviation_hz=dev_hz,
        gridcode=grid.get("gridcode"),
        nominal_hz=nominal_hz,
        sustain_s=sustain_s,
        reference_year=reference_year,
    )

    under_hz, over_hz, band_source = freq_band_from_gridcode(grid.get("gridcode"))
    settling_hz = _settling_frequency_hz(
        deviation_hz=dev_hz,
        total_commanded_mw=total_commanded,
        total_delivered_mw=total_delivered,
        nominal_hz=nominal_hz,
    )

    # BAND COMPLIANCE: the settling frequency must sit inside the continuous ride-through
    # band. None (NOT-RUN) when there was no command to respond to (no settling point to
    # judge) — never a spurious pass.
    band_compliant: bool | None
    if settling_hz is None:
        band_compliant = None
    else:
        band_compliant = bool(under_hz <= settling_hz <= over_hz)

    # ADEQUACY: the delivered response met the aggregate droop command (within tolerance).
    # None (NOT-RUN) when there was no command (zero-deviation event), else a physical
    # delivered-vs-commanded verdict.
    response_adequate: bool | None
    if total_commanded <= _MW_TOL:
        response_adequate = None
    else:
        response_adequate = bool(total_delivered + _MW_TOL >= total_commanded)

    # The dynamic ANDES nadir is NOT modelled by the D4a core yet (a shunt fault cannot apply
    # a frequency excursion). Even with the dynamic gate ON we return an explicit NOT-RUN
    # rather than fabricate a nadir — mirroring how ride_through reports HVRT/frequency.
    dynamic_nadir_hz: float | None = None
    dynamic_ran = False
    if run_dynamics:
        dynamic_ran, dynamic_nadir_hz = _attempt_dynamic_nadir(dev_hz)

    over_frequency = dev_hz > 0.0
    direction = (
        "over-frequency (down-regulation)"
        if over_frequency
        else ("under-frequency (up-regulation)")
    )
    n_soc_limited = sum(1 for c in contributions if c.soc_limited)
    return FreqResponseResult(
        contributions=tuple(contributions),
        deviation_hz=dev_hz,
        nominal_hz=nominal_hz,
        sustain_s=sustain_s,
        total_commanded_mw=total_commanded,
        total_delivered_mw=total_delivered,
        settling_frequency_hz=settling_hz,
        band_under_hz=under_hz,
        band_over_hz=over_hz,
        band_compliant=band_compliant,
        response_adequate=response_adequate,
        dynamic_ran=dynamic_ran,
        dynamic_nadir_hz=dynamic_nadir_hz,
        n_groups=len(contributions),
        n_soc_limited=n_soc_limited,
        method="enppc_group_droop",
        bankable=False,
        provenance=provenance if provenance is not None else _FREQ_RESPONSE_PROVENANCE,
        notes=(
            f"ENPPC {direction} split over {len(contributions)} group(s) for Δf={dev_hz:+.3f} "
            f"Hz: commanded {total_commanded:.3f} MW, delivered {total_delivered:.3f} MW "
            f"({n_soc_limited} SOC-limited). Settling "
            f"{'n/a' if settling_hz is None else f'{settling_hz:.3f} Hz'} vs band "
            f"[{under_hz}, {over_hz}] Hz ({band_source}) → "
            f"{_verdict_word(band_compliant, 'band')}; response "
            f"{_verdict_word(response_adequate, 'adequacy')}. Closed-form per-group split + "
            "band compliance are physical; the ANDES dynamic nadir is NOT modelled yet "
            "(dynamic_nadir_hz=None). ADVISORY — confirm the dynamic PFR with an RMS/EMT "
            "study against the utility base case."
        ),
    )


def _verdict_word(verdict: bool | None, label: str) -> str:
    """Human word for a tri-state verdict used in the result notes."""
    if verdict is None:
        return f"{label}=NOT-RUN"
    return f"{label}={'PASS' if verdict else 'FAIL'}"


def _resolve_grid_block(config: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return the ``grid`` block (or a grid-shaped mapping carrying a ``ppc``)."""
    if not isinstance(config, Mapping):
        raise ValueError(
            "run_hybrid_frequency_response requires a config mapping with a 'grid' block."
        )
    grid = config.get("grid")
    if isinstance(grid, Mapping):
        return grid
    if "ppc" in config:  # allow passing the grid block directly
        return config
    raise ValueError(
        "run_hybrid_frequency_response requires a 'grid' block (or a grid-shaped mapping "
        "with a 'ppc' key) — the hybrid plant controller."
    )


def _resolve_deviation_hz(
    grid: Mapping[str, Any], deviation_hz: float | None, nominal_hz: float
) -> float:
    """Resolve the signed event deviation Δf (Hz): explicit arg, else grid.freq_event_hz.

    Strict (CESSPIT): when no explicit ``deviation_hz`` is passed AND ``grid.freq_event_hz``
    is absent / ill-formed, RAISES — the study never assumes a nominal (zero-deviation)
    event, which would trivially "pass" everything.
    """
    if deviation_hz is not None:
        if not _is_number(deviation_hz):
            raise ValueError(
                f"deviation_hz must be a finite number (Hz), got {deviation_hz!r}."
            )
        return float(deviation_hz)
    event = grid.get("freq_event_hz")
    if not _is_number(event) or float(event) <= 0.0:
        raise ValueError(
            "hybrid frequency response requires an event frequency: pass deviation_hz or set "
            f"grid.freq_event_hz (Hz; > 0), got {event!r}. There is no silent nominal event."
        )
    return float(event) - nominal_hz


def _resolve_sustain_s(grid: Mapping[str, Any]) -> float:
    """Resolve the mandated response sustain window (s); default when absent.

    Prefers ``grid.freq_response_sustain_s`` (the mandated PFR hold time); defaults to
    :data:`_DEFAULT_SUSTAIN_S` when absent (a documented conventional floor). A PRESENT but
    non-positive / ill-formed value RAISES (CESSPIT — a bad explicit value is not silently
    ignored).
    """
    sustain = grid.get("freq_response_sustain_s")
    if sustain is None:
        return _DEFAULT_SUSTAIN_S
    return _require_positive(sustain, "grid.freq_response_sustain_s")


def _attempt_dynamic_nadir(
    deviation_hz: float,
) -> tuple[bool, float | None]:
    """Attempt the ANDES dynamic frequency-event solve via the SHARED D4a machinery.

    REUSES :func:`analytics.grid.ride_through.run_ride_through_case` (which reaches ``andes``
    through the shared ``_require_andes`` call-time guard) rather than re-scaffolding ANDES.
    The D4a core does NOT model a frequency excursion yet (a shunt fault cannot apply one),
    so the ``frequency`` ride-through case returns ``rode_through=None`` / NOT-RUN — and we
    propagate that as ``dynamic_nadir_hz=None`` with ``dynamic_ran`` reflecting whether the
    solve executed. We NEVER fabricate a nadir from the closed-form settling estimate: an
    un-measured dynamic quantity stays ``None`` (NO SPURIOUS PASS).
    """
    from analytics.grid.ride_through import run_ride_through_case

    result = run_ride_through_case(
        "frequency",
        run_dynamics=True,
        freq_excursion_hz=NOMINAL_FREQ_HZ + deviation_hz,
    )
    # The D4a frequency case is NOT-RUN (unmodelled): no dynamic nadir is available. Report
    # ran=False and nadir=None rather than fabricating a value.
    return bool(result.ran), None


__all__ = [
    "GroupDroopContribution",
    "compute_group_droop_split",
    "run_hybrid_frequency_response",
]

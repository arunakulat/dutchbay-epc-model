"""Shared BESS state-of-charge model + reserve-split accounting (D5a, #879).

This is the FOUNDATIONAL energy-accounting layer every multi-service BESS study
(firming, frequency response, curtailment absorption — the later D5c/D6 dolphins)
shares. It answers ONE question, once, so no downstream service re-derives (and
subtly diverges) it:

    given the battery's usable energy at a state-of-charge, how much MWh is available
    to DISCHARGE (above the min-SoC floor) and to CHARGE (below the max-SoC ceiling),
    and can a requested split across competing reserves be honoured WITHOUT the same
    MWh being claimed by more than one service?

The crux is the **no-double-count energy invariant**: the sum of the reserves
allocated in a given flow direction MUST be ``<=`` the usable headroom in that
direction at the given SoC. Discharge services (firming + frequency-response
down-regulation / droop discharge) draw from the energy ABOVE the min-SoC floor;
curtailment-absorption charges into the room BELOW the max-SoC ceiling. A request
that exceeds the direction headroom is REJECTED (the split is marked infeasible and
the shortfall is reported) rather than silently over-allocated — so the SAME MWh can
never be counted toward firming AND frequency AND curtailment simultaneously
(NO SPURIOUS PASS).

STANDALONE + ADVISORY (CASPER / KPI-neutral): this module imports NO grid library
(the accounting is pure Python — no ``pandapower`` / ``andes``), emits only
``bankable=False`` :class:`analytics.contracts_v14.BessSocState` /
:class:`analytics.contracts_v14.ReserveSplitResult`, and NEVER feeds the finance
engine, so committed scenarios stay byte-identical. A later dolphin wires this SoC
model into the D5c/D6 multi-service dispatch; here it is a config-level accounting
contract only.

STRICT (CESSPIT): every input (nameplate energy, SoH, SoC window, reserve requests)
is validated with an actionable, field-naming message and NO silent default — a
missing / ill-formed / out-of-window value is rejected, not assumed.
"""

from __future__ import annotations

from typing import Any, Mapping, TypeGuard

from analytics.contracts_v14 import BessSocState, ReserveSplitResult
from finance.tech_types import is_storage_type

#: Provenance stamped on the SoC / reserve-split accounting results (kept identical to
#: the contract default so the emitter and the contract never drift).
_BESS_SOC_PROVENANCE = (
    "In-house Python design-stage BESS state-of-charge + reserve-split accounting: "
    "usable energy = nameplate * SoH, bounded by the [min_soc, max_soc] operating "
    "window; multi-service reserves (firming / frequency-response / curtailment "
    "absorption) allocated against the direction-specific headroom with a strict "
    "no-double-count energy invariant. Advisory / config-level ONLY — NOT a dispatch "
    "optimisation and NOT the utility-accepted bankable study."
)

#: A hair of numerical tolerance so a request that equals its headroom to within
#: floating-point round-off (e.g. dischargeable computed as a product of fractions) is
#: NOT spuriously rejected. It is one-sided slack on the shortfall test only — it never
#: lets a genuinely over-sized request through (those exceed the headroom by far more).
_MWH_TOL = 1e-9


def _is_number(value: Any) -> TypeGuard[int | float]:
    """True iff ``value`` is a real (non-bool) int/float (narrows the type for mypy)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _require_positive(value: Any, field: str) -> float:
    """Return ``value`` as a positive float or raise a CESSPIT config error."""
    if not _is_number(value) or float(value) <= 0.0:
        raise ValueError(
            f"BESS SoC model requires {field} to be a number > 0, got {value!r}."
        )
    return float(value)


def _require_fraction(value: Any, field: str) -> float:
    """Return ``value`` as a fraction in [0, 1] or raise a CESSPIT config error."""
    if not _is_number(value) or float(value) < 0.0 or float(value) > 1.0:
        raise ValueError(
            f"BESS SoC model requires {field} to be a fraction in [0, 1], got {value!r}."
        )
    return float(value)


def _require_nonneg(value: Any, field: str) -> float:
    """Return ``value`` as a non-negative float or raise a CESSPIT config error.

    A reserve REQUEST of 0.0 is legitimate ("this service asks for nothing"); only a
    missing / negative / non-numeric request raises.
    """
    if not _is_number(value) or float(value) < 0.0:
        raise ValueError(
            f"BESS SoC model requires {field} to be a number >= 0, got {value!r}."
        )
    return float(value)


def _resolve_soh(grid: Mapping[str, Any], reference_year: int | None) -> float:
    """Resolve the governing SoH fraction from the grid block.

    Prefers an explicit ``grid.soh_fraction`` (a single fraction in (0, 1]); otherwise
    reads ``grid.soh_curve`` {year: fraction} and takes the ``reference_year`` entry
    (or, when ``reference_year`` is None, the LAST / end-of-life year — the binding,
    smallest-usable-energy case). STRICT: neither form present, or an out-of-range /
    ill-formed fraction, raises (no silent full-SoH default).
    """
    soh_direct = grid.get("soh_fraction")
    if _is_number(soh_direct):
        soh = float(soh_direct)
        if soh <= 0.0 or soh > 1.0:
            raise ValueError(
                f"BESS grid.soh_fraction must be in (0, 1], got {soh_direct!r}."
            )
        return soh

    curve = grid.get("soh_curve")
    if not isinstance(curve, Mapping) or not curve:
        raise ValueError(
            "BESS SoC model requires either grid.soh_fraction (a fraction in (0, 1]) "
            "or a non-empty grid.soh_curve {year: soh_fraction} — the usable energy "
            "degrades with state-of-health, so there is no silent full-SoH default."
        )

    parsed: dict[int, float] = {}
    for raw_year, raw_soh in curve.items():
        try:
            year = int(raw_year)
        except (TypeError, ValueError):
            raise ValueError(
                f"BESS grid.soh_curve has a non-integer year key {raw_year!r}."
            ) from None
        if not _is_number(raw_soh):
            raise ValueError(
                f"BESS grid.soh_curve[{raw_year!r}] must be a number, got {raw_soh!r}."
            )
        soh = float(raw_soh)
        if soh <= 0.0 or soh > 1.0:
            raise ValueError(
                f"BESS grid.soh_curve[{raw_year!r}] SoH fraction must be in (0, 1], "
                f"got {soh}."
            )
        parsed[year] = soh

    if reference_year is not None:
        if reference_year not in parsed:
            raise ValueError(
                f"BESS grid.soh_curve has no entry for reference_year={reference_year} "
                f"(available years: {sorted(parsed)})."
            )
        return parsed[reference_year]
    return parsed[max(parsed)]


def bess_soc_state(
    grid: Mapping[str, Any],
    *,
    soc_fraction: float,
    reference_year: int | None = None,
) -> BessSocState:
    """Build the usable-energy / headroom snapshot for a BESS at one state-of-charge.

    Reads from the per-site BESS ``grid`` block:
        ``type`` (must classify as storage — ``bess`` — via
            :func:`finance.tech_types.is_storage_type`; a block with no explicit ``type``
            is taken as ``bess``);
        ``energy_mwh`` (or ``nameplate_energy_mwh``) — the nameplate energy rating (> 0);
        ``soh_fraction`` OR ``soh_curve`` — the state-of-health at ``reference_year``
            (default: the curve's end-of-life year, the binding smallest-usable case);
        ``min_soc`` / ``max_soc`` — the operating SoC window (fractions in [0, 1],
            ``min_soc < max_soc``); STRICT, no silent default window.

    Args:
        soc_fraction: the current state-of-charge (fraction in [0, 1] of usable energy).
        reference_year: the operating year to evaluate SoH at; ``None`` uses the
            ``soh_curve`` end-of-life year.

    Returns:
        A :class:`BessSocState` with the SoH-degraded usable energy and the DISCHARGE /
        CHARGE headroom at the given SoC. ADVISORY (``bankable=False``).

    Raises:
        ValueError: if ``grid.type`` is not storage, or any input is missing / ill-formed
            / out of range, or ``soc_fraction`` falls outside the [min_soc, max_soc]
            operating window (CESSPIT — no silent defaults, NO SPURIOUS PASS).
    """
    tech_type = grid.get("type", "bess")
    if not is_storage_type(tech_type):
        raise ValueError(
            f"bess_soc_state is a STORAGE model; grid.type={tech_type!r} does not "
            "classify as storage (expected 'bess')."
        )

    nameplate = grid.get("energy_mwh")
    if not _is_number(nameplate):
        nameplate = grid.get("nameplate_energy_mwh")
    nameplate = _require_positive(
        nameplate, "grid.energy_mwh (or grid.nameplate_energy_mwh)"
    )

    soh = _resolve_soh(grid, reference_year)
    usable = nameplate * soh

    soc = _require_fraction(soc_fraction, "soc_fraction")
    min_soc = _require_fraction(grid.get("min_soc"), "grid.min_soc")
    max_soc = _require_fraction(grid.get("max_soc"), "grid.max_soc")
    if not min_soc < max_soc:
        raise ValueError(
            "BESS SoC model requires grid.min_soc < grid.max_soc, got "
            f"min_soc={min_soc}, max_soc={max_soc}."
        )
    if soc < min_soc or soc > max_soc:
        raise ValueError(
            f"BESS soc_fraction={soc} is outside the operating window "
            f"[{min_soc}, {max_soc}] — the reserve accounting is only defined inside the "
            "operating window (NO SPURIOUS PASS: an out-of-window SoC is rejected, not "
            "clamped)."
        )

    stored = usable * soc
    dischargeable = max(0.0, soc - min_soc) * usable
    chargeable = max(0.0, max_soc - soc) * usable

    return BessSocState(
        nameplate_energy_mwh=nameplate,
        soh_fraction=soh,
        usable_energy_mwh=usable,
        soc_fraction=soc,
        min_soc_fraction=min_soc,
        max_soc_fraction=max_soc,
        stored_energy_mwh=stored,
        dischargeable_mwh=dischargeable,
        chargeable_mwh=chargeable,
        method="closed_form",
        provenance=_BESS_SOC_PROVENANCE,
        notes=(
            f"Usable energy {nameplate:.3f} MWh * SoH {soh:.4f} = {usable:.3f} MWh; "
            f"SoC {soc:.4f} within window [{min_soc:.4f}, {max_soc:.4f}]. "
            f"Discharge headroom {dischargeable:.3f} MWh (above floor), charge headroom "
            f"{chargeable:.3f} MWh (below ceiling)."
        ),
    )


def split_reserves(
    soc: BessSocState,
    *,
    firming_mwh: float,
    frequency_mwh: float,
    curtailment_mwh: float,
) -> ReserveSplitResult:
    """Allocate competing reserves against a SoC snapshot with the no-double-count rule.

    Firming and frequency-response are DISCHARGE-direction services: together they draw
    from ``soc.dischargeable_mwh`` (the energy above the min-SoC floor). Curtailment
    absorption is a CHARGE-direction service: it draws from ``soc.chargeable_mwh`` (the
    room below the max-SoC ceiling). The two directions are physically distinct energy
    pools, so a split is feasible only when BOTH clear.

    The FOUNDATIONAL invariant enforced here: within each direction the sum of the
    requested reserves must be ``<=`` that direction's headroom. When it is not, the
    split is marked INFEASIBLE and the per-direction shortfall is reported; the granted
    MWh are clamped to the available headroom PROPORTIONALLY so no service is
    over-allocated and the SAME MWh is never claimed twice (NO SPURIOUS PASS).

    Args:
        soc: the :class:`BessSocState` the split is evaluated against.
        firming_mwh / frequency_mwh: requested DISCHARGE-direction reserves (MWh, >= 0).
        curtailment_mwh: requested CHARGE-direction reserve (MWh, >= 0).

    Returns:
        A :class:`ReserveSplitResult` with the per-service allocation, the per-direction
        requested / available / shortfall totals, and the ``feasible`` verdict. ADVISORY
        (``bankable=False``).

    Raises:
        ValueError: if any request is missing / negative / non-numeric (CESSPIT).
    """
    firming = _require_nonneg(firming_mwh, "firming_mwh")
    frequency = _require_nonneg(frequency_mwh, "frequency_mwh")
    curtailment = _require_nonneg(curtailment_mwh, "curtailment_mwh")

    discharge_requested = firming + frequency
    discharge_available = soc.dischargeable_mwh
    discharge_shortfall = max(0.0, discharge_requested - discharge_available)

    charge_requested = curtailment
    charge_available = soc.chargeable_mwh
    charge_shortfall = max(0.0, charge_requested - charge_available)

    # Allocate each service. When a direction is over-subscribed, clamp the grants to the
    # available headroom, splitting it PROPORTIONALLY to the requests so no service is
    # over-allocated and the total granted never exceeds the headroom (the same MWh is
    # never counted twice). A feasible direction grants every request in full.
    firming_alloc, frequency_alloc = _allocate_direction(
        firming, frequency, discharge_available, discharge_shortfall
    )
    curtailment_alloc = min(curtailment, charge_available)

    feasible = discharge_shortfall <= _MWH_TOL and charge_shortfall <= _MWH_TOL

    return ReserveSplitResult(
        soc=soc,
        firming_request_mwh=firming,
        frequency_request_mwh=frequency,
        curtailment_request_mwh=curtailment,
        firming_allocated_mwh=firming_alloc,
        frequency_allocated_mwh=frequency_alloc,
        curtailment_allocated_mwh=curtailment_alloc,
        discharge_requested_mwh=discharge_requested,
        discharge_available_mwh=discharge_available,
        discharge_shortfall_mwh=discharge_shortfall,
        charge_requested_mwh=charge_requested,
        charge_available_mwh=charge_available,
        charge_shortfall_mwh=charge_shortfall,
        feasible=feasible,
        method="closed_form",
        provenance=_BESS_SOC_PROVENANCE,
        notes=(
            "Discharge (firming+frequency) "
            f"{discharge_requested:.3f}/{discharge_available:.3f} MWh "
            f"(shortfall {discharge_shortfall:.3f}); charge (curtailment) "
            f"{charge_requested:.3f}/{charge_available:.3f} MWh "
            f"(shortfall {charge_shortfall:.3f}). "
            + (
                "Feasible: every reserve is covered by its direction's headroom; no MWh "
                "is double-counted."
                if feasible
                else "INFEASIBLE: a direction is over-subscribed — the requested split "
                "would double-count MWh, so grants are clamped to the headroom."
            )
        ),
    )


def _allocate_direction(
    first: float,
    second: float,
    available: float,
    shortfall: float,
) -> tuple[float, float]:
    """Grant two same-direction reserves, clamping to ``available`` when over-subscribed.

    When the direction clears (``shortfall == 0``) each reserve is granted in full. When
    it is over-subscribed, the available headroom is split PROPORTIONALLY to the two
    requests so the grants sum to exactly ``available`` (never more) — no service is
    over-allocated and the shared MWh is never double-counted.
    """
    if shortfall <= _MWH_TOL:
        return first, second
    total = first + second
    if total <= 0.0:  # pragma: no cover - shortfall>0 implies total>available>=0
        return 0.0, 0.0
    return available * (first / total), available * (second / total)


__all__ = [
    "bess_soc_state",
    "split_reserves",
]

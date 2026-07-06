"""BESS (storage) grid-capability plug-in (D4d, #878).

The battery energy-storage system is a converter-interfaced STORAGE technology
(:func:`finance.tech_types.is_storage_type`). Its grid-facing capability differs from a
generation resource in two design-stage-relevant ways this plug-in models:

1. **PCS short-circuit contribution is a MANUAL config input, not a modelled quantity.**
   The BESS power-conversion-system (PCS) fault-current contribution is NOT carried in the
   OEM ``.dyr`` dynamic model per the DIgSILENT manual (the current-limited converter
   presents a controlled, not a machine-derived, fault current), so it CANNOT be derived
   from the dynamics core. It is taken as a strict per-site config input
   (``sc_contribution_pu`` — the sustained fault-current contribution in pu on the BESS
   rated-MVA base) with NO silent default (CESSPIT): an absent/ill-formed value is REJECTED
   rather than assumed. This contribution is fed into the D1 SCR screen
   (:func:`analytics.grid.short_circuit.screen_grid_strength`) as an addition to the fault
   level at the POC — a BESS PCS stiffens the grid it connects to, RAISING the SCR.

2. **Reactive / apparent-power capability DEGRADES with state-of-health (SoH).**
   As the battery ages, its usable capacity and the converter's continuous apparent-power
   rating shrink, so the reactive headroom the BESS can offer at the POC (its Mvar
   capability) is smaller at end-of-life than at beginning-of-life. This plug-in applies a
   ``soh_curve`` (year → SoH fraction) to both the apparent-power rating and the reactive
   headroom, and screens the SoH-degraded (year-15) reactive capability against the
   grid-code reactive demand via the D3 :class:`analytics.contracts_v14.ReactiveCapabilityResult`.

Both outputs are DESIGN-STAGE ADVISORY (``bankable=False``): the SCR band + reactive
verdict are screening figures, NOT the utility-accepted bankable connection study
(CEB/NSCC require PSS/E or PowerFactory against their confidential grid base case). Nothing
here feeds the finance engine, so committed scenarios stay byte-identical (KPI-neutral).

This is a STANDALONE plug-in: it exposes pure entry points and REUSES the D1 SCR screen +
the D3 ``ReactiveCapabilityResult`` rather than inventing new dynamics or result types
(CCCDIR). A later dolphin wires the per-tech dispatch into the ``evaluate_grid`` gateway.

CASPER: no grid library is imported at module-import time. The SCR screen this plug-in
calls guards ``pandapower`` at call-time and transparently falls back to its closed-form
Thevenin path when the ``[grid]`` extra is absent — so the default (grid-free) install
imports and runs this plug-in cleanly (``method="closed_form"``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, TypeGuard

from analytics.contracts_v14 import (
    GRID_EMT_CONFIRMATION_SCR,
    GRID_SCR_STRONG_ABOVE,
    GRID_SCR_WEAK_BELOW,
    GridStrengthResult,
    ReactiveCapabilityResult,
)
from analytics.grid.reactive_screen import _required_mvar_at_p, pf_to_qp_ratio
from analytics.grid.short_circuit import screen_grid_strength
from finance.tech_types import is_storage_type

#: Provenance stamped on the BESS capability screen results.
_BESS_CAPABILITY_PROVENANCE = (
    "In-house Python design-stage BESS grid-capability screen: MANUAL per-site PCS "
    "short-circuit contribution (sc_contribution_pu — NOT in the OEM .dyr per the DIgSILENT "
    "manual, so a strict config input) fed into the IEC 60909 SCR screen, plus an "
    "SoH-degraded reactive/PQ capability screen. NOT the utility-accepted bankable "
    "grid-connection study — CEB/NSCC require PSS/E or PowerFactory against their "
    "confidential grid base case."
)


def _is_number(value: Any) -> TypeGuard[int | float]:
    """True iff ``value`` is a real (non-bool) int/float (narrows the type for mypy)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _require_positive(value: Any, field: str) -> float:
    """Return ``value`` as a positive float or raise a CESSPIT config error."""
    if not _is_number(value) or float(value) <= 0.0:
        raise ValueError(
            f"BESS grid capability requires {field} to be a number > 0, got {value!r}."
        )
    return float(value)


def bess_sc_contribution_pu(grid: Mapping[str, Any]) -> float:
    """Return the MANUAL BESS PCS short-circuit contribution (pu on the rated-MVA base).

    STRICT (CESSPIT): the PCS fault-current contribution is not in the OEM ``.dyr`` (per
    the DIgSILENT manual), so it MUST be supplied as ``grid.sc_contribution_pu`` — a real,
    non-negative number. There is NO silent default: an absent/ill-formed value is rejected
    with an actionable, field-naming message rather than assumed (which would fabricate an
    SCR uplift the plant may not actually provide, or hide an omitted input).

    A value of 0.0 is ACCEPTED (an explicit "the PCS contributes no sustained fault
    current" declaration); it is only the missing / non-numeric / negative cases that raise.
    """
    value = grid.get("sc_contribution_pu")
    if not _is_number(value) or float(value) < 0.0:
        raise ValueError(
            "BESS grid capability requires an explicit grid.sc_contribution_pu "
            "(the PCS sustained fault-current contribution, pu on the BESS rated-MVA base; "
            ">= 0). The PCS short-circuit contribution is NOT carried in the OEM .dyr (per "
            "the DIgSILENT manual), so it is a STRICT config input with no silent default — "
            f"got {value!r}."
        )
    return float(value)


def _soh_at_reference_year(
    soh_curve: Mapping[Any, Any] | None,
    *,
    reference_year: int | None,
) -> tuple[float, int | None]:
    """Resolve the governing SoH fraction (and its year) from a ``soh_curve``.

    The ``soh_curve`` maps an operating year (int-like key) to a state-of-health FRACTION
    in (0, 1]. The governing year is:

      * ``reference_year`` when supplied (and present in the curve); else
      * the LAST (maximum) year in the curve — the end-of-life, worst-SoH point, which is
        the binding case for reactive headroom (year-15 headroom shrinks as SoH degrades).

    Returns ``(soh_fraction, governing_year)``. STRICT (CESSPIT):

      * an absent / empty / non-mapping curve raises (no silent "assume 100% SoH");
      * a requested ``reference_year`` that is not in the curve raises;
      * an SoH fraction outside (0, 1] raises.
    """
    if not isinstance(soh_curve, Mapping) or not soh_curve:
        raise ValueError(
            "BESS grid capability requires a non-empty grid.soh_curve "
            "{year: soh_fraction} — the reactive/apparent-power headroom degrades with "
            "state-of-health, so there is no silent full-SoH default."
        )

    parsed: dict[int, float] = {}
    for raw_year, raw_soh in soh_curve.items():
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
        governing_year = reference_year
    else:
        governing_year = max(parsed)
    return parsed[governing_year], governing_year


@dataclass(frozen=True)
class BessDegradedRating:
    """The SoH-degraded BESS ratings at the governing (worst-SoH) year (pure data).

    Fields
        governing_year: the operating year the degradation is evaluated at (the curve's
            end-of-life year, or the explicit ``reference_year``).
        soh_fraction: the state-of-health fraction (in (0, 1]) at that year.
        rated_mva_bol / rated_mva_soh: the converter apparent-power rating (MVA) at
            beginning-of-life and after SoH degradation (``rated_mva_bol * soh_fraction``).
        q_rated_mvar_bol / q_rated_mvar_soh: the reactive headroom (Mvar, ± symmetric)
            at beginning-of-life and after SoH degradation.
    """

    governing_year: int | None
    soh_fraction: float
    rated_mva_bol: float
    rated_mva_soh: float
    q_rated_mvar_bol: float
    q_rated_mvar_soh: float


def _resolve_q_rated_mvar_bol(grid: Mapping[str, Any], rated_mva: float) -> float:
    """Beginning-of-life reactive headroom (± Mvar) for the BESS PCS.

    Prefers an explicit ``grid.q_rated_mvar`` (the ± symmetric reactive rating, e.g. the
    Envision ±3 Mvar per 10 MW site). Otherwise derives it from ``grid.pf_range`` +
    ``rated_mva``: the binding (tighter, smaller-|pf|) endpoint gives the reactive headroom
    ``rated_mva * tan(acos(pf))``. STRICT (CESSPIT): neither form present raises.
    """
    q_rated = grid.get("q_rated_mvar")
    if _is_number(q_rated):
        q = abs(float(q_rated))
        if q <= 0.0:
            raise ValueError(
                "BESS grid.q_rated_mvar must be a non-zero reactive rating (Mvar), "
                f"got {q_rated!r}."
            )
        return q

    pf_range = grid.get("pf_range")
    if (
        isinstance(pf_range, (list, tuple))
        and len(pf_range) == 2
        and all(_is_number(v) for v in pf_range)
    ):
        pf_binding = min(abs(float(pf_range[0])), abs(float(pf_range[1])))
        if pf_binding <= 0.0 or pf_binding > 1.0:
            raise ValueError(
                f"BESS grid.pf_range endpoints must have magnitude in (0, 1], "
                f"got {pf_range!r}."
            )
        return rated_mva * pf_to_qp_ratio(pf_binding)

    raise ValueError(
        "BESS grid reactive rating is undetermined — supply either grid.q_rated_mvar "
        "(± Mvar) or grid.pf_range [lag, lead] (with grid.rated_mva)."
    )


def degrade_bess_rating(
    grid: Mapping[str, Any],
    *,
    reference_year: int | None = None,
) -> BessDegradedRating:
    """Apply the ``soh_curve`` to the BESS apparent-power + reactive ratings (pure Python).

    Reads ``grid.rated_mva`` (or ``grid.rated_mw`` as a fallback rating), the reactive
    headroom (``grid.q_rated_mvar`` or ``grid.pf_range``), and ``grid.soh_curve``; scales
    both ratings by the governing-year SoH fraction. The reactive headroom the BESS can
    offer at the POC therefore SHRINKS as SoH degrades — the year-15 figure is the binding
    reactive-capability case. No grid library; grid-free testable.
    """
    rated_mva = grid.get("rated_mva")
    if not _is_number(rated_mva):
        rated_mva = grid.get(
            "rated_mw"
        )  # MW ≈ MVA rating fallback for the converter base
    rated_mva = _require_positive(rated_mva, "grid.rated_mva (or grid.rated_mw)")

    q_bol = _resolve_q_rated_mvar_bol(grid, rated_mva)
    soh, governing_year = _soh_at_reference_year(
        grid.get("soh_curve"), reference_year=reference_year
    )
    return BessDegradedRating(
        governing_year=governing_year,
        soh_fraction=soh,
        rated_mva_bol=rated_mva,
        rated_mva_soh=rated_mva * soh,
        q_rated_mvar_bol=q_bol,
        q_rated_mvar_soh=q_bol * soh,
    )


def screen_bess_capability(
    grid: Mapping[str, Any],
    *,
    reference_year: int | None = None,
    use_pandapower: bool = True,
    scr_weak_below: float = GRID_SCR_WEAK_BELOW,
    scr_strong_above: float = GRID_SCR_STRONG_ABOVE,
    emt_confirmation_scr: float = GRID_EMT_CONFIRMATION_SCR,
    provenance: str = _BESS_CAPABILITY_PROVENANCE,
) -> tuple[GridStrengthResult, ReactiveCapabilityResult]:
    """Screen a BESS site's grid capability: SCR (with PCS contribution) + SoH reactive PQ.

    Args:
        grid: the per-site BESS ``grid`` interface block. Reads:
            ``type`` (must classify as storage — ``bess`` — via
                :func:`finance.tech_types.is_storage_type`);
            ``poc_voltage_kv`` (kV; > 0) and the SCR-screen Thevenin inputs
                (``source_fault_level_mva``, ``source_rx``, ``connection_r_ohm``,
                ``connection_x_ohm``);
            ``rated_mva`` (or ``rated_mw``) — the SCR denominator + converter base;
            ``sc_contribution_pu`` (STRICT — the manual PCS fault-current contribution);
            the reactive rating (``q_rated_mvar`` or ``pf_range``); the grid-code reactive
            demand (``pf_range`` / ``gridcode.pf_range``); and ``soh_curve``.
        reference_year: the operating year to evaluate SoH degradation at; ``None``
            (default) uses the curve's end-of-life (last) year — the binding case.
        use_pandapower: forwarded to the SCR screen; when False (or the extra is absent)
            the closed-form Thevenin fallback is used.

    Returns:
        ``(GridStrengthResult, ReactiveCapabilityResult)`` — the SCR band (with the PCS
        short-circuit contribution folded into the POC fault level) and the SoH-degraded
        reactive-capability verdict. Both are ADVISORY (``bankable=False``); neither feeds
        the finance engine.

    Raises:
        ValueError: if ``grid.type`` does not classify as storage, or any strict input
            (``sc_contribution_pu``, ``soh_curve``, ratings, reactive/grid-code demand) is
            absent or ill-formed (CESSPIT — no silent defaults).
    """
    tech_type = grid.get("type", "bess")
    if not is_storage_type(tech_type):
        raise ValueError(
            f"screen_bess_capability is a STORAGE plug-in; grid.type={tech_type!r} does "
            "not classify as storage (expected 'bess'). Route a generation tech to its own "
            "capability plug-in."
        )

    poc_kv = _require_positive(grid.get("poc_voltage_kv"), "grid.poc_voltage_kv")
    rated = degrade_bess_rating(grid, reference_year=reference_year)
    sc_pu = bess_sc_contribution_pu(grid)

    # The PCS sustained fault-current contribution (pu on the BESS rated-MVA base) is an
    # apparent-power contribution to the fault level at the POC: S_pcs = sc_pu * rated_mva.
    # A current-limited converter's contribution does NOT degrade with SoH the way the
    # continuous rating does (it is set by the converter current limit, which is a hardware
    # constant), so the BoL rating is used for the fault contribution. Folding it into the
    # source fault level stiffens the grid the SCR screen sees → a higher (better) SCR.
    pcs_sc_mva = sc_pu * rated.rated_mva_bol
    source_fault_mva = (
        _require_positive(
            grid.get("source_fault_level_mva"), "grid.source_fault_level_mva"
        )
        + pcs_sc_mva
    )

    strength = screen_grid_strength(
        poc_voltage_kv=poc_kv,
        source_fault_level_mva=source_fault_mva,
        source_rx=float(grid.get("source_rx", 0.1)),
        connection_r_ohm=float(grid.get("connection_r_ohm", 0.0)),
        connection_x_ohm=float(grid.get("connection_x_ohm", 0.5)),
        plant_rating_mva=rated.rated_mva_bol,
        scr_weak_below=scr_weak_below,
        scr_strong_above=scr_strong_above,
        emt_confirmation_scr=emt_confirmation_scr,
        use_pandapower=use_pandapower,
        provenance=provenance,
    )

    reactive = _screen_bess_reactive(grid, rated, provenance=provenance)
    return strength, reactive


def _grid_code_pf_range(grid: Mapping[str, Any]) -> tuple[float, float, float]:
    """Return (pf_binding, pf_min, pf_max) for the grid-code reactive demand.

    Prefers ``grid.gridcode.pf_range`` (the D2 structured location); falls back to a
    top-level ``grid.pf_range``. STRICT (CESSPIT): an absent/ill-formed range raises.
    """
    gridcode = grid.get("gridcode")
    pf_range = None
    if isinstance(gridcode, Mapping):
        pf_range = gridcode.get("pf_range")
    if pf_range is None:
        pf_range = grid.get("pf_range")
    if (
        not isinstance(pf_range, (list, tuple))
        or len(pf_range) != 2
        or not all(_is_number(v) for v in pf_range)
    ):
        raise ValueError(
            "BESS reactive screen requires a grid-code pf_range [lag, lead] "
            "(grid.gridcode.pf_range or grid.pf_range) — the reactive demand the BESS must "
            "hold at the POC."
        )
    pf_min, pf_max = float(pf_range[0]), float(pf_range[1])
    pf_binding = min(abs(pf_min), abs(pf_max))
    if pf_binding <= 0.0 or pf_binding > 1.0:
        raise ValueError(
            f"BESS grid-code pf_range endpoints must have magnitude in (0, 1], "
            f"got {pf_range!r}."
        )
    return pf_binding, pf_min, pf_max


def _screen_bess_reactive(
    grid: Mapping[str, Any],
    rated: BessDegradedRating,
    *,
    provenance: str,
) -> ReactiveCapabilityResult:
    """Screen the SoH-degraded reactive headroom against the grid-code PQ demand.

    The grid-code reactive demand at the BESS's full active power is
    ``P * tan(acos(pf_binding))``; the AVAILABLE reactive is the SoH-degraded headroom
    ``q_rated_mvar_soh``. The active power at which the demand is evaluated is the degraded
    apparent-power rating (a BESS at unity-ish pf can export close to its MVA rating), so
    the demand itself also reflects the shrunk SoH rating. Reuses the D3
    :class:`ReactiveCapabilityResult` (CCCDIR). Governing corner is treated as converged
    (no load-flow is run in this closed-form capability screen).
    """
    pf_binding, pf_min, pf_max = _grid_code_pf_range(grid)
    # Active power the reactive demand is referenced to: the SoH-degraded MVA rating (the
    # BESS's continuous export capability at end-of-life). tan(acos(pf)) on this gives the
    # Mvar the code demands; the degraded headroom is what the PCS can actually offer.
    p_ref_mw = rated.rated_mva_soh
    mvar_required = _required_mvar_at_p(p_ref_mw, pf_binding)
    mvar_available = rated.q_rated_mvar_soh

    return ReactiveCapabilityResult.from_screen(
        pf_required_min=pf_min,
        pf_required_max=pf_max,
        mvar_required=mvar_required,
        mvar_available=mvar_available,
        pf_at_poc=pf_binding,
        governing_p_mw=p_ref_mw,
        governing_grid_v_pu=None,
        governing_converged=True,
        method="closed_form",
        provenance=provenance,
        notes=(
            "BESS reactive capability at the SoH-degraded (year "
            f"{rated.governing_year}) rating: SoH={rated.soh_fraction:.4f}, "
            f"S_rated {rated.rated_mva_bol:.3f}→{rated.rated_mva_soh:.3f} MVA, "
            f"Q_headroom {rated.q_rated_mvar_bol:.3f}→{rated.q_rated_mvar_soh:.3f} Mvar. "
            "Mvar shortfall is the STATCOM/MSC sizing figure at end-of-life; the reactive "
            "headroom shrinks as SoH degrades. Design-stage screen — confirm with the "
            "utility's PQ requirement + base case."
        ),
    )


__all__ = [
    "bess_sc_contribution_pu",
    "degrade_bess_rating",
    "screen_bess_capability",
    "BessDegradedRating",
]

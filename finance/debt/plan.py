"""``plan_debt``: the debt engine's orchestrator."""

from __future__ import annotations

import math
from typing import Any, Dict, Optional, Sequence

from finance.debt.balloon import (
    _balloon_resolution_path,
    _refinance_disclosure,
    _resize_for_amortization,
    resolve_balloon_treatment,
    resolve_refinance_terms,
)
from finance.debt.constants import _BALLOON_TOL
from finance.debt.dscr_contract import (
    _build_dscr_periods,
    _normalize_operating_year,
    _operating_dscr_minimum,
)
from finance.debt.funding import _build_funding
from finance.debt.helpers import _as_float, _section_case_insensitive
from finance.debt.layer import _coverage_ratios, apply_debt_layer
from finance.debt.placeholders import _FORBID_TOY_FALLBACK_KEY
from finance.debt.sizing import _maybe_autosolve_dscr
from finance.debt.terms import (
    _resolve_first_operating_period,
    _warn_if_decorative_tranches,
)


def plan_debt(
    *,
    annual_rows: Sequence[Dict[str, Any]],
    config: Dict[str, Any],
    forbid_toy_fallback: bool = False,
) -> Dict[str, Any]:
    """Plan debt for the project using the v14 engine.

    When ``Financing_Terms.debt_sizing`` is ``dual_dscr`` / ``auto_dscr``, the gearing is
    first solved on the real schedule to hit ``target_dscr`` (capped at ``debt_ratio``),
    and the dual-DSCR (P50/P99) capacity detail is attached under ``dual_dscr``.

    The debt mix/rates are governed by ``Financing_Terms.mix`` + ``Financing_Terms.rates``;
    a ``Financing_Terms.debt_tranches`` list is not an engine input (see
    :func:`_warn_if_decorative_tranches`).

    ``forbid_toy_fallback`` (#733b): when True (a declared lender/IC run whose
    ``run_modes`` policy sets ``allow_toy_capex=False``), stamp the reserved
    :data:`_FORBID_TOY_FALLBACK_KEY` onto a LOCAL config copy so every downstream
    capex-extraction and cost-free-debt site hard-forbids the toy fallback even
    where the config opted in. Never mutates the caller's config; default False
    keeps every other run byte-identical.

    Period taxonomy (published unconditionally)
    ------------------------------------------
    The debt timeline is PERIOD-indexed and is NOT the operating-year axis. Its
    layout is ``[construction] * construction_periods`` + an optional synthetic
    half-year ``bridge`` period + one period per operating row + post-tenor
    padding. Three keys make that taxonomy explicit so a consumer holding only a
    ``debt_result`` can tell which periods are operating:

    - ``construction_periods`` (``int``) — the construction-period count as
      resolved by :func:`_resolve_construction_periods` and used by the engine.
      Same value as the legacy ``construction_years`` key, which is retained
      unchanged; this is the name the engine itself uses.
    - ``bridge_debt_period`` (``int | None``) — index of the synthetic bridge
      period, or ``None`` when the timeline carries no bridge. Same value as the
      legacy ``cfads_bridge_debt_period`` key, which is retained unchanged. The
      bridge bears scheduled service but maps to NO operating row; its service is
      folded into operating year 1 by ``dscr_by_year`` and by the pipeline's
      row enrichment.
    - ``first_operating_period`` (``int``) — the first debt period that maps to an
      operating row (see :func:`_resolve_first_operating_period`). Every period
      ``< first_operating_period`` is non-operating, so a DSCR at such a period is
      not a covenant observation.

    Index space of each published series
    ------------------------------------
    There is now exactly ONE DSCR index space — the PERIOD space (F-2). Every
    positional series below has length ``timeline_periods`` and shares index ``p``.

    - ``dscr_series`` — PERIOD-indexed, positional, full timeline length.
      ``dscr_series[p]`` is the DSCR of debt period ``p``; a period with no debt
      service, and every construction period, appears as ``None``.
    - ``dscr_periods`` — the SAME series with each entry labelled, so a consumer
      filters instead of indexing blindly. One dict per period, in period order:
      ``period``, ``dscr``, ``operating_year`` (``None`` for construction, the
      bridge and post-tenor padding), ``annual_row_index`` and ``covenant_dscr``
      (the per-year, bridge-fold-applied coverage — see below). This is the
      canonical surface; see :func:`_build_dscr_periods`.
    - ``debt_service_total``, ``interest_total``, ``total_service``,
      ``debt_outstanding``, ``senior_fee_usd``, ``balloon_resolution``,
      ``balloon_interest`` — PERIOD-indexed, positional, aligned 1:1 with
      ``dscr_series``. ``debt_outstanding`` is each period's OPENING balance; after
      maturity it is the balloon actually outstanding under its treatment, and
      ``senior_fee_usd`` is charged on that balance (see
      :func:`_balloon_resolution_path`). ``interest_total`` is scheduled interest
      only; the balloon's post-maturity interest is ``balloon_interest``.
    - ``annual_row_debt_period_map`` — ROW-indexed list; each entry maps an
      ``annual_row_index`` to its ``debt_period`` in the PERIOD space above. It is
      the DEFINITIONAL source of the operating-year labels in ``dscr_periods``.
    - ``dscr_by_year`` — keyed by operating YEAR (bridge service folded into
      year 1), not by period. Restated per entry as ``dscr_periods[*].covenant_dscr``.
    - ``raw_dscr_series`` — **DEPRECATED** (``REFACTOR-04`` shim lifecycle, one
      release). An exact alias of ``dscr_series``, retained so existing consumers
      keep working; see :func:`deprecated_raw_dscr_series`. New code must not use it.

    ``min_dscr``
    ------------
    The CONSERVATIVE minimum over two views, and both terms are load-bearing:

    1. the minimum over OPERATING periods of ``dscr_series`` — periods that map to
       no operating row are excluded, because a coverage ratio there is not a
       covenant observation (:func:`_operating_dscr_minimum`); and
    2. the minimum over ``dscr_by_year``, which FOLDS the orphaned bridge period's
       scheduled service into operating year 1.

    Term 2 is what the covenant is actually tested on and it can sit far below term
    1 (both CEB BESS scenarios: ~0.87-0.91 folded against a 1.3000 period floor).
    Dropping it — or "restricting to operating periods" in a way that bypasses it —
    would RAISE reported coverage and overstate lender protection.
    """
    rows = list(annual_rows)
    for row_index, row in enumerate(rows):
        _normalize_operating_year(row.get("year", row_index + 1), row_index)
    if forbid_toy_fallback:
        config = {**config, _FORBID_TOY_FALLBACK_KEY: True}
    _warn_if_decorative_tranches(config)
    config, dual_dscr_detail = _maybe_autosolve_dscr(config, rows)
    core = apply_debt_layer(params=config, annual_rows=rows)

    # ── Balloon treatment ──────────────────────────────────────────────────
    treatment = resolve_balloon_treatment(config)
    refi_terms = resolve_refinance_terms(config)  # None unless treatment == refinance

    if treatment == "amortize":
        config, core = _resize_for_amortization(config, rows, core)

    structural_balloon = _as_float(core.get("balloon_remaining"), 0.0)
    # Non-refinance treatments never read the terms; 0/0.0 here is a placeholder the
    # stream ignores, not a refinance default.
    refi_tenor, refi_premium = refi_terms if refi_terms is not None else (0, 0.0)
    balloon_path = _balloon_resolution_path(
        treatment=treatment,
        balloon=structural_balloon,
        senior_fee_rate=_as_float(core.get("senior_fee_rate"), 0.0),
        cfads_ext=core.get("cfads_extended", []) or [],
        debt_service_total=core.get("debt_service_total", []) or [],
        construction_periods=int(core.get("construction_periods", 0) or 0),
        timeline_periods=int(core.get("timeline_periods", 0) or 0),
        avg_rate=_as_float(core.get("avg_debt_rate"), 0.0),
        refi_tenor_years=refi_tenor,
        refi_rate_premium=refi_premium,
    )
    balloon_resolution = balloon_path["resolution"]
    balloon_residual = balloon_path["residual"]
    balloon_interest = balloon_path["interest"]

    # After maturity the engine's own series still hold the STRUCTURAL balloon: the
    # layer amortises scheduled principal only, so it cannot see the sweep, bullet
    # or refinance that retires the balloon. Overlay the balance actually
    # outstanding, and the senior fee on that balance, wherever the balloon path
    # governs the period; then re-net LLCR/PLCR on the corrected fee.
    debt_outstanding = list(core.get("debt_outstanding", []) or [])
    senior_fee_usd = list(core.get("senior_fee_usd", []) or [])
    for period, opening in enumerate(balloon_path["outstanding"]):
        if opening is None:
            continue
        if period < len(debt_outstanding):
            debt_outstanding[period] = opening
        fee = balloon_path["senior_fee"][period]
        if fee is not None and period < len(senior_fee_usd):
            senior_fee_usd[period] = fee
    llcr = _as_float(core.get("llcr"), 0.0)
    plcr = _as_float(core.get("plcr"), 0.0)
    if senior_fee_usd != list(core.get("senior_fee_usd", []) or []):
        period_row_map_for_fee = core.get("annual_row_debt_period_map", []) or []
        llcr, plcr = _coverage_ratios(
            cfads=[_as_float(m.get("cfads_usd"), 0.0) for m in period_row_map_for_fee],
            senior_fee_schedule=senior_fee_usd,
            annual_row_debt_period_map=period_row_map_for_fee,
            tenor=int(core.get("tenor_years", 0) or 0),
            debt_principal_total=sum(
                _as_float(v, 0.0)
                for v in (core.get("principal_after_idc", {}) or {}).values()
            ),
            llcr_discount_rate=_as_float(core.get("llcr_discount_rate"), 0.0),
            plcr_discount_rate=_as_float(core.get("plcr_discount_rate"), 0.0),
        )

    refinance_disclosure = (
        _refinance_disclosure(
            config=config,
            terms=refi_terms,
            balloon=structural_balloon,
            resolution=balloon_resolution,
            cfads_ext=core.get("cfads_extended", []) or [],
            senior_fee_usd=senior_fee_usd,
            avg_rate=_as_float(core.get("avg_debt_rate"), 0.0),
        )
        if refi_terms is not None and structural_balloon > _BALLOON_TOL
        else None
    )
    # balloon_remaining is the residual of the IDC-INCLUSIVE amortizing principal
    # (sum of principal_after_idc), so the fraction must use that same base — not the
    # pre-IDC debt_total, which mixes bases and overstates the balloon.
    amortizing_base = sum(
        _as_float(v, 0.0) for v in (core.get("principal_after_idc", {}) or {}).values()
    )
    if amortizing_base <= 0.0:  # fallback if IDC detail is absent
        amortizing_base = _as_float(core.get("debt_total"), 0.0)
    balloon_pct = structural_balloon / amortizing_base if amortizing_base > 0 else 0.0
    max_balloon_pct = _as_float(
        (_section_case_insensitive(config, "constraints") or {}).get("max_balloon_pct"),
        0.10,
    )
    balloon_covenant_breach = balloon_pct > max_balloon_pct

    principal_by = {
        k.lower(): float(v)
        for k, v in (core.get("principal_after_idc", {}) or {}).items()
    }
    idc_by = {
        k.lower(): float(v) for k, v in (core.get("idc_by_tranche", {}) or {}).items()
    }

    timeline = core.get("timeline_periods", 0)
    debt_service_total = core.get("debt_service_total", []) or []
    interest_total = core.get("interest_total", []) or []

    # Period taxonomy (see the docstring). CESSPIT single-resolver discipline: read
    # the count the ENGINE already resolved via _resolve_construction_periods inside
    # apply_debt_layer rather than re-deriving it here — a second derivation is
    # exactly how the published surface came to disagree with the engine. `core` is
    # the post-balloon-treatment core, so an "amortize" resize is reflected too.
    period_row_map = core.get("annual_row_debt_period_map", []) or []
    construction_periods = int(core.get("construction_periods", 0) or 0)
    bridge_raw = core.get("cfads_bridge_debt_period")
    bridge_debt_period = None if bridge_raw is None else int(bridge_raw)
    first_operating_period = _resolve_first_operating_period(
        period_row_map, construction_periods, bridge_debt_period
    )

    # F-2/F-3: ONE positional DSCR series, every entry labelled with the operating year
    # it belongs to. `core["dscr_series"]` is already period-indexed; the published
    # `dscr_series` is now that same series verbatim, so `dscr_series[debt_period]` is
    # finally the DSCR of `debt_period` (it used to be the COMPACTED list, whose
    # positions meant nothing — the F-2 collision).
    positional_dscr_series = list(core.get("dscr_series", []) or [])
    dscr_periods = _build_dscr_periods(
        positional_dscr_series, period_row_map, core.get("dscr_by_year") or {}
    )

    # PERIOD half of the covenant minimum, over OPERATING periods only (F-3): a period
    # that maps to no operating row carries no covenant observation. Proven not to move
    # `min_dscr` on any evaluable committed scenario — the bridge DSCR is strictly above
    # the operating-period minimum in every one — but the exclusion is correct on its own
    # terms and is what stops a sub-1.0 non-operating ratio setting a lender-facing floor.
    operating_min = _operating_dscr_minimum(dscr_periods)
    raw_min = operating_min if operating_min is not None else core.get("dscr_min", 0.0)
    # Single source of truth for the covenant minimum (round-5 #3). The lender-facing
    # min_dscr must agree with the bridge-corrected per-year covenant table (dscr_by_year),
    # not only the per-period series. The period series carries the sub-annual bridge
    # (period 2) and phantom interest-only (period 3) entries as separate values, whereas
    # dscr_by_year folds the orphaned bridge service into operating year 1. Report the
    # CONSERVATIVE minimum over both views so the headline can never overstate coverage
    # relative to the per-year table the covenant is actually tested on. The two DIVERGE
    # on several committed scenarios (both CEB BESS scenarios ~0.87-0.91 fold vs 1.30
    # period — the year-1 bridge/interest-only lead-in service folds into operating
    # year 1, verified economically real, not a double-count, in #806). The min() keeps
    # the headline honest wherever they diverge.
    #
    # THE FOLD IS LOAD-BEARING AND MUST NOT BE BYPASSED. Restricting the PERIOD half to
    # operating periods raises that half wherever a non-operating period held the minimum;
    # dropping the `by_year_min` term as well would raise the HEADLINE and overstate
    # lender protection. The fold is preserved verbatim below — same source
    # (`core["dscr_by_year"]`), same traversal, same `min()` — and `dscr_periods` now also
    # carries it per entry as `covenant_dscr` so consumers can see it without re-deriving.
    by_year_min: Optional[float] = None
    for _dscr in (core.get("dscr_by_year") or {}).values():
        if _dscr is None:
            continue
        _val = _as_float(_dscr, float("nan"))
        if math.isfinite(_val):
            by_year_min = _val if by_year_min is None else min(by_year_min, _val)
    min_dscr = min(raw_min, by_year_min) if by_year_min is not None else raw_min

    return {
        "construction_years": core.get("construction_periods", 0),
        "tenor_years": core.get("tenor_years", 0),
        "timeline_periods": timeline,
        "lkr": {
            "principal": principal_by.get("lkr", 0.0),
            "principal_m": principal_by.get("lkr", 0.0),
            "idc": idc_by.get("lkr", 0.0),
            "idc_m": idc_by.get("lkr", 0.0),
        },
        "usd": {
            "principal": principal_by.get("usd", 0.0),
            "principal_m": principal_by.get("usd", 0.0),
            "idc": idc_by.get("usd", 0.0),
            "idc_m": idc_by.get("usd", 0.0),
        },
        "dfi": {
            "principal": principal_by.get("dfi", 0.0),
            "principal_m": principal_by.get("dfi", 0.0),
            "idc": idc_by.get("dfi", 0.0),
            "idc_m": idc_by.get("dfi", 0.0),
        },
        "total_idc": core.get("total_idc_capitalized", 0.0),
        "total_idc_m": core.get("total_idc_capitalized", 0.0),
        "min_dscr": min_dscr,
        "principal_by_tranche": principal_by,
        "idc_by_tranche": idc_by,
        "audit_status": core.get("audit_status", "REVIEW"),
        "debt_outstanding": debt_outstanding,
        "debt_service_total": debt_service_total,
        "interest_total": interest_total,
        "total_service": debt_service_total,
        "senior_fee_usd": senior_fee_usd,
        "senior_fee_rate": core.get("senior_fee_rate", 0.0),
        "dscr_series": positional_dscr_series,
        # DEPRECATED (F-2, REFACTOR-04 shim lifecycle): an exact alias of `dscr_series`,
        # retained for one release. See `deprecated_raw_dscr_series` for the warning
        # surface and why the key itself cannot raise on access.
        "raw_dscr_series": list(positional_dscr_series),
        "dscr_by_year": core.get("dscr_by_year", {}),
        "annual_row_debt_period_map": core.get("annual_row_debt_period_map", []),
        "cfads_bridge_debt_period": core.get("cfads_bridge_debt_period"),
        "balloon_remaining": structural_balloon,
        "balloon_treatment": treatment,
        "balloon_resolution": balloon_resolution,
        "balloon_residual": balloon_residual,
        "balloon_pct": balloon_pct,
        "balloon_covenant_breach": balloon_covenant_breach,
        "max_balloon_pct": max_balloon_pct,
        "debt_schedules": core.get("debt_schedules", {}),
        "debt_total": core.get("debt_total", 0.0),
        "avg_debt_rate": core.get("avg_debt_rate", 0.0),
        "llcr": llcr,
        "plcr": plcr,
        "fx_min": core.get("fx_min"),
        "fx_max": core.get("fx_max"),
        "fx_avg": core.get("fx_avg"),
        "dual_dscr": dual_dscr_detail,
        "funding": _build_funding(config, core),
        # ── Period taxonomy (additive; see the docstring) ──────────────────
        # Appended AFTER every pre-existing key so the published mapping's
        # existing key order survives untouched as a prefix. These three are
        # emitted UNCONDITIONALLY (CASPER) — a taxonomy that appears only on
        # some config paths is the defect this publishes its way out of.
        # `construction_periods` and `bridge_debt_period` restate, under the
        # engine's own names, the values already carried by `construction_years`
        # and `cfads_bridge_debt_period`; both legacy keys are retained.
        "construction_periods": construction_periods,
        "bridge_debt_period": bridge_debt_period,
        "first_operating_period": first_operating_period,
        # ── Unified DSCR series (F-2/F-3; additive, appended last) ─────────
        # ONE positional series, each entry labelled with its `operating_year`
        # (`None` for construction, the bridge and post-tenor padding) and its
        # fold-applied `covenant_dscr`. Consumers FILTER on `operating_year`;
        # they never index a compacted list whose positions carry no meaning.
        "dscr_periods": dscr_periods,
        # ── Refinanced tranche (#1396; additive, appended last) ─────────────
        # None unless the balloon is refinanced. Its terms are a YAML assumption
        # with no term-sheet basis, and its coverage is tested separately from
        # the scheduled-service min_dscr.
        "refinance": refinance_disclosure,
        # ── Balloon interest (additive, appended last) ──────────────────────
        # PERIOD-indexed interest accrued on the balloon after maturity, inside
        # `balloon_resolution` (cash_sweep, bullet and refinance). Interest a
        # sweep could not pay is capitalised into `balloon_residual`.
        "balloon_interest": balloon_interest,
    }

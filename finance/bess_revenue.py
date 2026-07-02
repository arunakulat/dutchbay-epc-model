"""Battery-storage (BESS) revenue for the v14 cashflow — capacity-charge tolling.

A BESS is **not** a generation source: it has no capacity factor and no AEP, so the
cashflow's ``capacity_mw × capacity_factor × tariff`` revenue basis does not apply to
it. In the Sri Lanka / Ceylon Electricity Board (CEB) standalone-BESS tender — the
distributed 16 × 10 MW / 40 MWh programme, ``TR/REP&PM/ICB/2025/003/C`` — the asset
instead earns an **availability-based Capacity Charge** in LKR/MW/month, flat over the
contract term, with no per-kWh energy revenue (CEB dispatches the asset; the only
energy-linked cashflow is a one-way liquidated damage to CEB).

This module resolves ``type: bess`` technologies declared under
``generation.technologies`` and computes that capacity-charge revenue per operating
year. The cashflow adds the result to (generation) revenue. Absent any ``type: bess``
block it returns ``None`` / ``0.0``, so a wind/solar-only run is **byte-identical**.

Revenue, per BESS, per year within the contract term::

    annual_lkr = R_lkr_per_mw_month * power_mw * 12 * availability_factor * dispatchable_ratio

where ``R`` is the bid Capacity Charge Rate. ``availability_factor`` (default ``1.0``)
derates the charge when monthly availability falls below the 97% guarantee — at or
above 97% the tender applies no availability derate, hence the ``1.0`` default.
``dispatchable_ratio`` (default ``1.0``) is a STATIC MDSC derate (a constant haircut over
the whole life). Both ``availability_factor`` and ``dispatchable_ratio`` are derate factors
that must lie in ``[0, 1]``; a value outside that range is a config error and **raises** (it
is not silently clamped). The charge is **flat — no escalation** — per the tender, paid for
``contract_years`` (then zero).

A separate, TIME-VARYING degradation lever ``revenue.mdsc_fade_pct_annual`` (default ``0.0``
→ no fade → byte-identical) models the year-over-year state-of-health decay:
``soh(t) = max(mdsc_floor_soh, (1 - mdsc_fade_pct_annual) ** t)`` (0-based operating year
``t``; floor default 0.70). The yearly revenue is the flat charge × ``soh(t)``, so a scenario
that opts in sees the BESS revenue DECLINE over life (and, with an augmentation schedule,
recover after a cell top-up — see ``mdsc_soh_for_year``). The static ``dispatchable_ratio``
and the year-indexed ``soh(t)`` multiply.

NB: the round-trip-efficiency and functional-performance liquidated damages, and a
sub-97% availability month, are *downside* levers; they are exposed here as optional
multipliers (``availability_factor`` / ``dispatchable_ratio``) rather than modelled
from a dispatch simulation, which the engine does not run. BESS-2 (#486): a scenario that
has a measured/projected monthly availability can OPT IN to the tender's liquidated-damages
derate ``clip(1 - 2*(0.97 - MA), 0, 1)`` by supplying ``revenue.monthly_availability_pct``
in place of the static ``availability_factor`` (absent -> the static factor, unchanged).

This module covers two ``revenue.model`` values: ``capacity_charge`` (above) and
``energy_tariff`` — a BESS charged by an existing solar PV plant and paid a flat tariff
for night-peak energy exported (the CEB Solar+BESS night-peak scheme, 45.80 LKR/kWh)::

    annual_lkr = energy_mwh × 1000 × cycles_per_year × round_trip_efficiency
                 × availability_factor × tariff_lkr_per_kwh

flat over ``contract_years`` (``cycles_per_year`` defaults to 365 — one cycle/day;
``round_trip_efficiency`` to 0.85, NREL ATB 2024, #588). BESS-6 (#486): the charging energy carries NO cost here
because the scheme charges the BESS from a SEPARATE co-located solar PV plant the EPC owns;
``round_trip_efficiency`` already books the dispatch loss, so a charging-cost line would
double-count. Out of scope: the Kolonnawa 100 MW single-site
project — a CEB-owned night-peak supply procured via an EPC contract, i.e. a
construction-margin deal, not an operational tolling/tariff stream, so it does not belong
on this operational cashflow path at all.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional

#: The explicit per-technology type discriminator value marking a storage block.
BESS_TYPE = "bess"

#: Revenue models this module understands.
#:
#: * ``capacity_charge`` — availability tolling: ``R × power_mw × 12`` (LKR/MW/month),
#:   the CEB distributed standalone-BESS tender.
#: * ``energy_tariff`` — a BESS charged by an existing solar PV plant, paid a flat tariff
#:   for night-peak energy exported: ``energy_mwh × 1000 × cycles_per_year × RTE ×
#:   tariff_lkr_per_kwh`` (the CEB Solar+BESS night-peak scheme, 45.80 LKR/kWh).
SUPPORTED_BESS_REVENUE_MODELS = ("capacity_charge", "energy_tariff")

_MONTHS_PER_YEAR = 12.0
_KWH_PER_MWH = 1000.0
#: Default cycles/year for an energy-tariff BESS (one charge/discharge per day).
_DEFAULT_CYCLES_PER_YEAR = 365.0
#: Default AC-AC round-trip efficiency. Re-baselined 0.90 -> 0.85 (#588) to NREL ATB 2024's
#: representative utility-scale Li-ion figure (Cole & Karmakar, "Cost Projections for Utility-Scale
#: Battery Storage", NREL/ATB 2023-24) — a conservative mid-market value, versus the prior
#: Ember-2025 upper-end 0.90. This is the CANONICAL constant; ``finance.bess_lcos`` imports it
#: (single source of truth). Overridable per scenario via ``revenue.round_trip_efficiency``.
_DEFAULT_ROUND_TRIP_EFFICIENCY = 0.85
#: Default lower bound on the year-indexed state-of-health (MDSC) curve. LFP degrades
#: near-linearly to its ~70% warranty / end-of-life threshold, below which fade turns
#: non-linear and is unmodelled — so soh(t) floors here rather than extrapolating
#: (NextG / Eway LFP warranty bands). Overridable per scenario via revenue.mdsc_floor_soh.
_DEFAULT_MDSC_FLOOR_SOH = 0.70


def _nested_get(config: Mapping[str, Any], *path: str) -> Any:
    """Walk a nested mapping by ``path``; return ``None`` on any miss."""
    cur: Any = config
    for key in path:
        if not isinstance(cur, Mapping):
            return None
        cur = cur.get(key)
    return cur


def _as_float(value: Any) -> Optional[float]:
    """Coerce a config scalar to ``float``; ``None`` for absent/non-numeric/bool/non-finite.

    NaN and ±inf return ``None`` so they are caught by the callers' fail-loud guards
    rather than silently poisoning the capacity charge (and thence CFADS/IRR/DSCR).
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        coerced = float(value)
        return coerced if math.isfinite(coerced) else None
    return None


def _unit_factor(value: Any, *, tech: str, field: str) -> float:
    """Validate a downside multiplier in ``[0, 1]``; default ``1.0`` when absent.

    Both BESS downside levers (``availability_factor``, ``dispatchable_ratio``) are
    derate factors bounded by ``[0, 1]``. A value outside that range (e.g. ``97``
    instead of ``0.97``, or a stray sign) is a config error and **raises** rather than
    silently inflating or negating the capacity charge (CESSPIT fail-loud), symmetric
    with the module's other guards.
    """
    coerced = _as_float(value)
    if coerced is None:
        if value is None:
            return 1.0
        raise ValueError(
            f"generation.technologies['{tech}'].revenue.{field}={value!r} is not "
            "numeric; it is a derate factor in [0, 1] (e.g. 0.97)."
        )
    if not 0.0 <= coerced <= 1.0:
        raise ValueError(
            f"generation.technologies['{tech}'].revenue.{field}={coerced} is out of "
            "range; it is a derate factor and must be in [0, 1] (e.g. 0.97, not 97)."
        )
    return coerced


def _fade_rate(value: Any, *, tech: str) -> float:
    """Validate the annual MDSC fade rate in ``[0, 1)``; default ``0.0`` when absent.

    ``0.0`` (the absent default) means NO year-over-year fade, so a scenario that does not
    opt in is byte-identical. A value outside ``[0, 1)`` (e.g. ``1.1`` for 1.1% mis-entered
    as a percent instead of the decimal ``0.011``, or a value ``>= 1`` that would zero the
    asset in one year) is a config error and **raises** (CESSPIT fail-loud).
    """
    coerced = _as_float(value)
    if coerced is None:
        if value is None:
            return 0.0
        raise ValueError(
            f"generation.technologies['{tech}'].revenue.mdsc_fade_pct_annual={value!r} "
            "is not numeric; it is a decimal annual fade rate (e.g. 0.011 for 1.1%/yr)."
        )
    if not 0.0 <= coerced < 1.0:
        raise ValueError(
            f"generation.technologies['{tech}'].revenue.mdsc_fade_pct_annual={coerced} is "
            "out of range; it is a decimal annual fade rate in [0, 1) (e.g. 0.011 for "
            "1.1%/yr, not 1.1)."
        )
    return coerced


def _resolve_augmentation_events(value: Any, *, tech: str) -> List[Dict[str, Any]]:
    """Validate ``revenue.augmentation_schedule`` into a sorted list of events.

    Each event is ``{year, capex_usd[, restore_to_soh]}`` — a mid-life cell top-up that
    (a) incurs ``capex_usd`` (USD) in 1-based operating ``year`` and (b) restores the
    state-of-health to ``restore_to_soh`` (default ``1.0``), after which it re-fades.
    Absent (``None``) -> ``[]`` -> no augmentation -> byte-identical. Fail-loud (CESSPIT)
    on a non-list, a bad year (not a positive whole number), a negative ``capex_usd``, or
    a ``restore_to_soh`` outside ``[0, 1]``.
    """
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise ValueError(
            f"generation.technologies['{tech}'].revenue.augmentation_schedule must be a "
            "list of {year, capex_usd[, restore_to_soh]} events."
        )
    events: List[Dict[str, Any]] = []
    for i, ev in enumerate(value):
        if not isinstance(ev, Mapping):
            raise ValueError(
                f"generation.technologies['{tech}'].revenue.augmentation_schedule[{i}] "
                "must be a mapping {year, capex_usd[, restore_to_soh]}."
            )
        year = _as_float(ev.get("year"))
        if year is None or year != int(year) or year < 1:
            raise ValueError(
                f"generation.technologies['{tech}'].revenue.augmentation_schedule[{i}]"
                f".year={ev.get('year')!r} must be a positive whole operating year."
            )
        capex = _as_float(ev.get("capex_usd"))
        if capex is None or capex < 0:
            raise ValueError(
                f"generation.technologies['{tech}'].revenue.augmentation_schedule[{i}]"
                ".capex_usd must be a non-negative USD amount (the cell top-up cost)."
            )
        restore_raw = ev.get("restore_to_soh")
        restore = (
            1.0
            if restore_raw is None
            else _unit_factor(restore_raw, tech=tech, field="restore_to_soh")
        )
        events.append(
            {"year": int(year), "capex_usd": capex, "restore_to_soh": restore}
        )
    events.sort(key=lambda e: e["year"])
    return events


def _ld_availability_derate(pct: Any, *, tech: str) -> float:
    """The CEB tender's liquidated-damages availability derate for a monthly availability %.

    The standalone-BESS tender guarantees 97% monthly availability with a 2x-per-point LD
    below it: ``derate = clip(1 - 2 * (0.97 - MA), 0, 1)`` where ``MA`` is the availability
    FRACTION. A month at/above 97% yields 1.0 (no penalty); 94% yields 1 - 2x0.03 = 0.94.
    This is the BESS-2 (#486) opt-in alternative to the static ``availability_factor``: it is
    used only when a scenario supplies ``revenue.monthly_availability_pct`` (a measured or
    projected %), so the committed scenarios (which do not) stay byte-identical.
    """
    ma_pct = _as_float(pct)
    if ma_pct is None or not 0.0 <= ma_pct <= 100.0:
        raise ValueError(
            f"generation.technologies['{tech}'].revenue.monthly_availability_pct={pct!r} "
            "must be a percentage in [0, 100] (e.g. 94.0 for a 94% availability month)."
        )
    return min(1.0, max(0.0, 1.0 - 2.0 * (0.97 - ma_pct / 100.0)))


def _resolve_project_life_years(config: Mapping[str, Any]) -> Optional[int]:
    """Resolve the project operating life in years from the standard config paths.

    Returns ``None`` when no life is declared (so the BESS-5 contract-years guard is a no-op
    rather than a false positive on a minimal/synthetic config).
    """
    for path in (
        ("project", "life_years"),
        ("returns", "project_life_years"),
        ("timeline", "ops_years"),
        ("project", "project_life_years"),
    ):
        v = _as_float(_nested_get(config, *path))
        if v is not None and v > 0:
            return int(v)
    return None


def resolve_bess_specs(
    config: Mapping[str, Any],
) -> Optional[List[Dict[str, Any]]]:
    """Resolve capacity-charge specs for every ``type: bess`` technology.

    Scans ``generation.technologies`` for blocks whose ``type`` is ``"bess"`` and
    builds a normalised spec per block. Returns ``None`` when no such block exists, so
    the cashflow keeps its byte-identical wind/solar behaviour.

    Each BESS block must declare ``power_mw`` and a ``revenue`` sub-block with
    ``model: capacity_charge`` and ``capacity_charge_lkr_per_mw_month``; a missing or
    non-numeric value raises (CESSPIT fail-loud — a mis-keyed BESS must not silently
    earn zero). Optional: ``revenue.contract_years`` (default ``None`` → paid for the
    full project life), ``revenue.availability_factor`` and
    ``revenue.dispatchable_ratio`` (each default ``1.0``; a derate factor that must lie
    in ``[0, 1]`` — a value outside that range raises, it is not clamped).

    Args:
        config: A loaded scenario config mapping.

    Returns:
        A list of ``{technology, power_mw, r_lkr_per_mw_month, contract_years,
        availability_factor, dispatchable_ratio}`` dicts, or ``None`` if no BESS block
        is present.

    Raises:
        ValueError: A ``type: bess`` block is malformed (missing/invalid ``power_mw``,
            ``revenue``, ``model``, or ``capacity_charge_lkr_per_mw_month``).
    """
    techs = _nested_get(config, "generation", "technologies")
    if not isinstance(techs, Mapping):
        return None

    specs: List[Dict[str, Any]] = []
    for name, block in techs.items():
        if not isinstance(block, Mapping):
            continue
        if block.get("type") != BESS_TYPE:
            # A block that declares a BESS revenue model but is NOT typed as a BESS is a
            # mis-key that would silently earn zero — fail loud (CESSPIT). A plain
            # storage block (power/energy, no BESS revenue model) is just skipped.
            rev_block = block.get("revenue")
            if (
                isinstance(rev_block, Mapping)
                and rev_block.get("model") in SUPPORTED_BESS_REVENUE_MODELS
            ):
                raise ValueError(
                    f"generation.technologies['{name}'] declares a BESS revenue model "
                    f"({rev_block.get('model')!r}) but is not type: {BESS_TYPE!r}. Add "
                    f"`type: {BESS_TYPE}`, or remove the revenue block."
                )
            continue

        power_mw = _as_float(block.get("power_mw"))
        if power_mw is None or power_mw <= 0:
            raise ValueError(
                f"generation.technologies['{name}'] is type: bess but has no positive "
                "power_mw — a capacity charge needs the contracted power rating (MW)."
            )

        # Cross-assert the (informational) energy rating against power x duration so a
        # typo cannot masquerade as a valid spec — the capacity charge itself is
        # POWER-based (LKR/MW/month), so energy_mwh / duration_h only document the
        # 4-hour / 0.25C nature. Other reporting-only fields: capex_usd (the financed
        # capex is capex.usd_total, as for wind/solar) and availability_pct (the live
        # derate is revenue.availability_factor).
        energy_mwh = _as_float(block.get("energy_mwh"))
        duration_h = _as_float(block.get("duration_h"))
        if energy_mwh is not None and duration_h is not None:
            implied_mwh = power_mw * duration_h
            if implied_mwh <= 0 or abs(energy_mwh - implied_mwh) / implied_mwh > 0.01:
                raise ValueError(
                    f"generation.technologies['{name}']: energy_mwh={energy_mwh} does "
                    f"not reconcile with power_mw*duration_h={implied_mwh:.4f} (within "
                    "1%). Align the BESS rating."
                )

        revenue = block.get("revenue")
        if not isinstance(revenue, Mapping):
            raise ValueError(
                f"generation.technologies['{name}'] (type: bess) needs a 'revenue' "
                "block declaring the model and its parameters."
            )
        model = revenue.get("model")
        if model not in SUPPORTED_BESS_REVENUE_MODELS:
            raise ValueError(
                f"generation.technologies['{name}'].revenue.model={model!r} is not "
                f"supported; expected one of {SUPPORTED_BESS_REVENUE_MODELS}."
            )

        contract_years_raw = revenue.get("contract_years")
        contract_years: Optional[int] = None
        if contract_years_raw is not None:
            cy_float = _as_float(contract_years_raw)
            if cy_float is None or cy_float != int(cy_float) or cy_float <= 0:
                raise ValueError(
                    f"generation.technologies['{name}'].revenue.contract_years="
                    f"{contract_years_raw!r} is invalid; expected a positive whole "
                    "number of years."
                )
            contract_years = int(cy_float)
            # BESS-5 (#486): a BESS cannot earn its charge beyond the project's operating
            # horizon — guard contract_years against the resolved project life.
            project_life = _resolve_project_life_years(config)
            if project_life is not None and contract_years > project_life:
                raise ValueError(
                    f"generation.technologies['{name}'].revenue.contract_years="
                    f"{contract_years} exceeds the project life ({project_life} years); a "
                    "BESS contract cannot run past the project's operating horizon."
                )

        # availability_factor is a common static derate ([0, 1]). BESS-2 (#486): a scenario
        # that has actual/projected MONTHLY availability can OPT IN to the tender's
        # liquidated-damages formula via revenue.monthly_availability_pct instead of the
        # static factor. Absent (the committed case) -> the static factor -> byte-identical.
        monthly_avail = revenue.get("monthly_availability_pct")
        if monthly_avail is not None:
            availability = _ld_availability_derate(monthly_avail, tech=str(name))
        else:
            availability = _unit_factor(
                revenue.get("availability_factor"),
                tech=str(name),
                field="availability_factor",
            )
        # Year-indexed MDSC fade (default 0.0 -> no fade -> byte-identical). This is the
        # TIME-VARYING state-of-health decay, distinct from the STATIC dispatchable_ratio
        # derate above; the two multiply. floor_soh bounds the fade curve.
        fade = _fade_rate(revenue.get("mdsc_fade_pct_annual"), tech=str(name))
        floor_raw = revenue.get("mdsc_floor_soh")
        floor_soh = (
            _DEFAULT_MDSC_FLOOR_SOH
            if floor_raw is None
            else _unit_factor(floor_raw, tech=str(name), field="mdsc_floor_soh")
        )
        spec: Dict[str, Any] = {
            "technology": str(name),
            "model": model,
            "power_mw": power_mw,
            "contract_years": contract_years,
            "availability_factor": availability,
            "mdsc_fade_pct_annual": fade,
            "mdsc_floor_soh": floor_soh,
            # Mid-life cell top-ups (default [] -> no augmentation -> byte-identical).
            "augmentation_events": _resolve_augmentation_events(
                revenue.get("augmentation_schedule"), tech=str(name)
            ),
        }

        if model == "capacity_charge":
            r_lkr = _as_float(revenue.get("capacity_charge_lkr_per_mw_month"))
            if r_lkr is None or r_lkr < 0:
                raise ValueError(
                    f"generation.technologies['{name}'].revenue."
                    "capacity_charge_lkr_per_mw_month must be a non-negative number "
                    "(LKR/MW/month, the bid Capacity Charge Rate)."
                )
            spec["r_lkr_per_mw_month"] = r_lkr
            spec["dispatchable_ratio"] = _unit_factor(
                revenue.get("dispatchable_ratio"),
                tech=str(name),
                field="dispatchable_ratio",
            )
        elif model == "energy_tariff":
            if energy_mwh is None or energy_mwh <= 0:
                raise ValueError(
                    f"generation.technologies['{name}'].energy_mwh must be a positive "
                    "number for the energy_tariff model (it sets the energy exported "
                    "per cycle)."
                )
            tariff = _as_float(revenue.get("tariff_lkr_per_kwh"))
            if tariff is None or tariff < 0:
                raise ValueError(
                    f"generation.technologies['{name}'].revenue.tariff_lkr_per_kwh must "
                    "be a non-negative number (the night-peak export tariff)."
                )
            cycles = _as_float(revenue.get("cycles_per_year"))
            cycles = _DEFAULT_CYCLES_PER_YEAR if cycles is None else cycles
            if cycles <= 0:
                raise ValueError(
                    f"generation.technologies['{name}'].revenue.cycles_per_year="
                    f"{cycles} is invalid (must be > 0)."
                )
            rte_raw = revenue.get("round_trip_efficiency")
            spec["round_trip_efficiency"] = (
                _DEFAULT_ROUND_TRIP_EFFICIENCY
                if rte_raw is None
                else _unit_factor(
                    rte_raw, tech=str(name), field="round_trip_efficiency"
                )
            )
            spec["energy_mwh"] = energy_mwh
            spec["tariff_lkr_per_kwh"] = tariff
            spec["cycles_per_year"] = cycles
        else:  # pragma: no cover - guarded by the SUPPORTED_BESS_REVENUE_MODELS check
            raise AssertionError(f"unhandled BESS revenue model {model!r}")

        specs.append(spec)

    return specs or None


def _spec_annual_revenue_lkr(spec: Dict[str, Any]) -> float:
    """The flat annual BESS revenue (LKR) for one resolved spec, by its model."""
    model = spec["model"]
    if model == "capacity_charge":
        return float(
            spec["r_lkr_per_mw_month"]
            * spec["power_mw"]
            * _MONTHS_PER_YEAR
            * spec["availability_factor"]
            * spec["dispatchable_ratio"]
        )
    if model == "energy_tariff":
        return float(
            spec["energy_mwh"]
            * _KWH_PER_MWH
            * spec["cycles_per_year"]
            * spec["round_trip_efficiency"]
            * spec["availability_factor"]
            * spec["tariff_lkr_per_kwh"]
        )
    raise AssertionError(  # pragma: no cover - specs only carry supported models
        f"unhandled BESS revenue model {model!r}"
    )


def mdsc_soh_for_year(spec: Dict[str, Any], year_index: int) -> float:
    """The state-of-health (usable MDSC) factor for one operating year, in ``(0, 1]``.

    Without augmentation, ``soh(t) = max(floor_soh, (1 - mdsc_fade_pct_annual) ** t)``.
    With an ``augmentation_schedule``, the curve RESTORES to ``restore_to_soh`` at each
    event year and re-fades from there: for the most recent event at 0-based year ``e``,
    ``soh(t) = min(1.0, restore_to_soh * (1 - fade) ** (t - e))``. With the absent default
    fade ``0.0`` and no events this is exactly ``1.0`` (no degradation -> byte-identical),
    so a scenario that does not opt in is unchanged. ``year_index`` is 0-based (operating
    year 1 -> 0).

    Args:
        spec: A resolved BESS spec (carries ``mdsc_fade_pct_annual`` / ``mdsc_floor_soh`` /
            ``augmentation_events``).
        year_index: Zero-based operating-year index.

    Returns:
        The multiplicative SoH derate to apply to the year's flat revenue.
    """
    fade = float(spec.get("mdsc_fade_pct_annual", 0.0))
    # Most recent augmentation event at or before this year sets the fade origin.
    base_year_index = 0
    base_soh = 1.0
    for event in spec.get("augmentation_events") or []:
        event_index = int(event["year"]) - 1  # 1-based year -> 0-based index
        if event_index <= year_index:
            base_year_index = event_index
            base_soh = float(event["restore_to_soh"])
        else:
            break  # events are sorted ascending
    if fade <= 0.0:
        soh = base_soh
    else:
        soh = base_soh * (1.0 - fade) ** (year_index - base_year_index)
    floor = float(spec.get("mdsc_floor_soh", _DEFAULT_MDSC_FLOOR_SOH))
    return min(1.0, max(floor, soh))


def bess_augmentation_capex_lkr_for_year(
    specs: Optional[List[Dict[str, Any]]],
    year_index: int,
    fx_rate_lkr_per_usd: float,
) -> float:
    """Total BESS augmentation capex (LKR) incurred in one operating year.

    Sums every spec's augmentation event whose 0-based year matches ``year_index`` and
    converts the ``capex_usd`` at the supplied FX rate. ``0.0`` when there are no specs or
    no event falls in this year (so a scenario without an ``augmentation_schedule`` is
    byte-identical). This is a CASH OUTFLOW the cashflow nets out of CFADS in the incurred
    year; the depreciation tax shield on it is conservatively NOT credited (a documented
    lender-prudent simplification — it understates value slightly rather than risking an
    incorrect mid-life depreciation treatment).

    Args:
        specs: Resolved BESS specs from :func:`resolve_bess_specs`, or ``None``.
        year_index: Zero-based operating-year index.
        fx_rate_lkr_per_usd: The year's LKR/USD rate to translate the USD capex.

    Returns:
        The combined augmentation capex in LKR for the year (``0.0`` if none).
    """
    if not specs:
        return 0.0
    total_usd = 0.0
    for spec in specs:
        for event in spec.get("augmentation_events") or []:
            if int(event["year"]) - 1 == year_index:
                total_usd += float(event["capex_usd"])
    return total_usd * float(fx_rate_lkr_per_usd)


def bess_revenue_lkr_for_year(
    specs: Optional[List[Dict[str, Any]]], year_index: int
) -> float:
    """Total BESS revenue (LKR) for one operating year, summed over every spec.

    Dispatches by each spec's ``model`` (``capacity_charge`` or ``energy_tariff``) and
    pays each only while the operating year is within its ``contract_years`` window (a
    spec with ``contract_years is None`` is paid every year). ``year_index`` is 0-based
    (operating year 1 → 0). The per-spec revenue is flat — no escalation.

    Args:
        specs: Resolved BESS specs from :func:`resolve_bess_specs`, or ``None``.
        year_index: Zero-based operating-year index.

    Returns:
        The combined BESS revenue in LKR (``0.0`` when ``specs`` is empty or every BESS
        contract has expired for this year).
    """
    if not specs:
        return 0.0
    total = 0.0
    for spec in specs:
        contract_years = spec["contract_years"]
        if contract_years is not None and year_index >= contract_years:
            continue
        # Flat per-spec revenue, derated by the year-indexed state-of-health (1.0 when
        # the spec declares no MDSC fade -> byte-identical to the prior flat behaviour).
        total += _spec_annual_revenue_lkr(spec) * mdsc_soh_for_year(spec, year_index)
    return total


__all__ = [
    "BESS_TYPE",
    "SUPPORTED_BESS_REVENUE_MODELS",
    "resolve_bess_specs",
    "bess_revenue_lkr_for_year",
    "mdsc_soh_for_year",
    "bess_augmentation_capex_lkr_for_year",
]

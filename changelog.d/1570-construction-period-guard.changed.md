- **The construction-period count must equal the declared build time (15.24.0, #1570).**
  `finance/debt/terms.py::_resolve_construction_periods` read only the financing section and
  fell back to two periods, so a scenario that declared a one-year build in
  `timeline.construction_years` and no count under `Financing_Terms` ran on two. That count
  drives the debt draw, IDC, the CFADS timeline, the FX start and the project NPV/IRR lag.
  - A financing count (`construction_periods`, or the legacy `construction_years`) that
    disagrees with `timeline.construction_years`, or two `Financing_Terms` keys that disagree,
    is now refused with both values named, in every run mode.
  - A scenario that declares only `timeline.construction_years` now runs on it. A scenario
    that declares neither keeps the default of two.
  - The placeholder draw and capex phasing, used when a scenario supplies neither, are sized
    to the count. Two periods keep `[0.5, 0.5]` and `[40, 60]`. One period draws half the debt
    at financial close and the rest at COD, so IDC is a year's interest on the average balance
    (`0.5 * D * r`): the figure the engine already gave, now a stated convention rather than
    the side effect of a two-entry list meeting a one-period window.
  - KPIs move only for the three scenarios that declared a one-year build in `timeline` alone:
    the superseded Blue Whale hybrid (project IRR 9.28% -> 10.61%, NPV USD -2.07M -> -0.21M),
    `ceb_bess_10mw_capacity_charge` (project NPV USD -3.54M -> -3.23M) and
    `ceb_solar_bess_nightpeak_10mw` (project IRR 10.04% -> 13.10%, equity NPV USD -0.35M ->
    +0.25M, covenant FAIL with four breach years -> REVIEW with one). The canonical lender case,
    both live Blue Whale projects, every DutchBay and NSO 250 scenario are bit-identical.
    Applied under the owner's KPI delegation of 2026-11-07.

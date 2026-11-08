- **Capex and opex price dates (15.26.0, #1569).** A scenario can now state the year its capex
  and opex are priced in, and the engine escalates from there. Before, capex was spent at the
  amount it was priced at, whatever the year, and opex was stated at COD.
  - `capex.price_basis` (`price_year`, `escalation_pct`, `source`) escalates
    `capex.usd_total` from the price year to each construction draw. The draws run from
    financial close (`project.cod_year` less the construction periods), one per year, with the
    phasing shares of `Financing_Terms.construction_schedule` or the sized placeholder:
    `usd_total * sum_i w_i (1 + e) ** (close + i - price)`. The block is resolved once on the
    evaluated configuration and recorded as `capex.price_basis_applied`. A price year after
    financial close, a price year that contradicts `capex.cost_basis_year`, an unknown key or a
    missing `project.cod_year` is refused. The canonical pipeline and the batch scenario
    analytics both apply it, and so does the report gateway (`build_report_context`), because
    the out-of-band report emitters re-load the scenario YAML: their three statements now book
    PP&E and paid-in equity on the capex the engine financed, and their FX methodology is no
    longer withheld for a dated scenario.
  - `opex.price_year` makes every opex escalation run from the price year: operating year 1
    carries `cod_year - price_year` years. The USD share of a currency split keeps the
    engine's own FX path, anchored at the financial-close spot.
  - Both live Blue Whale projects declare 2026 for capex and opex (input B36, placeholder),
    capex escalating at 5%/yr (B29), and start the PUCSL O&M index at 2026 too
    (`tariff.om_indexation.pre_operation_years` wind 2, solar + BESS 3; a test checks it equals
    `cod_year - opex.price_year`). Wind: capex x 1.05 to the 2027 draw, project IRR 13.13% ->
    12.41%, equity IRR 11.55% -> 10.55%, project NPV USD 1.96M -> 1.40M. Solar + BESS: capex x
    1.1025 to the 2028 draw, project NPV USD -4.44M -> -5.58M, equity NPV USD -5.08M -> -6.17M,
    and the equity cash flows no longer have an IRR (their NPV is negative at every rate; it was
    -5.00%). Every other scenario, the superseded hybrid and the canonical lender case included,
    is bit-identical. Applied under the owner's KPI delegation of 2026-11-07.

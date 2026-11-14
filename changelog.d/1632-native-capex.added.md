Added an opt-in flat pre-levy native-currency CAPEX input with declared financial-close FX provenance, strict ambiguity checks, and a single USD resolution for finance and report consumers. Existing configurations remain unchanged; no transaction FX or commercial terms are supplied by this feature. Financial results change only when the new input or its overrides are used; regression and independent review are required before reliance.

The default tornado shocks `capex.input.amount` as its CAPEX bar when CAPEX is authored natively, so the bar no longer disappears. These surfaces do not yet support native CAPEX and refuse it rather than report on it (#1629 boundaries):

- D3B feasibility execution refuses a native scenario at its compatibility check. D3C result projection and the feasibility manifest check accept only run-manifest schema 1.0, while native runs emit 1.1.
- Monte Carlo refuses, before sampling, any `capex.usd_total`, `fx.start_lkr_per_usd` or `fx_calibrated` parameter on a native scenario. Sweep `capex.input.amount` instead.
- Batch scenario analytics refuses a native scenario that also declares `capex.price_basis`.
- Any `fx.start_lkr_per_usd` override is refused, because the conversion rate must equal the financial-close spot. Analysing FX risk on native LKR CAPEX is an open design question under #1629.

# Parameter Schema

This document lists all supported `Params` keys, with units, expected types, allowed ranges, and short descriptions. Values outside these ranges will be rejected by the scenario validator with a friendly message.

| Key | Unit | Type | Range | Description |
|-----|------|------|-------|-------------|
| `total_capex` | USD million | float | [50.0, 500.0] | Total project CAPEX |
| `project_life_years` | years | int | [10, 40] | Model horizon |
| `nameplate_mw` | MW | float | [10.0, 1000.0] | Installed capacity |
| `cf_p50` | fraction | float | [0.2, 0.6] | Net capacity factor (P50) |
| `yearly_degradation` | fraction | float | [0.0, 0.03] | Annual energy degradation |
| `hours_per_year` | hours | float | [7000, 9000] | Operational hours per year |
| `tariff_lkr_kwh` | LKR/kWh | float | [10.0, 200.0] | Feed-in tariff |
| `fx_initial` | LKR/USD | float | [100.0, 1000.0] | Initial FX rate (LKR per USD) |
| `fx_depr` | fraction | float | [0.0, 0.2] | Annual FX depreciation |
| `opex_usd_mwh` | USD/MWh | float | [3.0, 50.0] | Operational expenditure |
| `opex_esc_usd` | fraction | float | [0.0, 0.15] | USD OPEX escalation |
| `opex_esc_lkr` | fraction | float | [0.0, 0.2] | LKR OPEX escalation |
| `opex_split_usd` | fraction | float | [0.0, 1.0] | Share of OPEX in USD |
| `opex_split_lkr` | fraction | float | [0.0, 1.0] | Share of OPEX in LKR |
| `sscl_rate` | fraction | float | [0.0, 0.1] | Surcharge/levy rate |
| `tax_rate` | fraction | float | [0.0, 0.5] | Corporate tax rate |
| `discount_rate` | fraction | float | [0.0, 0.5] | NPV discount rate |

### Composite constraints

- Tariff in USD/kWh must be in [0.05, 0.25]; computed as tariff_lkr_kwh / fx_initial.
- If fx_depr > 0.10 then USD tariff must be ≥ 0.07 (7¢/kWh).
- opex_split_usd + opex_split_lkr must sum to 1.0 (±0.05 tolerance)
## DebtTerms schema

| Key | Unit | Type | Range | Description |
|-----|------|------|-------|-------------|
| `debt_ratio` | fraction | float | [0.4, 0.95] | Debt as % of CAPEX |
| `usd_debt_ratio` | fraction | float | [0.0, 1.0] | Share of debt in USD |
| `usd_dfi_pct` | fraction | float | [0.0, 1.0] | Share of USD debt at DFI rate |
| `usd_dfi_rate` | rate/yr | float | [0.0, 0.2] | USD DFI interest rate |
| `usd_mkt_rate` | rate/yr | float | [0.0, 0.25] | USD market interest rate |
| `lkr_rate` | rate/yr | float | [0.0, 0.4] | LKR nominal interest rate |
| `tenor_years` | years | int | [5, 30] | Debt tenor |
| `grace_years` | years | int | [0, 5] | Interest-only years |
| `principal_pct_1_4` | fraction | float | [0.0, 1.0] | Principal % in first 4 amort years |
| `principal_pct_5_on` | fraction | float | [0.0, 1.0] | Principal % thereafter |

# Within-year rows: what is allocated and what is computed (#1395 part (d))

- **Issue:** [#1395](https://github.com/arunakulat/dutchbay-epc-model/issues/1395) part (d), the A4
  tax and loss carry-forward allocation, and which within-year rows are allocated rather than
  computed. Parts (b) (#1476, the event calendar) and (c) (#1556, the sub-period coverage view)
  have landed.
- **Scope:** documentation of behaviour already on `main`. No code, figure or KPI changes.
- **F-5:** in force. Nothing here supports a covenant, lender or IC representation, and this
  document does not record an F-5 exit. That exit keeps its own reviewer and authority path.

## 1. Where within-year rows come from

The model computes one row per operating year (`finance.cashflow_v14.build_annual_rows`). Three
modules turn those rows into a finer grid. All three are default-off: every committed scenario
uses the annual grid, where none of them runs.

| Module | Part | What it does |
|---|---|---|
| `finance/period_grid_v14.py` | A1 | Resolves `cashflow.resolution` to a grid (annual, or quarterly) and maps a sub-period to its operating year. |
| `finance/subannual_rows_v14.py` | A2 | Splits each annual row across the year's sub-periods by `cashflow.within_year_profile` (an even split when absent). |
| `finance/event_calendar_v14.py` | (b) | On a sub-annual grid, moves tax cash and BESS augmentation capex onto the sub-periods they fall in (`cashflow.event_calendar`), then re-derives the CFADS lines that depend on them. |
| `finance/subperiod_coverage_v14.py` | (c) | Places the debt engine's finished debt service, coverage CFADS and DSCR on the same sub-period index, beside the annual figures. |

No pipeline, API, report or workbook output reads these modules today. The v14 pre-flight
(`analytics/schema_guard.py`) validates their configuration keys, and the tests under
`tests/finance/` call them directly. A within-year figure exists only for a caller that builds
one.

**A fifth module computes some lines per month (#1893).** `finance/monthly_cascade_v14.py`, opted into with
`cashflow.monthly`, is the first dolphin of the monthly CFADS cascade. It is separate from the
grid above and does not use `cashflow.resolution`. Energy follows a scenario-declared
calendar-month shape, and generation revenue, statutory charges and CFADS are computed from
that month's energy. Fixed opex, the senior fee and a BESS capacity charge accrue by days. Tax
and augmentation capex are still the annual figures spread by days. Its `LINE_BASIS` labels
each line `computed`, `time_accrued` or `allocated`, and every line still adds back to the
annual figure. The rule in section 2 therefore describes the four modules above, not this
one. Nothing reads it yet, and F-5 applies to it as to the others.

## 2. The rule: allocated from the annual engine, never re-computed

Every within-year figure is the annual engine's figure divided across the year. No sub-period
runs the tax, degradation, escalation, FX or debt arithmetic on its own inputs. So a within-year
series can show **when** cash falls within a year, but it cannot disagree with the annual
figures: each year's sub-periods add back to the annual figure, exactly on the even profile and
within one unit in the last place otherwise (`RECONCILIATION_ULP_TOLERANCE`). The year's closing
sub-period takes the residual `annual − fsum(earlier sub-periods)`, so all rounding sits in one
declared place.

Each key of an annual row takes exactly one of four treatments. A key in no set is refused
(`_reject_unclassified_keys`), so a new engine row key cannot be silently spread or dropped.

- **Allocated:** split by the within-year profile. A quarter's value is a share of the year's.
- **Placed:** on a sub-annual grid, moved onto the sub-periods named by the event calendar, or
  onto its illustrative default date, which is recorded as an assumption and warned.
- **Re-derived:** recomputed per sub-period from the placed and allocated lines, so that each
  sub-period still adds up. The closing sub-period takes the annual residual.
- **Year-level:** a rate, a flag or a year-end stock. Carried unchanged onto every sub-period,
  never divided.

### Every annual row key

| Key | Treatment | What a sub-period value means |
|---|---|---|
| `gross_kwh` | Allocated | A share of the year's energy, not a seasonal yield. Seasonality appears only through a declared profile. |
| `grid_loss` | Allocated | A share of the year's loss. |
| `net_kwh` | Allocated | A share of the year's net energy. |
| `revenue_lkr` | Allocated | A share of the year's revenue. |
| `generation_revenue_lkr` | Allocated | A share of the year's revenue. |
| `bess_revenue_lkr` | Allocated | A share of the year's revenue. |
| `success_fee_lkr` | Allocated | A share of the year's deduction. |
| `env_surcharge_lkr` | Allocated | A share of the year's deduction. |
| `social_levy_lkr` | Allocated | A share of the year's deduction. |
| `total_statutory_deductions_lkr` | Allocated | A share of the year's deductions. |
| `opex_usd` | Allocated | A share of the year's opex. Escalation is annual, so there is no within-year drift. |
| `opex_lkr` | Allocated | As `opex_usd`, at the year's single FX rate. |
| `senior_fee_lkr` | Allocated | A share of the year's credit-support fee. |
| `ebitda_lkr` | Allocated | A share of the year's EBITDA. |
| `pretax_cfads_lkr` | Allocated | A share of the year's pre-tax CFADS. |
| `total_depreciation_lkr` | Allocated | A share of the year's tax depreciation (section 3). |
| `interest_expense_lkr` | Allocated | A share of the year's deductible interest (section 3). |
| `taxable_income_lkr` | Allocated | A share of the year's taxable income after loss offset (section 3). |
| `tax_lkr` | Placed | Tax cash. On a sub-annual grid it is placed on the calendar's `tax` dates, by default the year's last sub-period (section 3). |
| `posttax_cfads_lkr` | Re-derived | The sub-period's pre-tax CFADS less the tax placed in it. |
| `risk_haircut_amount_lkr` | Allocated | A share of the year's haircut, which the engine computes once on the annual post-tax CFADS. It is not the haircut rate times the sub-period's own post-tax CFADS. |
| `bess_augmentation_capex_lkr` | Placed | The augmentation payment, placed on the calendar's dates, by default the year's first sub-period. |
| `cfads_final_lkr` | Re-derived | Post-tax CFADS less the allocated haircut less the placed augmentation. |
| `cfads_risk_adjusted_lkr` | Re-derived | The same figure as `cfads_final_lkr`, under its alias. |
| `revenue_usd` | Allocated | A share of the year's USD revenue. |
| `cfads_usd` | Re-derived | `cfads_final_lkr` at the year's own LKR-to-USD factor (hedged or not), so no intra-year FX is modelled. |
| `wht_on_interest` | Allocated | A share of the year's withholding tax on interest. |
| `fx_rate` | Year-level | The year's single rate, on every sub-period. |
| `risk_haircut_pct` | Year-level | The year's haircut rate. |
| `effective_tax_rate` | Year-level | The year's tax over the year's taxable income. Not a sub-period rate. |
| `tax_holiday_applied` | Year-level | Whether the year is a holiday year. |
| `carried_forward_losses` | Year-level | The loss ledger's total at the year's END, repeated on each sub-period. Not a sub-period balance (section 3). |
| `year` | Positional | The operating year. A2 adds `period_index`, `period_in_year` (0-based) and `is_year_end`. |

On the annual grid, A2 is an identity and no key is placed or re-derived.

## 3. Tax and the loss carry-forward (the A4 allocation)

### How the annual engine computes tax

`finance/cashflow_v14_tax.calculate_tax` runs once per operating year, threaded year to year by
`build_annual_rows`:

1. Pre-offset taxable income is EBIT, less interest when `interest_deductibility` is on, less the
   year's tax depreciation.
2. The loss ledger is a list of vintages (`_apply_loss_vintages`). A vintage older than
   `loss_carryforward_years` expires before any offset. With a window of 0, no loss is carried
   at all (`allowable_losses_carryforward` is off). A negative year adds a new vintage. A holiday year consumes no losses. Otherwise the oldest
   vintages are offset first.
3. Tax is zero in a holiday year, and taxable income times the corporate rate otherwise.
4. `carried_forward_losses` is the ledger's total after the year.

The year is the unit of assessment throughout. Losses and profits inside one year net off before
any offset or charge, because the year's income is one number.

### What a sub-period then shows

A quarter has no tax computation of its own. In particular:

- **Taxable income, depreciation and interest are allocated.** A quarter's `taxable_income_lkr`
  is a share of the year's figure, already after that year's loss offset. A quarter whose own
  operating result would be a loss shows a positive share in a profitable year, and it creates no
  loss vintage.
- **Tax cash is placed, not computed.** On a sub-annual grid, `tax_lkr` falls on the calendar's
  `tax` sub-periods. Undeclared, it takes the illustrative default of one payment in the year's
  last sub-period, listed in `EventCalendar.assumed` and named in a warning. A scenario can
  declare instalment periods and weights, or `profile` to keep tax on A2's spread. The actual
  instalment dates are tax-law and project facts this repository holds no evidence for (#920).
  So a quarter's `tax_lkr` is generally not its `taxable_income_lkr` times the rate, and is not
  meant to be.
- **The loss ledger is a year-end stock.** `carried_forward_losses` on every sub-period is the
  year-end total, and the vintages behind it are not exposed per sub-period. Read the closing
  sub-period (`is_year_end == 1.0`) when the year-end balance is what you want. No within-year
  build-up or use of losses is modelled.
- **Holiday flag and effective rate are year facts.** `tax_holiday_applied` and
  `effective_tax_rate` repeat the year's values.
- **Post-tax CFADS follows the placement.** Because `posttax_cfads_lkr` is re-derived per
  sub-period as pre-tax less placed tax, a year-end tax payment lowers that sub-period's post-tax
  CFADS by the whole year's tax. In a year with a large tax charge, that sub-period's post-tax
  CFADS can be negative while the year's is positive. That dip is the point of the calendar, and
  its size rests on the assumed date.

For example, on the committed lender case's project-basis rows (`build_annual_rows` with no
interest series), losses build through years 1 to 5 and are used up in years 6 and 7, and the
first tax falls in year 7. On a quarterly grid each quarter of year 5 still shows the year-5
closing loss balance. Under the default calendar each year's tax falls in its fourth quarter, and
that quarter's post-tax CFADS is negative in 13 of the 14 tax-paying years (years 8 to 20). The
coverage rows the debt was sized on (#1397) deduct interest, so their tax years differ. The
mechanism is the same.

## 4. Other figures computed annually and then spread

- **Degradation, escalation and FX** are annual series in the engine
  (`calculate_single_year_cfads` takes one `fx_rate` per year). Every sub-period of a year
  inherits them, so the within-year series has no intra-year drift.
- **The risk haircut** is computed once on the year's post-tax CFADS and then spread. Under a
  calendar, post-tax CFADS is re-derived but the haircut is not, so a sub-period's haircut is not
  the rate times its own post-tax CFADS.
- **BESS augmentation** is a discrete payment. A2 alone smooths it across the year. The
  calendar places it, by default in the year's first sub-period, so the dip shows. Its annual
  amount is the engine's.

## 5. The debt side (part (c))

`build_subperiod_coverage` reads the debt engine's finished result. It does not run a debt
schedule per sub-period.

| Series | Treatment |
|---|---|
| Coverage CFADS (`cfads_usd`) | The levered-tax sizing rows the facility was sized on (#1397), through A2 and the calendar. Rows that do not match the debt result are refused. |
| Senior fee (`senior_fee_usd`) | Allocated evenly over the year. |
| Scheduled debt service | Placed on the calendar's `debt_service` dates, or spread evenly. The even spread is recorded in `SubperiodCoverage.assumptions` and warned, because instalment dates are #920 facts. |
| Bridge service | Lands in operating year 1, where `dscr_by_year` already counts it, on `bridge_service` dates or spread evenly (assumed). |
| Interest and principal | The year's interest is allocated on the same weights as its service, so each instalment carries the year's interest share. Interest is not recomputed on a within-year balance. |
| Balloon interest paid after maturity | Read from the debt result and placed with the service, outside the DSCR, as in `dscr_by_year`. |
| Sub-period DSCR | The one figure computed per sub-period: (coverage CFADS − fee) accumulated since the previous instalment, divided by this instalment. It is a ratio of allocated and placed figures, so it inherits every assumption above. |

Each year's sub-periods re-aggregate to the debt engine within one unit in the last place and so
reproduce `dscr_by_year`. Nothing in the view feeds `min_dscr`, `dscr_by_year`, the sculpt or a
KPI. Its own minimum is named `min_subperiod_dscr`, and every sub-period DSCR carries
`COVENANT_USE`.

## 6. What a within-year figure may be used for

While F-5 stands, no within-year CFADS, tax or DSCR figure may support a covenant, lender or IC
representation. #1110 keeps its circulation HOLD. A within-year series may be used to see the
shape of cash timing within a year, labelled as an allocation of the annual engine with declared
or assumed dates. The assumed dates are listed by `EventCalendar.assumed` and
`SubperiodCoverage.assumptions`.

Lifting that bar needs the evidence the #1395 "Done when" list names: dated tax, bridge and debt
instalments from the term sheet and tax advice (#920), and an independent finance review that
states which figures may be used. This document records what the model does. It is not that
review.

## 7. Where each statement is pinned

| Statement | Test |
|---|---|
| Every row key is classified; an unknown key is refused | `tests/finance/test_subannual_rows.py` |
| The table in section 2 lists exactly the engine's keys and their treatment | `tests/finance/test_within_year_rows_doc_1395.py` |
| Placement, re-derivation, default dates and reconciliation | `tests/finance/test_event_calendar.py` |
| Debt service, coverage CFADS and sub-period DSCR | `tests/finance/test_subperiod_coverage.py` |
| Pre-flight refusal of unsupported resolutions, profiles and calendars | `tests/finance/test_f03_preflight_period_fields.py`, `tests/finance/test_period_grid.py` |

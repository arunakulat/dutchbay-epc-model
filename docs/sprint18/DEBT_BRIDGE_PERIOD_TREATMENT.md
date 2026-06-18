# Sprint 18B Debt Bridge / Ramp Period Treatment

## Purpose

This note documents the lender-presentation treatment introduced in PR #107 for the debt CFADS bridge/ramp period in `finance/debt_v14.py`.

## Decision

The bridge/ramp period is treated as **inside the post-construction lender debt-service timeline**.

It is **not** treated as an annual operating row. It is a separate bridge period inserted after construction and before the first mapped annual operating row.

## Timeline convention

The debt timeline is ordered as follows:

1. Construction periods: zero CFADS periods used for construction drawdown / IDC alignment.
2. Bridge/ramp period: the first post-construction debt period, represented by `cfads_bridge_debt_period`.
3. Annual operating rows: mapped explicitly by `annual_row_debt_period_map`.
4. Any additional tail periods needed to satisfy the derived debt timeline length.

## Tenor treatment

For lender presentation, the bridge/ramp period is counted **inside the debt-service timeline and inside the post-construction tenor window**. The first annual operating row therefore maps to the period immediately after the bridge period, not to the first post-construction debt period.

In practical terms:

- construction periods are outside operating DSCR presentation;
- the bridge/ramp period is the first post-construction debt-service period;
- annual operating rows start after the bridge/ramp period;
- `dscr_by_year` is keyed only to the mapped annual operating rows;
- the bridge period is tracked separately through `cfads_bridge_debt_period`.

## Why this convention is used

This convention avoids blending a partial ramp/bridge CFADS assumption into the first full annual operating year. It preserves a clean audit trail between annual model rows and lender-facing DSCR by year, while still allowing the debt engine to model first-period post-construction CFADS support for sculpting and service coverage.

## Outputs affected

PR #107 exposes the following surfaces for auditability:

- `cfads_bridge_debt_period`: identifies the bridge/ramp debt period;
- `annual_row_debt_period_map`: maps each annual row to its debt period;
- `dscr_by_year`: maps annual operating years to DSCR values without conflating the bridge period with year 1.

## Review note

Future lender packs should label the bridge/ramp period explicitly as a partial post-construction debt-service period. It should not be presented as Year 1 operating DSCR unless the annual model is deliberately rebased to make the bridge period the first full operating year.

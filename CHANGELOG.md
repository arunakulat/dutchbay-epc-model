# Changelog

All notable changes to this project will be documented here.

## [Unreleased]

## [15.6.0] - 2026-09-28

Release records the A1/A2 cashflow period-grid work on main and related 15.5.x hardening.
Pending `changelog.d/` fragments remain in the tree for optional full compile via
`python scripts/compile_changelog.py` (large fold). Highlights of this version bump:

### Added
- **A1 cashflow period grid** (`finance.period_grid_v14`) — single resolver for
  `cashflow.resolution` (`annual` | `quarterly`); describable vs engine-buildable seams.
- **A2 sub-annual operating rows** (`finance.subannual_rows_v14`) — allocates annual CFADS
  rows onto the quarterly grid (not an independent monthly engine). Default scenarios stay annual.
- **F6 debt period taxonomy** on `plan_debt` — `construction_periods`, `bridge_debt_period`,
  `first_operating_period`.
- **WIND-3 gross-AEP integrator parity tests** — production vs oracle Weibull integrators ≤0.05%.

### Changed
- **F2/F3 DSCR contract (carried from 15.5.0):** `plan_debt.dscr_series` is positional;
  `dscr_periods` publishes operating-year labels and per-year folded coverage. Malformed
  labels fail loudly. Headline `min_dscr` retains operating-period minimum and `dscr_by_year` fold.
- **Package / engine identity** — `VERSION` and `pyproject.toml` **15.6.0**; engine identity
  and synthetic-feeder VERSION content hashes refreshed.

### Notes
- Quarterly sub-annual remains **allocation-from-annual**; debt service on that grid (A3) is not claimed.
- Confers no separate Board/lender grade beyond existing code on main.
- Full historical notes through v15.4.0 and earlier remain below.

## v15.4.0 - 2026-08-18

See repository history and prior release notes for the full v15.4.0 entry (feasibility extra,
Python 3.12 baseline, grid lock composition, and related fixes).

- **Blue Whale dispatch: the bool refusal in `_number` has a negative control** (#1578,
  #1590 assurance A-1). A test sets each `_number`-guarded key of the battery, dispatch and
  tariff blocks to `True` and expects the bool message, and shows the same key at `1.0` is
  not refused with it. Test only; no output or KPI moves.

- The FX risk profile no longer drops a single-currency debt mix to float rounding (#1850).
  The debt-concentration Herfindahl index is the sum of the squared currency shares, and with
  all debt in one currency the shares can round so the index comes out a few ulps above 1.
  `FXRiskProfile` refused that value, so the run went on without its FX risk profile and
  logged a warning (seen on a share of the Blue Whale wind Monte Carlo trials). An index
  within 1e-9 of 1 is now 1; a value clearly outside [0, 1] is still refused. Reporting
  only: no KPI or Monte Carlo metric moves.

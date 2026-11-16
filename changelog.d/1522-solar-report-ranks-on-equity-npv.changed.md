The solar assessment report's gearing and DSCR-target optimisations now rank on equity NPV, not equity IRR (#1456, #1522 assurance A-3). On the report's competitive case, the DSCR-target optimum moves from 1.60x (equity IRR) to 1.05x (equity NPV). The 1.05x optimum is worth only about USD 0.08M over 1.30x, and the gearing sweep has no feasible point under either measure. The gearing chart plots equity NPV, and its caption is stated from the run. `optimize_parameter` now logs the #1456 IRR-ranking warning when a caller ranks on `equity_irr`, as the capital-structure optimisers already do.

The report's narrative is refreshed against the current engine. Every figure in the financial, risk, DSCR, discussion and conclusions sections is now a placeholder filled from the run, so the prose cannot drift from the model again. The old prose quoted a superseded baseline: a +1.1% competitive project IRR (now -2.6%), breakevens of LKR 50-60/kWh (now about LKR 73 for the 1.30x covenant and LKR 86 for a 10% project IRR, both solved by the report), 35% gearing and 3% FX drift (the scenario declares 70% and 5.89%).

The narrative now explains what the equity measures show:
- Equity NPV rises with gearing only because the debt costs less than the flat 10% equity discount rate, and the sponsor funds up to USD 8.06M of debt service the asset cannot cover.
- Below the 1.30x lock-up threshold, every distribution is trapped until the debt is repaid, so neither equity measure moves monotonically with the DSCR target.
- The project NPV is discounted at the declared 10% rate and the equity NPV at the waterfall's own 10% rate. The CAPM block's 11.6% WACC is informational and does not use the tranche terms.

The verdict, do not proceed, is unchanged.

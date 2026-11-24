# Additional omitted report modules and activation requirements

The verified legacy emit-all produced a 37-page lender report with three optional sections. Previous P01 analyses identified the following modules as not included in the committed lender report or not run in its present configuration.

| Module | Current condition | What is required |
|---|---|---|
| app/reports/grid_screening_emit.py | legacy grid.study_enabled=false | Valid 220kV Wariyapola POI, verified CEB/NSO fault equivalents, R/X, P/Q, studies; external advisory screening only. |
| app/reports/interaction_grid_emit.py | no interaction_grid block | two approved financial driver ranges plus KPI and verified scenario |
| app/reports/tech_comparison_emit.py | no tech_comparison.scenarios | two or more technically and commercially comparable scenarios |
| app/reports/site_analysis_sections.py | no site-analysis blocks | wind/BESS, PV/BESS, financing or equipment cost blocks with qualified sources |
| app/reports/climate_risk_disclosure.py | not wired to lender template | EIA hazard baseline plus forward climate pathways, quantified resilience and climate finance effects |
| app/reports/tender_gap_dossier_emit.py | procurement dossier not issued | signed OEM offers and technical and commercial deviation register |
| app/reports/solar_assessment.py | wind-only scenario | solar/hybrid resource, design, dispatch and tariff |
| app/reports/module_ledger.py | no dedicated lender annex | verifiable execution and evidence-status manifest |
| app/reports/synthetic_qsts_finance_report.py | synthetic only | always separate from real utility evidence |
| analytics/conditions_precedent.py | zero declared items | 13 formally tracked close/drawdown conditions and verified instruments |
| analytics/feasibility_sections.py | zero authored sections | 20-section authored report with content/evidence checks |
| wind_resource/long_term_trend.py | no accepted crossvalidated trend | synchronized measured mast, NASA/ERA5 series, uncertainty and reviewer |

Other substantive analytical modules not separately presented: ARCO/crossval/MCP, GIS suitability/roughness/RIX, layout/exclusions/shadow flicker, grid SCR/reactive/harmonics/dynamic ride-through/QSTS, wind+BESS storage dispatch, BESS LCOS, OEM equipment parity, what-if/DSCR/tax sensitivity, post-COD operational AEP/EYA bridge. See the 25-module CSV.

Agreed activation priority: financial interaction and FX/tenor once yield provenance is accepted; technology comparison/equipment parity; 220kV grid study after utility inputs; BESS/solar only when source-supported; operations after COD.

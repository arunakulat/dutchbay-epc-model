# Renewable-Energy Knowledge Base

Consolidated, technical reference documentation for the renewable-energy projects this financial model serves — Sri Lankan onshore wind and battery storage. It complements the model's code, scenarios and architecture docs with the cost benchmarks, project facts, regulatory framework and project-finance methodology behind the numbers.

## Documents

| Document | Contents |
|---|---|
| [`01_wind_epc_costs_and_scaling.md`](01_wind_epc_costs_and_scaling.md) | Onshore wind EPC cost benchmarks (a tendered line-item base plus IRENA / Lazard / NREL) and the bottom-up methodology used to scale a 50 MW base to the 60 MW and 150 MW capex cases in the scenarios. |
| [`02_dutch_bay_project_dossier.md`](02_dutch_bay_project_dossier.md) | The Dutch Bay 150 MW wind + BESS project — engineering configuration, EIA energy yield and economics, and the CEB Standardized PPA commercial terms. |
| [`03_kalpitiya_60mw_and_esia.md`](03_kalpitiya_60mw_and_esia.md) | The Kalpitiya 60 MW (Kandakkuliya) wind project, its flat-LKR PPA, and the lender-grade ESIA framework and E&S risk register. |
| [`04_bess_technology_pricing_revenue.md`](04_bess_technology_pricing_revenue.md) | Battery storage technology, 2026 pricing benchmarks, and the distinct utility BESS revenue models (capacity-charge vs single-site vs solar-plus-storage). |
| [`05_project_finance_methodology.md`](05_project_finance_methodology.md) | DFI / lender project-finance methodology — debt sizing & covenants, P50/P90 bankability, FX & currency-mismatch, the Sri Lankan tax regime, grid-curtailment and multi-technology modelling. |
| [`../renewable_energy_corpus_index.md`](../renewable_energy_corpus_index.md) | Index of the underlying source-document corpus (EIAs, tenders, PPAs, technical studies, GIS data). |

## Relationship to the financial model

These documents are **reference knowledge** (the *why* and the *inputs*); the repository's scenarios, engine and architecture docs are the **configuration and computation**. Where a figure here also drives the model (e.g. capex $/kW, AEP, tariff), the scenario YAML is the single source of truth and this knowledge base explains its provenance.

## Scope & sanitization

This is a **public** knowledge base: it carries technical, analytical and benchmark knowledge and cites publicly disclosed sources (the project EIA, the CEB Standardized PPA template, IRENA / Lazard / NREL / IEA, Sri Lankan law). Private commercial counterparty terms, vendor pricing, land/ownership detail and internal strategy are generalized; a fuller private record is held by the project owner.

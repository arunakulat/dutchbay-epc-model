# Finance, Python, and renewable-production comparative review

**Research date:** 5 October 2026
**Record type:** persistent analyst knowledge; no model-input or authority effect
**Scope:** renewable-project finance, scientific Python, and production-modelling programs

## Purpose and authority boundary

This record preserves a current professional briefing requested from the perspective of a CFA-level
renewable-energy analyst with strong Python engineering capability. It compares the DutchBay model
with established specialist programs and identifies practices worth carrying into future bounded
work.

This is reference knowledge, not a bankability opinion, energy-yield assessment, grid-connection
study, tax or legal opinion, release disposition, or instruction to change a canonical scenario.
Issue #1110 and the broader Board/lender reliance `HOLD` remained open when this research was
performed. Neither a cited program nor a passing software test transfers professional authority to
DutchBay.

Package versions and repository activity below are point-in-time observations from public package
and project metadata on the research date. They are not upgrade instructions. Market forecasts are
source projections, not DutchBay assumptions.

## Executive findings

1. Renewable investment analysis has moved beyond technology-level LCOE. Capture price,
   curtailment, congestion, FX, construction delay, refinancing, degradation, resource uncertainty,
   and covenant resilience can reverse an LCOE ranking.
2. P50/P75/P90 cases should be derived from a traceable physical and operational uncertainty chain.
   A generic revenue haircut is not a substitute for a correlated uncertainty model.
3. DutchBay is an integration and project-finance layer. PyWake, FLORIS, OpenOA, pvlib, PySAM,
   reV, WISDEM, PyPSA, and pandapower solve narrower technical problems and are better treated as
   upstream engines or independent comparators than as interchangeable competitors.
4. DutchBay's largest production-analysis opportunity is operational calibration: reconcile the
   pre-construction energy-yield assessment with SCADA, revenue-meter, meteorological, and
   reanalysis evidence using an OpenOA-style schema and loss bridge.
5. The governed Python 3.12 baseline remains defensible. Migrating to pandas 3 or free-threaded
   Python should require a dedicated compatibility and KPI-oracle exercise, not routine dependency
   churn.

## Finance learning

### Revenue quality now matters as much as energy quantity

The IEA's *Renewables 2024* main case projects about 5,500 GW of new renewable capacity becoming
operational from 2024 through 2030; solar PV and wind represent 95% of forecast capacity growth.
Higher variable-renewable penetration increases the importance of capture-price erosion, negative
prices, congestion, curtailment, balancing costs, and interconnection delay. LCOE remains useful for
technology screening but does not measure the timing, contractual quality, or debt service value of
cash flows.

A project comparison should therefore carry at least:

- delivered-energy LCOE and its boundary;
- project and equity NPV/IRR;
- minimum and average DSCR, LLCR, and PLCR;
- debt quantum, tenor, sculpting constraints, and reserve requirements;
- break-even tariff and capture price;
- curtailment and grid-availability exposure; and
- downside covenant-breach probability.

### Separate resource and operational uncertainty

A lender case should distinguish resource uncertainty—measurement, long-term correction,
interannual variability, and climate non-stationarity—from operational and commercial uncertainty,
including wakes, availability, electrical losses, curtailment, grid outages, degradation, and
tariff collection. These drivers are not necessarily independent or Gaussian.

The auditable chain is:

```text
gross resource
  -> physical conversion
  -> wake and plant losses
  -> availability, grid and curtailment
  -> net delivered energy
  -> tariff or capture price
  -> revenue and CFADS
  -> debt service and covenant outcomes
```

Every percentile must state its distribution and period. Annual P90 energy and ten-year average
P90 energy are different risk measures.

### Put climate effects in the affected cash-flow drivers

IFRS S2 requires disclosure of climate-related risks and opportunities that could reasonably affect
cash flows, access to finance, or cost of capital. For a renewable project, that can include changing
wind or irradiance regimes, extreme wind, flooding, heat, salt corrosion, insurance cost, repair
lead times, and supply-chain concentration.

Physical effects should first alter production, cost, outage, and useful-life scenarios. Financing
effects should then appear in liquidity, reserve, debt-margin, and discount-rate cases. A generic
climate premium added only to WACC can double-count or conceal the underlying exposure.

### Environmental and social risk is credit risk

The Equator Principles describe a common financial-industry framework for identifying, assessing,
and managing environmental and social risk in projects. Conditions precedent, mitigation cost,
permit risk, community obligations, biodiversity controls, and construction delay should be linked
to the financial case where evidence supports that link. They should not remain an unpriced prose
annex.

## Renewable-production program comparison

| Program | Primary scope | Best-qualified use | Relationship to DutchBay |
|---|---|---|---|
| [PyWake](https://gitlab.windenergy.dtu.dk/TOPFARM/PyWake) | Engineering wake models and wind-farm AEP | Per-turbine wakes, model comparison, AEP, and layout studies | Upstream physical engine already used by DutchBay |
| [FLORIS](https://github.com/NatLabRockies/floris) | Controls-oriented steady-state wake simulation | Wake steering, yaw control, and controls research | Complementary; deeper in wind-farm controls |
| [OpenOA](https://openoa.readthedocs.io/en/latest/) | Operational wind-plant assessment | Long-term operational AEP, loss estimation, uncertainty, and EYA-to-actual gap analysis | Strong candidate for DutchBay's missing operational-calibration layer |
| [pvlib](https://github.com/pvlib/pvlib-python) | PV performance simulation | Solar position, irradiance transposition, temperature, module, and inverter models | Upstream solar engine already used by DutchBay |
| [PVPMC](https://pvpmc.sandia.gov/) | PV modelling guidance, datasets, and validation | Selecting and independently validating PV model components | Technical reference and oracle for DutchBay solar work |
| [PySAM](https://github.com/NatLabRockies/pysam) | Python access to NREL's System Advisor Model | Detailed technology-performance and techno-economic studies | Broader technology reference; less tailored to DutchBay debt and covenants |
| [reV](https://github.com/NatLabRockies/reV) | Geospatial techno-economic assessment | Resource potential, exclusions, transmission cost, and supply curves | Stronger for regional screening; DutchBay is narrower and project-specific |
| [WISDEM](https://github.com/WISDEM/WISDEM) | Integrated wind-system engineering and cost | Turbine, BOS, energy, and cost-of-energy optimization | Stronger for physical design and COE optimization |
| [PyPSA](https://pypsa.org/) | Power- and energy-system optimization | Dispatch, network-constrained capacity expansion, and market scenarios | Better suited to system/capture-price studies |
| [pandapower](https://github.com/e2nIEE/pandapower) | Steady-state network calculation | Load flow, short circuit, and network screening | An upstream screening engine, not a utility-accepted study by itself |
| DutchBay | Project integration and finance | Resource-to-cash-flow, debt, tax, FX, uncertainty, and lender reporting | Differentiated integration layer; project-specific and subject to the active `HOLD` |

The comparison is functional, not a league table. Repository stars, recent commits, package versions,
and passing tests indicate activity or engineering hygiene; they do not establish accuracy for a
specific site.

### Priority production improvement: operational reconciliation

An OpenOA-style operating-data layer would provide more decision value than adding another wake
formula. The bounded target should include:

- standardized SCADA, revenue-meter, meteorological, and reanalysis schemas;
- explicit availability, electrical, curtailment, wake, and performance-loss categories;
- long-term operational AEP and uncertainty;
- a pre-construction EYA-to-operational gap bridge; and
- governed posterior updates to finance assumptions without overwriting original evidence.

### Wake-model qualification protocol

PyWake and FLORIS comparisons are meaningful only when turbine curves, layouts, coordinate systems,
wind roses, air density, turbulence intensity, wake superposition, blockage, and loss boundaries are
matched. Divergent results usually identify model or boundary sensitivity; they do not, without
further evidence, prove that one implementation is defective. Site-specific calibration and
independent engineering review remain necessary for reliance.

## Python engineering learning

### Point-in-time ecosystem observations

Public package metadata observed on 5 October 2026 reported PyWake 2.6.20, FLORIS 4.6.6, OpenOA
3.2, pvlib 0.16.1, NREL-PySAM 7.1.1.post1, NREL-reV 0.14.5, PyPSA 1.3.0, pandapower 3.5.5, and
WISDEM 4.2.8. These values will become stale and must be re-queried before dependency decisions.

DutchBay's strict configuration validation, typed contracts, single evaluation gateway, isolated
IRR/NPV implementation, explicit seeds, governed lock, optional-dependency guards, unit-bearing
field names, and independent-oracle rule are appropriate model-risk controls.

### Upgrade conservatism is justified

Pandas 3 makes Copy-on-Write behaviour standard, changes string dtype behaviour, and removes many
deprecated APIs. DutchBay's current `pandas<3` boundary should be lifted only through a dedicated
migration with dataframe-semantics probes and financial KPI oracles.

CPython's free-threaded build can execute without the global interpreter lock, but extension-module
compatibility and single-thread overhead remain workload-dependent. NumPy/SciPy vectorization,
process-level parallelism, and profiling should remain the default path until a representative
DutchBay benchmark proves that free threading improves throughput without changing numerical or
reproducibility properties.

### Highest-value engineering investments

1. Versioned immutable input and output contracts.
2. Dimensional and unit validation at boundaries.
3. Source and derived-artifact provenance hashes.
4. Property-based finance tests and independent closed-form or cross-engine oracles.
5. Matched-boundary golden cases against specialist programs.
6. Explicit numerical tolerances, convergence receipts, and solver diagnostics.
7. Dependency graphs mapping each external datum and assumption to affected KPIs.

## Disposition of the KIMI Q4 2026 comparison

A third-party KIMI report was supplied after the initial research checkpoint. It is treated as a
claim set, not as a source. Its useful themes and material corrections are preserved here so later
work does not silently inherit either its conclusions or its errors.

### Retained as directionally useful

- Cost of capital, execution quality, offtake, curtailment, and capture price can dominate a
  technology-level LCOE comparison.
- Hybrid generation and storage require explicit revenue-stack, charging-cost, degradation,
  augmentation, and dispatch assumptions; an LCOS headline alone does not establish bankability.
- OpenOA-style operational reconciliation remains the clearest post-COD capability opportunity.
- IFRS S1/S2 can be relevant to investor reporting when the applicable reporting perimeter and
  jurisdiction are established.
- Current IEA evidence strengthens the market-direction conclusion: *Renewables 2025* projects
  global renewable capacity to double from 2025 to 2030, with solar PV providing almost 80% of the
  increase, while *Electricity 2026* reports that renewable generation virtually matched coal in
  2025 and expects renewables and nuclear together to supply around half of global electricity by
  2030.

### Corrected or rejected

| KIMI claim | Disposition |
|---|---|
| DutchBay has no BESS modelling | **False.** The repository contains `finance/bess_revenue.py`, `finance/bess_lcos.py`, `finance/bess_project_economics.py`, grid BESS capabilities, dedicated scenarios, and focused tests. Dispatch/arbitrage breadth can still be assessed, but the capability is not absent. |
| Add PySAM to create a BESS module | **Not a gap statement.** PySAM may be a useful independent comparator or dispatch/technology engine, but adopting it requires a bounded interface and oracle assessment against the existing BESS implementation. |
| Add Cambium/ERA5 price data for merchant forecasting | **Category error and jurisdiction mismatch.** ERA5 is meteorological reanalysis, not a power-price dataset; Cambium is a United States power-sector dataset and is not a Sri Lankan merchant-price source. |
| PyWake is canonical for a bankable AEP and open-source tools are bankable alternatives | **Overstated.** These are calculation engines. Bankability comes from site evidence, calibrated methods, loss and uncertainty boundaries, independent review, and professional reliance—not the package name. |
| DutchBay is lender-grade | **Authority overreach.** The repository's architecture and controls can be compared, but issue #1110 and the Board/lender reliance `HOLD` prohibit that conclusion. |
| BESS LCOS is below USD 80/MWh | **Not a general benchmark.** The report itself gives incompatible ranges. LCOS depends on duration, cycles, charging cost, augmentation, financing, residual value, and included revenue/cost boundaries. |
| Contracted renewable DSCR is universally 1.20–1.25x against P90 | **Too broad.** DSCR convention varies by technology, resource case, contract, tenor, jurisdiction, and lender. The existing knowledge base records contracted-solar and contracted-wind ranges separately and distinguishes P50 operating cases from downside debt sizing. |
| IFRS S2 mandates fixed 1.5°C and 4°C scenarios | **Too prescriptive.** IFRS S2 requires climate-resilience disclosure informed by climate-related scenario analysis using an approach commensurate with the entity's circumstances; any fixed scenario pair needs a separate applicable basis. |
| PyWake 2.6.8, FLORIS 4.0, and TopFarm 2.6.1 are the current comparison versions | **Stale on the research date.** Public PyPI metadata returned PyWake 2.6.20, FLORIS 4.6.6, and TopFarm 2.6.2. Versions remain mutable observations, not upgrade instructions. |
| `PYDANTIC_V2_RUNTIME_RISKS.md` is a DutchBay control | **Exists, but qualify its evidential weight.** The root-level document is present and records a 2025 migration-era review of Pydantic v2 runtime risks. It is useful historical control evidence, but its own date, branch, and stated analysis scope mean that it is not by itself proof that the current head is free of Pydantic v2 runtime risk. Current tests and exact-head review remain necessary. |
| A naive 1,000-trial Monte Carlo is categorically insufficient for lenders | **Unsupported as a universal threshold.** Adequacy depends on the estimator, tail metric, convergence evidence, dependence structure, and decision. DutchBay correctly separates bounded regression tests from explicit stochastic qualification. |
| The cited 800 GW of 2025 capacity additions and detailed country splits are established by the cited IEA material | **Not reproduced from the accessible primary IEA pages reviewed here.** Do not use those figures until the exact table, unit, vintage, and primary source are retrieved. |
| Lazard v19 values and year-on-year percentages in the supplied table | **Not independently admitted.** Lazard returned HTTP 403 in this cloud session and KIMI's opaque search markers are not reproducible citations. Retain the existing verified v18/v10 knowledge-base figures until the primary v19 objects are ingressed. |

The report's United States tax-credit discussion may be useful for a United States project but is
not a DutchBay scenario input. Any OBBBA credit, prohibited-foreign-entity, transferability, PPA,
swap-rate, or regional WACC claim requires a dated primary legal or market source and an explicit
jurisdiction before it enters a model or benchmark table.

## Qualified conclusion

DutchBay is broader in project finance than the specialist production and grid libraries, and more
project-specific than regional platforms such as reV, WISDEM, and PyPSA. Its defensible role is to
orchestrate, reconcile, and financially interpret recognized specialist engines. It should not claim
to replace an independent energy-yield assessment, utility grid study, lender technical adviser, or
other professional authority.

## Sources and reproducibility notes

- International Energy Agency, [*Renewables 2024*](https://www.iea.org/reports/renewables-2024),
  especially the executive-summary capacity forecast.
- International Energy Agency, [*Renewables 2025*](https://www.iea.org/reports/renewables-2025)
  and [*Electricity 2026*](https://www.iea.org/reports/electricity-2026), used for the current
  market-direction statements in the KIMI disposition.
- International Renewable Energy Agency,
  [*Renewable Power Generation Costs in 2024*](https://www.irena.org/Publications/2025/Jul/Renewable-power-generation-costs-in-2024).
- IFRS Foundation,
  [IFRS S2 Climate-related Disclosures](https://www.ifrs.org/issued-standards/ifrs-sustainability-standards-navigator/ifrs-s2-climate-related-disclosures/).
- Equator Principles Association,
  [About the Equator Principles](https://equator-principles.com/about-the-equator-principles/).
- Sandia National Laboratories, [PV Performance Modeling Collaborative](https://pvpmc.sandia.gov/).
- Primary documentation and repositories linked in the comparison table.
- Package versions were queried from the public PyPI JSON API on the research date. Repository
  activity and descriptions were queried from the public GitHub API. Those mutable observations are
  included for recency context only.
- The IRENA and Lazard sites returned HTTP 403 to this cloud session. No inaccessible body text was
  represented as freshly read. IRENA is cited as a current benchmark source, while quantitative
  statements in this record rely on accessible IEA and primary standards pages or are clearly
  described as package metadata observations.
# P3 Monte Carlo / FX / Equity-Reporting Independent Refuter Checkpoint

Completed the independent read-only P3 refuter pass against the audited repository commit. No repository or remediation artefact other than this requested checkpoint was edited.

Repository state remained clean:

- Worktree: `/Users/aruna/Downloads/dutchbay-wt-audit-corrigendum`
- HEAD: `7e99f34d75b9c3d44a5c5b260cedbe403d2f79e8`
- Branch/status: `codex/audit-corrigendum-2026-08...origin/main`, no tracked or untracked changes
- The worktree had no `.venv`; reproductions used `/Users/aruna/Downloads/dutchbay-epc-model/.venv/bin/python` and `pytest`, with the audited worktree as the working directory, so imports resolved from `7e99f34`.

## Disposition summary

| Claim | Exact disposition | Bottom line |
|---|---|---|
| P3 quantitative assertion: canonical 100,000-trial finance MC | **REFUTED** | `n_scenarios: 100000` is a wind-AEP key, not the finance-MC trial count. No executed 100,000-trial finance-MC artefact was found. |
| MCFX-01 | **PARTIALLY CONFIRMED** | Canon does use uniform `[300,367]` and no committed scenario enables `fx_calibrated`; however, the calibrated implementation is a one-year spot mixture plus constant drift, not a 20-year regime/path model, and “dominant/material” magnitude was not established by the audit. |
| MCFX-02 | **PARTIALLY CONFIRMED** | Six live finance-MC drivers and the stated omissions are confirmed. A universal DFI requirement that every listed risk be a stochastic MC driver is not supported; risk selection must be transaction-specific. |
| MCFX-03 | **CONFIRMED** | The percentile diagnostic uses the defective bare DSCR comparison. The precise overstatement is sample-specific, not universally 12.5 percentage points. |
| MCFX-04 | **CONFIRMED, scope corrected** | Two VaR/CVaR implementations use different definitions and give different deterministic outputs. CASPER’s lean MC/risk blocks omit CVaR, but separate async-analysis and capital-risk report/client surfaces do expose it. |
| MCFX-05 | **PARTIALLY CONFIRMED** | The 10% Weibull knob is unattributed, but it is not the live finance-MC wind driver. The canonical wind-AEP adapter currently fails on the shared list-form `parameters` schema before using it. |
| MCFX-06 | **PARTIALLY CONFIRMED** | Successful finance-MC runs get convergence metadata keys, populated for at least 30 finite trials. They quantify error; they do not certify sufficiency, and “above typical practice” lacks comparison evidence. |
| EQ-01 | **PARTIALLY CONFIRMED; blanket assertions refuted** | Canon’s actual report is correctly value-destructive and co-locates both IRRs. “Every surface,” “no external project-only path,” “architecturally incapable,” and “no misleading presentation anywhere” are false. |
| EQ-02 | **CONFIRMED, inventory expanded** | Not one but at least three production info-log sites omit equity IRR while printing project IRR. No lender-deliverable numerical impact was shown. |
| EQ-03 | **PARTIALLY CONFIRMED** | The dated ten-step rebaseline history is comment-only, but the generated report already contains a live project-to-equity IRR bridge. “Roughly half” is an unsupported order-dependent attribution. |

## Cross-cutting quantitative correction: the alleged 100,000-trial finance MC

**Supersedes**

- `/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_2026-08/03_bankability_methodology.md:72`
- The “100,000-trial run” wording at lines 76–77
- `/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_2026-08/raw/P3_c_mc_fx_rigor.json:8`

**Disposition: REFUTED.**

Evidence:

- The scenario declares `monte_carlo.n_scenarios: 100000` at `scenarios/dutchbay_lendercase_2025Q4.yaml:552-555`.
- The only production reader of that field is the wind-AEP adapter at `analytics/wind/pipeline_aep_v14.py:172-219`.
- The finance engine always requires an explicit caller-supplied `n_trials` at `analytics/mc/engine.py:786-805`.
- Finance-MC caller defaults differ:

  - Standalone CLI: 10,000 at `analytics/cli/cli_monte_carlo_hydra.py:167-209`.
  - CASPER evaluator: external MC config, default 1,000 at `analytics/evaluation_v14.py:461-521`.
  - Opt-in lender capital-risk report: default 2,000 at `app/reports/capital_risk_emit.py:62-84`.
  - Async analysis request: default 2,000, maximum 20,000 at `app/jobs/models.py:247-253`.
  - Full-pipeline documentation explicitly says capital-risk `n_trials` is **not** scenario `n_scenarios` at `run_full_pipeline_v14.py:763-778`.

- No finance-MC result, capital-risk report, or 100,000-trial manifest was found in the immutable audit pack or the audited repository output directories.
- Directly exercising the wind-AEP adapter with the canonical scenario did not run 100,000 wind scenarios either; it failed before simulation with:

```text
AttributeError 'list' object has no attribute 'get'
```

This occurs because `analytics/wind/pipeline_aep_v14.py:201-205` expects `monte_carlo.parameters` to be a mapping, while the canonical finance engine correctly requires the list at `analytics/mc/engine.py:603-618`.

- The convergence code publishes CI measurements but has no scenario-authored target precision, acceptance threshold, or pass/fail gate. Its own documentation says the mean CI does not certify lender tail bands: `analytics/mc/convergence.py:4-38,59-133`.

**Corrected claim**

> The scenario authors a 100,000-scenario count for a legacy wind-AEP simulation path. The finance Monte Carlo has no scenario-canonical trial count: callers currently request between 1,000 and 20,000 by default or policy. No executed 100,000-trial finance-MC pack was evidenced. Statistical sufficiency must be assessed against declared mean, percentile, breach-probability, and ES/CVaR precision tolerances on an actual run manifest; trial count alone is not a certificate.

**Canon impact**

None on the deterministic KPI vector. The audit’s characterization of existing stochastic evidence and convergence strength must change. Actual MC bands at the intended lender run count remain unestablished.

**Owner/dependency**

Risk-methodology owner plus finance-MC orchestration owner. Dependency: choose one governed finance-MC run configuration, define acceptance tolerances, emit a manifest with actual effective `n_trials`, and retain the resulting risk pack.

---

## MCFX-01 — calibrated FX not enabled

**Supersedes**

- `03_bankability_methodology.md:38,72,75`
- `raw/P3_c_mc_fx_rigor.json:2`

**Disposition: PARTIALLY CONFIRMED.**

Confirmed evidence:

- Canonical finance MC uses `fx.start_lkr_per_usd`, uniform `[300,367]`: `scenarios/dutchbay_lendercase_2025Q4.yaml:593-596`.
- Repository-wide scenario parsing found **zero** `distribution: fx_calibrated` declarations.
- Engine calibration is opt-in only: `analytics/mc/engine.py:378-456`.
- For `fx_calibrated`, the engine replaces authored bounds with unit `[0,1]`, applies the inverse CDF, and injects calibrated `fx.annual_depr`: `analytics/mc/engine.py:482-507,632-645`.
- The pinned historical series is integrity-checked BIS data: `analytics/fx/fx_history.py:12-32,208-255`.
- The calibration explicitly models a one-year two-regime spot mixture: `analytics/fx/fx_calibration.py:1-34,164-253,279-327`.
- The module expressly says full Markov regime-switching paths are a future enhancement at `analytics/fx/fx_calibration.py:32-34`.

Pinned-vintage calibration reproduced:

```text
provider           BIS
date range          2005-01-03 .. 2026-06-23
observations        5,379
annual_depr         0.058946094019936
crisis_prob         0.047619047619047616
sigma_normal_1y     0.08362364305338552
sigma_crisis_1y     0.4600628016265296
crisis_log_shift    0.3610400033180719
```

Spot quantile comparison, LKR/USD:

| Quantile | Calibrated | Uniform `[300,367]` |
|---:|---:|---:|
| 0.1% | 187.918 | 300.067 |
| 1% | 269.443 | 300.670 |
| 5% | 289.828 | 303.350 |
| 10% | 299.481 | 306.700 |
| 50% | 334.778 | 333.500 |
| 90% | 377.602 | 360.300 |
| 95% | 396.644 | 363.650 |
| 99% | 694.059 | 366.330 |
| 99.9% | 1,220.601 | 366.933 |

A common-seed, six-driver, fail-loud 256-trial comparison produced no failures or toy fallbacks:

| Metric | Uniform | Calibrated |
|---|---:|---:|
| Project IRR P5 | −2.9102% | −3.0555% |
| Project IRR P10 | −2.0529% | −2.4362% |
| Project IRR P50 | 0.3699% | 0.3599% |
| Project IRR min / max | −4.8267% / 6.1193% | −5.2383% / 14.4654% |
| Equity IRR P5 | −12.5690% | −13.1675% |
| Equity IRR P10 | −11.5269% | −12.1680% |
| Equity IRR P50 | −7.5953% | −7.6636% |
| Equity IRR min / max | −14.5587% / 2.0895% | −29.1881% / 17.9280% |
| Project NPV P5 | −$121.51m | −$124.04m |
| Project NPV P10 | −$116.98m | −$118.64m |
| Project NPV min / max | −$128.97m / −$27.67m | −$167.18m / +$81.67m |

This confirms a much wider, skewed FX spot tail, but it does not validate a production lender distribution.

What failed adversarial testing:

- “Dominant 20-year risk” was not established by a controlled driver attribution.
- Enabling the current feature does **not** introduce stochastic annual drift paths. It replaces the one-year spot draw and sets one calibrated constant annual depreciation rate.
- Calling the remedy “a one-line YAML change” is technically true for engine activation, but inadequate as a model-risk remedy. The 99.9% quantile of approximately 1,221 LKR/USD itself needs validation, truncation/horizon policy, and lender approval.
- The 256-trial result is illustrative, not a lender-grade tail estimate and not proof of the effect at a nonexistent 100,000-trial run.

**Corrected claim**

> No committed scenario activates the available BIS-history-calibrated one-year FX spot mixture; canonical finance MC uses a symmetric uniform spot band. A seed-matched 256-trial refuter run confirms that activation broadens and skews FX-sensitive output tails, especially extrema. The current calibrated feature is not a full 20-year regime/path model and does not add annual drift variance. Validate its horizon, tail, source vintage, and transaction use before enabling it in a governed lender run.

**Canon impact**

No deterministic KPI movement. Only stochastic risk bands, extrema, VaR/CVaR, and risk disclosures change unless base-case FX assumptions are separately re-authorized.

**Owner/dependency**

FX model-risk owner and transaction financial analyst. Dependencies: calibration validation, approved tail/horizon policy, a governed MC config, independent run review, and lender-facing disclosure.

**Limitations / unfinished items**

- No production-scale lender MC was run; the 256-trial comparison is an adversarial illustration.
- No transaction owner has approved the calibrated tail, truncation, horizon, or the decision to activate it.
- A full 20-year regime/path model remains an unimplemented future enhancement.

---

## MCFX-02 — six-driver risk universe

**Supersedes**

- `03_bankability_methodology.md:72,76`
- `99_SYNTHESIS_final_audit.md:76`
- `raw/P3_c_mc_fx_rigor.json:3`

**Disposition: PARTIALLY CONFIRMED.**

Repository-wide parsing of all 39 tracked YAML/YML/JSON scenario files found:

```text
list-form finance-MC configs:     9
legacy mapping-form configs:      7
parse failures:                   0
unique live list parameter names:
  capex.usd_total
  fx.start_lkr_per_usd
  opex.usd_per_year
  project.capacity_factor
  project.curtailment_pct
  tariff.lkr_per_kwh
```

No list-form MC config contained interest/margin/refinancing, construction delay, tax-law change, or offtaker/default-event drivers.

The canonical six entries and their correlation matrix are at `scenarios/dutchbay_lendercase_2025Q4.yaml:569-629`.

Nuances the audit omitted:

- Interest rates and tax are numerical live config paths, but absent from MC. The generic `Financing_Terms.interest_rate_nominal` is a known no-op and is intentionally excluded from default sensitivity at `analytics/core/sensitivity_runner.py:31-54`; the actual tranche-rate paths under `Financing_Terms.rates.*` are the likely live shock paths.
- A corporate-tax deterministic sensitivity already exists at `analytics/core/sensitivity_runner.py:47-54`.
- Offtaker default is not merely “held deterministic”; no credit-event/default/recovery mechanism exists in the finance-MC driver contract.
- Refinancing settings exist at `scenarios/dutchbay_lendercase_2025Q4.yaml:534-539`, but canonical `balloon_treatment: cash_sweep` at lines 461–468 does not activate a stochastic refinancing facility or spread.
- A construction duration is authored under `timeline`, but debt construction periods resolve from `Financing_Terms` and default to two at `finance/debt_v14.py:382-410,674-689`.

Primary-source calibration of the normative wording:

- IFC’s developer guide lists capex, opex, energy production, and interest rate as typical sensitivity variables and asks for stress/scenario results and financing-cost sensitivities: `IFC_Utility_Scale_Solar_Project_Developer_Guide_2015.txt:10127-10159,10223-10241`.
- The WBG PPP Handbook identifies construction, FX, interest, and changes in law among a comprehensive risk universe, but permits qualitative **and/or** quantitative assessment and says quantitative analysis may be used where significant risks need it: `WBG_PPP_Handbook_2024.txt:2365-2389,2411-2458,2468-2474`.
- The 2025 Sri Lanka energy PAD provides transaction precedent for MC including capex overruns and construction delays and separately identifies CEB payment risk: `World_Bank_IDA_Sri_Lanka_Renewable_Energy_2025_PAD.txt:1530-1535,1821-1829`.

These sources support broader stress coverage; they do not impose a universal rule that every risk category must be one dimension in one joint Monte Carlo.

**Corrected claim**

> The canonical finance MC jointly samples six operating/economic drivers and omits rate/refinancing, construction-delay, tax-change, and offtaker-credit events from that joint distribution. Official guidance supports identifying all material risks and quantitatively stressing key financing and project variables, but whether a risk belongs in MC, deterministic scenario analysis, a structural event tree, or qualitative/contractual treatment is transaction-specific. The risk register should disclose inclusions, exclusions, mitigations, and residual risks; trial count must not imply completeness.

**Canon impact**

No deterministic impact. Potentially material stochastic and credit-decision impact after distributions, correlations, event logic, and mitigations are authorized.

**Owner/dependency**

Transaction risk owner plus finance/risk-engine owner. Dependencies: approved risk taxonomy, source-backed distributions and correlations, live tranche-rate paths, construction-delay timing model, offtaker default/recovery mechanism, and model-validation tests.

**Limitations / unfinished items**

- The final transaction risk universe and each treatment remain owner decisions, not refuter determinations.
- No distributions, correlations, recovery rates, or event frequencies were invented or implemented.

---

## MCFX-03 — DSCR breach-probability CI

**Supersedes**

- `03_bankability_methodology.md:77`
- `raw/P3_c_mc_fx_rigor.json:4`

**Disposition: CONFIRMED, with exact-impact correction.**

Code evidence:

- Bare count: `analytics/mc/convergence.py:246-258`.
- Noise-tolerant single-source primitive: `analytics/core/covenant_breach.py:30-55`.
- Unconditional engine wiring: `analytics/mc/engine.py:979-990`.
- Canonical threshold resolves to 1.30 through `constraints.min_dscr_covenant`: `scenarios/dutchbay_lendercase_2025Q4.yaml:526-532` and `analytics/mc/covenant.py:24-58`.

Independent common-seed results:

| Trials | Bare `<1.30` | Tolerant `prob_breach` | Overstatement |
|---:|---:|---:|---:|
| 64 | 98.4375% | 85.9375% | 12.5000 pp |
| 128 | 97.65625% | 85.15625% | 12.5000 pp |
| 256 | 99.609375% | 86.71875% | 12.890625 pp |

At 256 trials, the wrong Wilson CI was approximately `[97.821%, 99.931%]`; the same Wilson method around the tolerance-corrected count was `[82.014%, 90.338%]`.

Important qualification: the corrected breach probability is not zero here. The fixed-debt stressed array contains genuine DSCR values down to approximately 1.2167. The bug adds near-floor floating-point values to those genuine breaches.

**Corrected claim**

> The DSCR breach-probability point estimate and Wilson CI in `percentile_ci_diagnostic` use a bare `< floor` count instead of the repository’s tolerance-aware covenant primitive. Seed-42 reproductions overstate the point by 12.5 pp at 64 and 128 trials and 12.890625 pp at 256 trials. The exact production impact must be recalculated from the actual governed run; no 100,000-trial finance run was evidenced. Other percentile intervals are not invalidated by this counting defect.

**Canon impact**

No deterministic KPI impact. The MC metadata point estimate, breach Wilson interval, and any consumer relying on them are wrong.

**Owner/dependency**

Risk-metrics owner. Dependency: route the diagnostic through the shared covenant primitive, add exact regression tests for point and CI, and regenerate actual run metadata.

**Limitations / unfinished items**

- The impact at the eventual governed production trial count is unknown until that run exists.
- No code remediation was applied in this refuter checkpoint.

---

## MCFX-04 — duplicate VaR/CVaR paths and CASPER scope

**Supersedes**

- `03_bankability_methodology.md:78`
- `raw/P3_c_mc_fx_rigor.json:5`

**Disposition: CONFIRMED, scope corrected.**

The two definitions are demonstrably different:

- Engine metadata: quantile-interpolated VaR and mean of all values `<= VaR`: `analytics/mc/engine.py:163-207`.
- Core risk analyzer: integer order-statistic index and mean of values strictly before that index: `analytics/core/risk_metrics.py:229-285`.

Deterministic reproduction with arrays `0..n-1`, 95% confidence:

| n | Engine VaR / CVaR | Core analyzer VaR / CVaR |
|---:|---:|---:|
| 20 | 0.95 / 0.00 | 1.00 / 0.00 |
| 100 | 4.95 / 2.00 | 5.00 / 2.00 |
| 101 | 5.00 / 2.50 | 5.00 / 2.00 |

CASPER omission is confirmed:

- Lean MC serializer has project IRR/NPV/DSCR only: `analytics/casper/casper_payload.py:307-342`.
- CASPER `mc_risk` delegates to percentile/covenant tables with no CVaR: `analytics/casper/casper_payload.py:393-430` and `analytics/mc/exports.py:229-268`.

But “neither reaches a lender-facing surface” would be false:

- Async analysis returns the engine result, including metadata, verbatim: `app/api/responses.py:124-155` and `app/jobs/analysis_runner.py:118-128`.
- The opt-in capital-risk report and client surface expose the core analyzer’s VaR/CVaR: `app/reports/templates/report.html.j2:434-473`, `app/api/surface.py:105-141,251-280`.

**Corrected claim**

> The engine metadata and capital-risk layer maintain distinct VaR/ES definitions and can disagree even on deterministic samples. CASPER’s lean `monte_carlo` and `mc_risk` blocks omit CVaR, while the async analysis payload and opt-in capital-risk report/client surfaces expose one or the other implementation. Select and document one canonical quantile/ES convention, reconcile all consumers, and label exact tail direction and inclusion rules.

**Canon impact**

No deterministic impact. Stochastic VaR/CVaR values and cross-surface consistency may change after consolidation.

**Owner/dependency**

Risk-methodology/analytics owner and CASPER contract owner. Dependency: approved ES convention, golden vectors, serializer decision, and versioned contract review.

**Limitations / unfinished items**

- No production MC artefact existed against which to quantify the two methods’ live difference.
- The canonical definition remains an owner/model-risk decision.

---

## MCFX-05 — Weibull ±10% uncertainty

**Supersedes**

- `03_bankability_methodology.md:79`
- `raw/P3_c_mc_fx_rigor.json:6`

**Disposition: PARTIALLY CONFIRMED.**

Confirmed:

- Canon contains an uncited `weibull_uncertainty_pct: 10.0`: `scenarios/dutchbay_lendercase_2025Q4.yaml:558-562`.
- The legacy AEP-MC module also hardcodes/defaults 10%: `analytics/simulation/monte_carlo_aep.py:55-85,216-235`.
- No traceable derivation connects this parameter to the separate AEP exceedance budget.

Refuted or unestablished:

- It is not a finance-MC driver. Finance MC samples `project.capacity_factor` uniformly over `[0.2988,0.3652]`: `scenarios/dutchbay_lendercase_2025Q4.yaml:576-580`.
- `pipeline_aep_v14` never passes scenario `weibull_uncertainty_pct` into `run_monte_carlo_aep`; the callee would use its own default.
- The canonical wind-AEP integration currently fails because it calls `.get` on the finance engine’s list-form `parameters`.
- A separate `analytics/wind/mc_aep_weibull.py:77-120` uses another default, 6%, and has no production caller outside tests.
- Therefore the audit cannot infer an executed canonical A/k band or its impact.

**Corrected claim**

> The repository contains an unattributed 10% Weibull A/k uncertainty knob in the canonical scenario and legacy wind-AEP code, but it is not the live finance-MC wind driver and the canonical wind-AEP adapter currently cannot consume the shared list-form MC schema. Treat the knob as ambiguous/dead until the wind and finance simulation configurations are separated, provenance is supplied, and an actual wind-AEP run manifest establishes what was used.

**Canon impact**

None on deterministic KPIs. No trustworthy current wind-AEP MC sidecar impact can be stated because the canonical integration fails before execution.

**Owner/dependency**

Wind-resource methodology owner and configuration-architecture owner. Dependency: split finance-MC and wind-AEP schemas, derive the uncertainty from an approved EYA budget, and run/validate a governed sidecar.

**Limitations / unfinished items**

- No canonical wind-AEP MC was executed because the reproduced schema failure occurs before simulation.
- The approved source and value for the eventual Weibull uncertainty remain unresolved.

---

## MCFX-06 — convergence metadata as a positive finding

**Supersedes**

- `03_bankability_methodology.md:72`
- `raw/P3_c_mc_fx_rigor.json:7`

**Disposition: PARTIALLY CONFIRMED.**

Confirmed implementation:

- Every successful `MonteCarloEngine.run` attaches `convergence`, `percentile_ci`, and `run_meta`: `analytics/mc/engine.py:975-999`.
- Both diagnostic functions skip metrics with fewer than 30 finite trials: `analytics/mc/convergence.py:59-133,178-218`.
- Probe:

```text
n=20: convergence_keys=[]; percentile_ci_keys=[]
n=30: seven finance metric entries in each
```

Not supported:

- There is no automated convergence verdict or target precision.
- The mean CI is approximate under LHS/Iman-Conover and expressly does not certify tails: `analytics/mc/convergence.py:82-88`.
- The percentile rank interval is also described as approximate for LHS prefixes: `analytics/mc/convergence.py:20-38`.
- MCFX-03 corrupts the DSCR breach subblock.
- “Above typical sector practice” was not tied to a comparative source or survey.

**Corrected claim**

> Every successful finance-MC run stores convergence and percentile-CI metadata keys; per-metric diagnostics populate when at least 30 finite trials exist. These diagnostics quantify approximate mean and percentile uncertainty for a reader to compare against separately declared tolerances. They do not themselves certify sufficiency, and the DSCR breach-probability subblock is wrong at commit `7e99f34`.

**Canon impact**

None on deterministic or MC point bands; metadata/disclosure only.

**Owner/dependency**

Model-validation owner. Dependency: user-approved precision gates by statistic and use case, corrected breach counting, and acceptance tests on actual governed runs.

**Limitations / unfinished items**

- No evidence-based cross-sector benchmark was located for the audit’s “above typical practice” statement.
- Convergence acceptance thresholds remain unauthored and unapproved.

---

## EQ-01 — canonical honesty versus blanket repository-wide assertions

**Supersedes**

- `03_bankability_methodology.md:20,27,83,91`
- `raw/P3_d_equity_irr_and_synthesis.json:2,5`

**Disposition: PARTIALLY CONFIRMED; the universal assertions are refuted.**

### What is confirmed

An actual canonical pipeline/report-context reproduction returned:

```text
project_irr          0.014551597740253388
equity_irr          -0.05841298678542661
project_npv        -79,273,039.20645273
equity_npv         -81,592,659.21758533
min_dscr             1.285740985294611
discount_rate_used   0.100202604022396
headline             Value-destructive at the modeled assumptions.
```

The generated HTML contained:

- `Value-destructive at the modeled assumptions.`
- `Project IRR`
- `Equity IRR`
- `-5.84%`

The target report test passed:

```text
tests/app/test_report_model.py::test_verdict_value_destructive
1 passed
```

Strong report paths:

- Canon verdict and sign-aware wording: `app/reports/report_model.py:944-1049`.
- Negative-equity IC red flag: `app/reports/report_model.py:1117-1150`.
- Executive table co-locates project/equity IRR: `app/reports/templates/report.html.j2:145-168`.
- Default KPI table is adjacent: `config/report_defaults.yaml:31-42`.
- Full-pipeline API block includes both: `api/pipeline_api.py:99-111,479-493`.
- Executive workbook includes both: `analytics/executive_workbook.py:180-192`.

No canon KPI or report verdict defect was reproduced.

### What is refuted

1. **“Requires a positive equity return” is incomplete.**

`_build_verdict` prefers `equity_npv > 0` and only falls back to `equity_irr` if NPV is absent: `app/reports/report_model.py:951-966`.

A type-valid adversarial probe:

```python
{
    "project_irr": 0.12,
    "discount_rate_used": 0.08,
    "equity_npv": 1.0,
    "equity_irr": -0.01,
    "min_dscr": 1.50,
    "balloon_pct": 0.10,
}
```

returned:

```text
headline: Bankable at the modeled assumptions.
note:     Equity IRR -1.00% — negative to sponsors.
```

Thus the architecture can emit a Bankable headline alongside a negative equity-IRR note if the two equity metrics disagree. This is a synthetic inconsistency probe, not a demonstration that the canonical engine currently emits that combination, but it directly refutes “architecturally incapable.”

2. **Not every external surface co-locates both IRRs.**

- Authenticated `/v1/sensitivity/run-tornado/` is intentionally single-metric and defaults to project IRR: `api/sensitivity_api.py:34-120`, mounted at `app/api/main.py:519-535`.
- The dashboard renders one selected metric at a time and defaults to project IRR: `analytics/dashboard/streamlit_app.py:34-40`.
- CASPER’s lean MC subblock calls its project-only block simply `"irr"` and carries no equity-IRR distribution: `analytics/casper/casper_payload.py:307-342`.

These are analytical sub-surfaces and are not automatically misleading, but they refute “no code path” and “every surface.”

3. **“No misleading presentation was found” is directly refuted.**

The actual generated canonical HTML contains:

```text
FX path stressed to CBSL/IMF projections
```

from `config/report_defaults.yaml:50-58`.

No IMF FX projection or stress input used by canon was found. Actual canonical inputs are:

- BIS-history-derived deterministic 5.89% depreciation: `scenarios/dutchbay_lendercase_2025Q4.yaml:284-307`.
- Uniform finance-MC spot band `[300,367]`: lines 593–596.
- Calibrated BIS mixture not enabled.

The report statement is therefore unsupported/misattributed at this commit. A repo-wide search found no corresponding IMF projection input; merely listing IMF as a possible approved provider is not evidence that an IMF projection was used.

**Corrected claim**

> In the audited canonical case, the main HTML/PDF report, full finance API block, executive workbook, and IC red-flag logic co-locate the negative equity IRR with project IRR and correctly render the case as value-destructive. Repository-wide absence claims are not supportable: several intentionally single-metric analytics surfaces expose project IRR alone, the verdict can be contradictory on a positive-NPV/negative-IRR payload, and the generated risk register incorrectly states that canon was stressed to CBSL/IMF projections. Limit the positive assurance to enumerated, reproduced decision surfaces and correct the FX mitigation wording to the actual BIS-derived deterministic drift and authored uniform MC band.

**Canon impact**

- Current canon headline/KPIs: none; correctly value-destructive.
- Report narrative: current canonical HTML contains an unsupported FX methodology statement.
- Architecture: latent contradictory-verdict risk for inconsistent or non-conventional equity-return metrics.

**Owner/dependency**

Reporting model owner, report-content owner, and API/contract owner. Dependencies: define IRR/NPV consistency policy, fail or downgrade on contradictory equity signals, inventory decision versus analytical surfaces, and source every methodology statement from the run manifest.

**Limitations / unfinished items**

- The positive-NPV/negative-IRR probe is synthetic; the refuter did not establish that the canonical engine emits that combination.
- Deployed front ends, cached reports, and operational report copies outside the repository were not inspected.
- The exact replacement wording for the unsupported CBSL/IMF claim requires report-content owner approval.

---

## EQ-02 — project-only operational logs

**Supersedes**

- `03_bankability_methodology.md:85`
- `raw/P3_d_equity_irr_and_synthesis.json:3`

**Disposition: CONFIRMED, but the audit inventory was incomplete.**

At least three production info-log sites omit equity IRR:

- `analytics/evaluate_scenario.py:120-128`
- `analytics/pipeline_v14_enhanced.py:976-981`
- `analytics/pipeline_v14_enhanced.py:1011-1016`

A separate analytics log correctly prints both at `analytics/pipeline_analytics_v14.py:173-176`, demonstrating inconsistency rather than a single deliberate logging policy.

**Corrected claim**

> At least three production operational log messages print project IRR and other KPIs while omitting equity IRR. The returned API/report objects retain equity IRR, and no lender-deliverable numerical impact was demonstrated. This is an observability-consistency gap, not currently a finance-output defect.

**Canon impact**

None on calculations or lender artefacts. Operational triage and copied log excerpts can present an incomplete return picture.

**Owner/dependency**

Observability owner. Dependency: one canonical KPI-summary formatter and log tests.

**Limitations / unfinished items**

The search covered literal and multiline logger calls in the audited repository; deployed log processors and externally copied logs were not inspected.

---

## EQ-03 — causal explanation and rebaseline history

**Supersedes**

- `03_bankability_methodology.md:85`
- `raw/P3_d_equity_irr_and_synthesis.json:4`

**Disposition: PARTIALLY CONFIRMED.**

Confirmed comment-only material:

- The ten-step dated correction sequence is in YAML comments at `scenarios/dutchbay_lendercase_2025Q4.yaml:683-732`.
- `yaml.safe_load` removes it; the loaded `expected_results` contains only six numerical keys and no rebaseline narrative.
- No report code reads comment text.

But the report is not causally silent:

- A project-to-equity IRR bridge is built from the live run at `app/reports/report_model.py:2253-2291`.
- Production report routes pass `run_result`: `app/api/main.py:322-359` and `app/reports/capital_risk_emit.py:203-220`.
- The bridge explicitly decomposes leverage, cost of debt, tax shield, and a closing residual: `analytics/irr_bridge.py:83-108,165-211`.
- It is rendered in the report at `app/reports/templates/report.html.j2:1092-1145`.

Actual canonical bridge reproduction:

| Bridge item | Contribution / endpoint |
|---|---:|
| Project IRR | 1.45516% |
| Leverage | +6.88079 pp |
| Cost of debt | −7.64051 pp |
| Tax shield | +0.93391 pp |
| Residual: timing/interactions, principal, lockup, DSRA, WHT | −7.47064 pp |
| Total project-to-equity uplift | −7.29646 pp |
| Equity IRR | −5.84130% |
| Reconciled | Yes |

The risk register also supplies the top-line FX/tariff mismatch at `config/report_defaults.yaml:50-58`, though its claimed CBSL/IMF stress provenance is wrong as described under EQ-01.

The raw audit’s “roughly half” attribution is not reproducible as a controlled causal result. The YAML sequence is path- and order-dependent, combines opposing changes in some steps, and does not isolate interactions. The live bridge is a current-state cashflow substitution bridge, not the dated counterfactual history.

**Corrected claim**

> The generated report already explains the current project-to-equity gap through a reconciled leverage/cost-of-debt/tax-shield/residual bridge. What remains comment-only is the dated ten-step rebaseline provenance and an explicit renegotiable-versus-intrinsic classification. The sequential comment deltas are not a controlled causal decomposition; do not claim “roughly half” without one-factor reruns plus interaction treatment or another approved attribution method.

**Canon impact**

No KPI impact. Disclosure/provenance only.

**Owner/dependency**

Financial-analysis and report-content owners. Dependency: structured rebaseline register, retained pre/post run hashes, an approved attribution method, and report projection of the resulting controlled bridge.

**Limitations / unfinished items**

- No controlled one-factor-plus-interaction attribution was executed.
- No owner decision has yet classified each driver as renegotiable, intrinsic, mitigated, or residual.

## Reproduction command ledger

Representative exact commands used from the audited worktree:

```bash
git rev-parse HEAD
git status --short --branch
```

```bash
/Users/aruna/Downloads/dutchbay-epc-model/.venv/bin/pytest \
  -q tests/app/test_report_model.py::test_verdict_value_destructive
```

```bash
/Users/aruna/Downloads/dutchbay-epc-model/.venv/bin/python - <<'PY'
from analytics.fx.fx_history import load_pinned_history
from analytics.fx.fx_calibration import calibrate_fx
cal = calibrate_fx(load_pinned_history(), pinned_spot=333.79, frequency="weekly")
for q in (.001, .01, .05, .10, .50, .90, .95, .99, .999):
    print(q, cal.sampler().spot_from_unit(q), 300 + 67*q)
PY
```

```bash
/Users/aruna/Downloads/dutchbay-epc-model/.venv/bin/python - <<'PY'
import copy, logging, numpy as np
from analytics.scenario_loader import load_scenario_config
from analytics.mc.engine import MonteCarloEngine
from analytics.core.covenant_breach import prob_breach
logging.disable(logging.CRITICAL)
cfg = load_scenario_config("scenarios/dutchbay_lendercase_2025Q4.yaml")
cfg["monte_carlo"]["allow_toy_fallback"] = False
for label, distribution in (("uniform", "uniform"), ("calibrated", "fx_calibrated")):
    c = copy.deepcopy(cfg)
    p = next(x for x in c["monte_carlo"]["parameters"]
             if x["name"] == "fx.start_lkr_per_usd")
    p["distribution"] = distribution
    result = MonteCarloEngine(c, seed=42).run(n_trials=256)
    print(label, result.failed_iterations, result.metadata.get("toy_fallback_count"))
    for metric in ("project_irr", "equity_irr", "project_npv", "dscr_min"):
        a = np.asarray(result.trials[metric], dtype=float)
        print(metric, np.quantile(a, [.05, .10, .50]), a.mean(), a.min(), a.max())
    if label == "uniform":
        a = np.asarray(result.trials["dscr_min"], dtype=float)
        print(np.mean(a < 1.30), prob_breach(a, 1.30))
PY
```

```bash
/Users/aruna/Downloads/dutchbay-epc-model/.venv/bin/python - <<'PY'
from analytics.scenario_loader import load_scenario_config
from analytics.wind.pipeline_aep_v14 import integrate_aep_pipeline
cfg = load_scenario_config("scenarios/dutchbay_lendercase_2025Q4.yaml")
try:
    integrate_aep_pipeline(cfg, run_monte_carlo=True)
except Exception as exc:
    print(type(exc).__name__, str(exc))
PY
```

```bash
/Users/aruna/Downloads/dutchbay-epc-model/.venv/bin/python - <<'PY'
import numpy as np
from analytics.mc.engine import _tail_risk
from analytics.core.risk_metrics import RiskConfig, TailRiskAnalyzer
analyzer = TailRiskAnalyzer(RiskConfig(
    confidence_level=.95, target_return=0,
    min_dscr=1.2, min_llcr=1.25, min_plcr=1.3,
))
for n in (20, 100, 101):
    values = np.arange(n, dtype=float)
    print(n, _tail_risk([{"x": float(v)} for v in values], .95)["x"],
          analyzer.calculate_var_cvar(values, "x").model_dump())
PY
```

```bash
/Users/aruna/Downloads/dutchbay-epc-model/.venv/bin/python - <<'PY'
from app.reports.report_model import _build_verdict, load_report_config
kpis = {
    "project_irr": .12, "discount_rate_used": .08,
    "equity_npv": 1.0, "equity_irr": -.01,
    "min_dscr": 1.5, "balloon_pct": .10,
}
print(_build_verdict(kpis, load_report_config().covenants).model_dump())
PY
```

## Overall limitations and explicitly unfinished work

- This checkpoint is a read-only refuter record, not an implementation or remediation register update.
- No audited repository code, scenario, report default, findings register, or evidence register was edited.
- No production-scale finance Monte Carlo was run; no such canonical run configuration or acceptance policy was evidenced.
- The 256-trial FX comparison is illustrative and cannot certify tail precision.
- Transaction-policy choices—risk inclusion, calibrated FX activation, tail truncation, ES convention, convergence tolerances, and causal classification—remain expressly unresolved owner decisions.
- The refuter inspected repository-authored and generated-in-memory surfaces, not deployed applications, cached artefacts, external report copies, or production logs.
- The official-source analysis used the remediation workspace’s preserved converted copies; no new live source refresh was performed in this pass.

Final source-worktree integrity check before checkpoint creation remained:

```text
HEAD 7e99f34d75b9c3d44a5c5b260cedbe403d2f79e8
git status: clean
```

No 100,000-trial finance run was attempted: it was neither evidenced as canonical nor necessary to refute the routing claim, and a new long stochastic run would not retroactively validate the immutable audit.

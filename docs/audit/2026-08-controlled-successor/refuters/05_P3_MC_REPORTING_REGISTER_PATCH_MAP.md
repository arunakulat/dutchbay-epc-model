# P3 MC / FX / Equity-Reporting Register and Corrigendum Patch Map

## Control status

This is a read-only, field-by-field patch specification. It records the exact changes required to reconcile the completed independent P3 refuter into the current machine-readable findings register and controlled corrigendum. It does not itself amend either controlled draft.

- Audited worktree: `/Users/aruna/Downloads/dutchbay-wt-audit-corrigendum`
- Audited commit: `7e99f34d75b9c3d44a5c5b260cedbe403d2f79e8`
- Immutable audit: `/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_2026-08`
- Remediation workspace: `/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_Remediation_2026-08`
- Controlling refuter: `refuters/04_P3_MC_REPORTING_REFUTER_CHECKPOINT.md`
- Controlling refuter SHA-256: `2e150dc6b1f949418236256057b3e291f80d7c466873d436a15db37523631685`
- Findings-register baseline SHA-256: `b64c8e4430ea9febd58226c4a8a039fb2001fbce5979e433631c53216c3864f8`
- Corrigendum baseline SHA-256: `00c86be397db186494619ecbaa4935e35dee806279105bf2dbd67648b7271bb0`
- Status: `WORKING PATCH MAP — not for Board, lender, investor, or external circulation`

For the field mapping below, `REF` means the full absolute path:

`/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_Remediation_2026-08/refuters/04_P3_MC_REPORTING_REFUTER_CHECKPOINT.md`

Do not store `REF` as an alias in JSON; expand it to that full path.

## Exact disposition and control-field changes

| ID | Current to corrected disposition | Confidence | Verification | Status | Severity |
|---|---|---|---|---|---|
| `EVAL-10` | new to `refuted` | `high` | `independent_reproduction` | `requires_correction` | `high` |
| `P3-MCFX-01` | `partially_confirmed` unchanged | `medium` to `high` | `single_pass_code_inspection` to `independent_reproduction` | `open` unchanged | `critical` unchanged |
| `P3-MCFX-02` | `deferred` to `partially_confirmed` | `medium` to `high` | `single_pass_code_inspection` to `source_and_code_refuter` | `deferred` to `open` | `high` unchanged |
| `P3-MCFX-03` | `confirmed` unchanged | `high` unchanged | `finder_refuter` to `independent_reproduction` | `open` unchanged | `high` unchanged |
| `P3-MCFX-04` | `partially_confirmed` to `confirmed` | `medium` to `high` | `single_pass_code_inspection` to `independent_reproduction` | `open` unchanged | `medium` unchanged |
| `P3-MCFX-05` | `partially_confirmed` unchanged | `medium` to `high` | `single_pass_code_inspection` to `independent_reproduction` | `open` unchanged | `medium` unchanged |
| `P3-MCFX-06` | `not_a_defect` to `partially_confirmed` | `medium` to `high` | `single_pass_code_inspection` to `independent_reproduction` | `closed` to `open` | `low` unchanged |
| `P3-EQ-01` | `not_a_defect` to `partially_confirmed` | `medium` to `high` | `single_pass_code_inspection` to `independent_reproduction` | `closed` to `open` | `low` unchanged |
| `P3-EQ-02` | `partially_confirmed` to `confirmed` | `medium` to `high` | `single_pass_code_inspection` to `finder_refuter` | `open` unchanged | `low` unchanged |
| `P3-EQ-03` | `partially_confirmed` unchanged | `medium` to `high` | `single_pass_code_inspection` to `independent_reproduction` | `open` unchanged | `medium` unchanged |

The existing severities remain unchanged because the refuter adjudicated truth, scope, and reproducibility rather than applying a new severity scale. `EVAL-10` is High because it corrects a lender-relevant assurance claim about the existence and sufficiency of stochastic evidence.

## New record — EVAL-10

- `finding_id`: `EVAL-10`
- `title`: `Canonical 100,000-trial finance-Monte-Carlo run was not evidenced`
- `source_phase`: `EVAL`
- `severity`: `high`
- `disposition`: `refuted`
- `confidence`: `high`
- `verification_level`: `independent_reproduction`
- `status`: `requires_correction`

`evidence_refs`:

- `/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_2026-08/03_bankability_methodology.md`
- `/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_2026-08/raw/P3_c_mc_fx_rigor.json`
- `/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_Remediation_2026-08/refuters/04_P3_MC_REPORTING_REFUTER_CHECKPOINT.md`

`code_anchors`:

- `scenarios/dutchbay_lendercase_2025Q4.yaml:552-555`
- `analytics/wind/pipeline_aep_v14.py:172-219`
- `analytics/mc/engine.py:603-618`
- `analytics/mc/engine.py:786-805`
- `analytics/cli/cli_monte_carlo_hydra.py:167-209`
- `analytics/evaluation_v14.py:461-521`
- `app/reports/capital_risk_emit.py:62-84`
- `app/jobs/models.py:247-253`
- `run_full_pipeline_v14.py:763-778`
- `analytics/mc/convergence.py:4-38`
- `analytics/mc/convergence.py:59-133`

`reproduction_refs`:

- `REF:27-71`
- After separate persistence: `/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_Remediation_2026-08/reproductions/p3_mc_trial_routing_reproduction.json`

`canon_impact`:

```json
{
  "level": "none",
  "direction": "none",
  "detail": "The deterministic KPI vector is unaffected. The audit's characterization of existing stochastic evidence and convergence strength must change; finance-MC bands at the intended lender run count remain unestablished."
}
```

- `owner_role`: `risk_methodology_and_finance_mc_orchestration_owner`

`remediation_dependency`:

```json
[
  "Choose one governed finance-MC run configuration.",
  "Define acceptance tolerances by statistic and use case.",
  "Emit a manifest containing the actual effective n_trials, seed, commit, configuration hash, failures, and fallback count.",
  "Retain and independently review the resulting risk pack."
]
```

`corrected_claim`:

> The scenario authors a 100,000-scenario count for a legacy wind-AEP simulation path. The finance Monte Carlo has no scenario-canonical trial count: callers currently request between 1,000 and 20,000 by default or policy. No executed 100,000-trial finance-MC pack was evidenced. Statistical sufficiency must be assessed against declared mean, percentile, breach-probability, and ES/CVaR precision tolerances on an actual run manifest; trial count alone is not a certificate.

`limitations`:

> No production-scale finance Monte Carlo was run or found. The canonical wind-AEP adapter failed before simulation because it expects mapping-form parameters while the canonical finance-MC schema supplies a list. No transaction-approved precision thresholds or production risk-pack manifest existed at the audited commit.

## P3-MCFX-01

- `title`: `Canon omits calibrated FX; available calibration is a one-year spot mixture`
- `disposition`: `partially_confirmed`
- `confidence`: `high`
- `verification_level`: `independent_reproduction`
- `status`: `open`

Retain the two current immutable-audit `evidence_refs` and append the full `REF` path.

Replace `code_anchors` with:

- `scenarios/dutchbay_lendercase_2025Q4.yaml:593-596`
- `analytics/mc/engine.py:378-456`
- `analytics/mc/engine.py:482-507`
- `analytics/mc/engine.py:632-645`
- `analytics/fx/fx_history.py:12-32`
- `analytics/fx/fx_history.py:208-255`
- `analytics/fx/fx_calibration.py:1-34`
- `analytics/fx/fx_calibration.py:164-253`
- `analytics/fx/fx_calibration.py:279-327`

`reproduction_refs`:

- `REF:94-137`
- `REF:646-678`
- After separate persistence: `/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_Remediation_2026-08/reproductions/p3_fx_calibration_seed42_n256_reproduction.json`

`canon_impact`:

```json
{
  "level": "potential",
  "direction": "wider_and_skewed_fx_sensitive_stochastic_tails_if_activated",
  "detail": "No deterministic KPI movement. Only stochastic risk bands, extrema, VaR/CVaR, and risk disclosures change unless base-case FX assumptions are separately re-authorized."
}
```

- `owner_role`: `fx_model_risk_and_transaction_financial_analysis_owner`

`remediation_dependency`:

```json
[
  "Validate the calibration implementation and pinned source vintage.",
  "Approve the modeled horizon, tail and truncation policy.",
  "Create one governed finance-MC configuration.",
  "Run an independent model-validation review.",
  "Approve lender-facing methodology and limitations disclosure before activation."
]
```

`corrected_claim`:

> No committed scenario activates the available BIS-history-calibrated one-year FX spot mixture; canonical finance MC uses a symmetric uniform spot band. A seed-matched 256-trial refuter run confirms that activation broadens and skews FX-sensitive output tails, especially extrema. The current calibrated feature is not a full 20-year regime/path model and does not add annual drift variance. Validate its horizon, tail, source vintage, and transaction use before enabling it in a governed lender run.

`limitations`:

> No production-scale lender Monte Carlo was run; the 256-trial comparison is an adversarial illustration. No transaction owner has approved the calibrated tail, truncation, horizon, or activation. A full 20-year regime/path model remains an unimplemented future enhancement.

## P3-MCFX-02

- `title`: `Canon samples six finance-MC drivers; wider risk treatment is transaction-specific`
- `disposition`: `partially_confirmed`
- `confidence`: `high`
- `verification_level`: `source_and_code_refuter`
- `status`: `open`

Retain the current audit refs and append:

- Full `REF` path
- `/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_Remediation_2026-08/sources/converted/IFC_Utility_Scale_Solar_Project_Developer_Guide_2015.txt`
- `/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_Remediation_2026-08/sources/converted/WBG_PPP_Handbook_2024.txt`
- `/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_Remediation_2026-08/sources/converted/World_Bank_IDA_Sri_Lanka_Renewable_Energy_2025_PAD.txt`

Replace `code_anchors` with:

- `scenarios/dutchbay_lendercase_2025Q4.yaml:569-629`
- `analytics/core/sensitivity_runner.py:31-54`
- `scenarios/dutchbay_lendercase_2025Q4.yaml:461-468`
- `scenarios/dutchbay_lendercase_2025Q4.yaml:534-539`
- `finance/debt_v14.py:382-410`
- `finance/debt_v14.py:674-689`

`reproduction_refs`:

- `REF:176-227`
- After separate persistence: `/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_Remediation_2026-08/reproductions/p3_mc_parameter_inventory.json`
- After source-register extension: the three new PSR IDs specified under Evidence persistence requirements

`canon_impact`:

```json
{
  "level": "potential",
  "direction": "unknown",
  "detail": "There is no deterministic impact. Stochastic and credit-decision impact may be material after distributions, correlations, event logic, and mitigations are authorized."
}
```

- `owner_role`: `transaction_risk_and_finance_engine_owner`

`remediation_dependency`:

```json
[
  "Approve the transaction risk taxonomy and treatment by risk.",
  "Obtain source-backed distributions and correlations.",
  "Identify and test the live tranche-rate shock paths.",
  "Specify a construction-delay timing model.",
  "Specify an offtaker default and recovery mechanism if quantitative treatment is selected.",
  "Add model-validation and reporting tests for inclusions, exclusions, mitigations, and residual risks."
]
```

`corrected_claim`:

> The canonical finance MC jointly samples six operating/economic drivers and omits rate/refinancing, construction-delay, tax-change, and offtaker-credit events from that joint distribution. Official guidance supports identifying all material risks and quantitatively stressing key financing and project variables, but whether a risk belongs in MC, deterministic scenario analysis, a structural event tree, or qualitative/contractual treatment is transaction-specific. The risk register should disclose inclusions, exclusions, mitigations, and residual risks; trial count must not imply completeness.

`limitations`:

> The final transaction risk universe and treatment of each risk remain owner decisions, not refuter determinations. No distributions, correlations, recovery rates, or event frequencies were invented or implemented.

## P3-MCFX-03

- `title`: `DSCR breach-probability diagnostic bypasses the tolerance-aware covenant comparator`
- `disposition`: `confirmed`
- `confidence`: `high`
- `verification_level`: `independent_reproduction`
- `status`: `open`

Retain current evidence refs and append the full `REF` path.

Replace `code_anchors` with:

- `analytics/mc/convergence.py:246-258`
- `analytics/core/covenant_breach.py:30-55`
- `analytics/mc/engine.py:979-990`
- `scenarios/dutchbay_lendercase_2025Q4.yaml:526-532`
- `analytics/mc/covenant.py:24-58`

`reproduction_refs`:

- `P2-MC-SENS-02`
- `REF:246-254`
- `REF:656-678`
- After separate persistence: `/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_Remediation_2026-08/reproductions/p3_dscr_breach_ci_seed42_reproduction.json`

`canon_impact`:

```json
{
  "level": "confirmed",
  "direction": "lower_tolerance_aware_breach_probability_and_revised_wilson_interval",
  "detail": "No deterministic KPI is affected. The MC metadata point estimate, breach Wilson interval, and any consumer relying on them are wrong. The observed magnitude is sample-specific rather than universally 12.5 percentage points."
}
```

- `owner_role`: `risk_metrics_owner`

`remediation_dependency`:

```json
[
  "Route the diagnostic through the shared tolerance-aware covenant primitive.",
  "Add exact regression tests for the point estimate and Wilson interval.",
  "Regenerate metadata from the eventual governed finance-MC run."
]
```

`corrected_claim`:

> The DSCR breach-probability point estimate and Wilson CI in `percentile_ci_diagnostic` use a bare `< floor` count instead of the repository’s tolerance-aware covenant primitive. Seed-42 reproductions overstate the point by 12.5 pp at 64 and 128 trials and 12.890625 pp at 256 trials. The exact production impact must be recalculated from the actual governed run; no 100,000-trial finance run was evidenced. Other percentile intervals are not invalidated by this counting defect.

`limitations`:

> The impact at the eventual governed production trial count is unknown until that run exists. The refuter did not apply code remediation.

## P3-MCFX-04

- `title`: `VaR/ES definitions diverge and CASPER omits CVaR while other surfaces expose it`
- `disposition`: `confirmed`
- `confidence`: `high`
- `verification_level`: `independent_reproduction`
- `status`: `open`

Retain current evidence refs and append the full `REF` path.

Replace `code_anchors` with:

- `analytics/mc/engine.py:163-207`
- `analytics/core/risk_metrics.py:229-285`
- `analytics/casper/casper_payload.py:307-342`
- `analytics/casper/casper_payload.py:393-430`
- `analytics/mc/exports.py:229-268`
- `app/api/responses.py:124-155`
- `app/jobs/analysis_runner.py:118-128`
- `app/reports/templates/report.html.j2:434-473`
- `app/api/surface.py:105-141`
- `app/api/surface.py:251-280`

`reproduction_refs`:

- `REF:286-307`
- `REF:693-706`
- After separate persistence: `/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_Remediation_2026-08/reproductions/p3_var_cvar_definition_vectors.json`

`canon_impact`:

```json
{
  "level": "potential",
  "direction": "definition_dependent_var_cvar_and_cross_surface_reconciliation",
  "detail": "There is no deterministic impact. Stochastic VaR/CVaR values and cross-surface consistency may change after consolidation."
}
```

- `owner_role`: `risk_methodology_and_casper_contract_owner`

`remediation_dependency`:

```json
[
  "Approve one ES/CVaR convention, including quantile interpolation, tail direction, equality and floor handling.",
  "Create golden-vector tests.",
  "Decide which CASPER and external serializers expose the statistic.",
  "Perform a versioned contract review before changing external surfaces."
]
```

`corrected_claim`:

> The engine metadata and capital-risk layer maintain distinct VaR/ES definitions and can disagree even on deterministic samples. CASPER’s lean `monte_carlo` and `mc_risk` blocks omit CVaR, while the async analysis payload and opt-in capital-risk report/client surfaces expose one or the other implementation. Select and document one canonical quantile/ES convention, reconcile all consumers, and label exact tail direction and inclusion rules.

`limitations`:

> No production Monte Carlo artefact existed against which to quantify the live difference between the two methods. The canonical ES definition remains an owner/model-risk decision.

## P3-MCFX-05

- `title`: `The 10% Weibull knob is unattributed, not live finance MC, and blocked by schema mismatch`
- `disposition`: `partially_confirmed`
- `confidence`: `high`
- `verification_level`: `independent_reproduction`
- `status`: `open`

Retain current evidence refs and append the full `REF` path.

Replace `code_anchors` with:

- `scenarios/dutchbay_lendercase_2025Q4.yaml:558-562`
- `scenarios/dutchbay_lendercase_2025Q4.yaml:576-580`
- `analytics/simulation/monte_carlo_aep.py:55-85`
- `analytics/simulation/monte_carlo_aep.py:216-235`
- `analytics/wind/pipeline_aep_v14.py:172-219`
- `analytics/wind/mc_aep_weibull.py:77-120`

`reproduction_refs`:

- `REF:337-349`
- `REF:681-690`
- After separate persistence: `/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_Remediation_2026-08/reproductions/p3_wind_mc_schema_probe.json`

`canon_impact`:

```json
{
  "level": "none",
  "direction": "none",
  "detail": "There is no deterministic KPI impact. No trustworthy current wind-AEP MC sidecar impact can be stated because the canonical integration fails before execution."
}
```

- `owner_role`: `wind_methodology_and_configuration_architecture_owner`

`remediation_dependency`:

```json
[
  "Separate the finance-MC and wind-AEP configuration schemas.",
  "Derive the eventual uncertainty input from an approved EYA uncertainty budget.",
  "Run and validate a governed wind-AEP sidecar with a retained manifest."
]
```

`corrected_claim`:

> The repository contains an unattributed 10% Weibull A/k uncertainty knob in the canonical scenario and legacy wind-AEP code, but it is not the live finance-MC wind driver and the canonical wind-AEP adapter currently cannot consume the shared list-form MC schema. Treat the knob as ambiguous/dead until the wind and finance simulation configurations are separated, provenance is supplied, and an actual wind-AEP run manifest establishes what was used.

`limitations`:

> No canonical wind-AEP Monte Carlo was executed because the reproduced schema failure occurs before simulation. The approved source and value for the eventual Weibull uncertainty remain unresolved.

## P3-MCFX-06

- `title`: `Convergence metadata quantifies uncertainty but does not certify sufficiency`
- `disposition`: `partially_confirmed`
- `confidence`: `high`
- `verification_level`: `independent_reproduction`
- `status`: `open`

Retain current evidence refs and append the full `REF` path.

Replace `code_anchors` with:

- `analytics/mc/engine.py:975-999`
- `analytics/mc/convergence.py:20-38`
- `analytics/mc/convergence.py:59-133`
- `analytics/mc/convergence.py:178-218`

`reproduction_refs`:

- `REF:379-396`
- After separate persistence: `/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_Remediation_2026-08/reproductions/p3_convergence_metadata_probe.json`

`canon_impact`:

```json
{
  "level": "none",
  "direction": "none",
  "detail": "There is no deterministic or MC point-band impact. The finding concerns metadata and the strength of the audit's convergence assurance."
}
```

- `owner_role`: `model_validation_owner`

`remediation_dependency`:

```json
[
  "Approve precision gates by statistic and use case.",
  "Correct the DSCR breach count.",
  "Add acceptance tests against actual governed finance-MC runs."
]
```

`corrected_claim`:

> Every successful finance-MC run stores convergence and percentile-CI metadata keys; per-metric diagnostics populate when at least 30 finite trials exist. These diagnostics quantify approximate mean and percentile uncertainty for a reader to compare against separately declared tolerances. They do not themselves certify sufficiency, and the DSCR breach-probability subblock is wrong at commit `7e99f34`.

`limitations`:

> No evidence-based cross-sector benchmark was located for the audit’s “above typical practice” statement. Convergence-acceptance thresholds remain unauthored and unapproved.

## P3-EQ-01

- `title`: `Canonical report is value-destructive, but repository-wide equity-presentation assurances are false`
- `disposition`: `partially_confirmed`
- `confidence`: `high`
- `verification_level`: `independent_reproduction`
- `status`: `open`

Retain current evidence refs and append the full `REF` path.

Replace `code_anchors` with:

- `app/reports/report_model.py:944-1049`
- `app/reports/report_model.py:1117-1150`
- `app/reports/templates/report.html.j2:145-168`
- `config/report_defaults.yaml:31-42`
- `config/report_defaults.yaml:50-58`
- `api/pipeline_api.py:99-111`
- `api/pipeline_api.py:479-493`
- `analytics/executive_workbook.py:180-192`
- `api/sensitivity_api.py:34-120`
- `app/api/main.py:519-535`
- `analytics/dashboard/streamlit_app.py:34-40`
- `analytics/casper/casper_payload.py:307-342`

`reproduction_refs`:

- `REF:428-517`
- `REF:641-644`
- `REF:709-718`
- After separate persistence: `/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_Remediation_2026-08/reproductions/p3_equity_report_and_verdict_reproduction.json`

`canon_impact`:

```json
{
  "level": "confirmed",
  "direction": "kpi_neutral_report_narrative_correction_and_latent_verdict_guard",
  "detail": "The current canonical headline and KPI vector are correctly value-destructive. The canonical HTML nevertheless contains an unsupported FX-methodology statement, and the verdict architecture has a latent contradictory-result risk for a positive-equity-NPV and negative-equity-IRR payload."
}
```

- `owner_role`: `reporting_model_report_content_and_api_contract_owner`

`remediation_dependency`:

```json
[
  "Define the IRR/NPV consistency policy.",
  "Fail, downgrade, or explicitly qualify contradictory equity-return signals.",
  "Inventory decision surfaces separately from analytical sub-surfaces.",
  "Source every methodology statement from the actual run manifest."
]
```

`corrected_claim`:

> In the audited canonical case, the main HTML/PDF report, full finance API block, executive workbook, and IC red-flag logic co-locate the negative equity IRR with project IRR and correctly render the case as value-destructive. Repository-wide absence claims are not supportable: several intentionally single-metric analytics surfaces expose project IRR alone, the verdict can be contradictory on a positive-NPV/negative-IRR payload, and the generated risk register incorrectly states that canon was stressed to CBSL/IMF projections. Limit the positive assurance to enumerated, reproduced decision surfaces and correct the FX mitigation wording to the actual BIS-derived deterministic drift and authored uniform MC band.

`limitations`:

> The positive-NPV/negative-IRR probe is synthetic; it does not establish that the canonical engine currently emits that combination. Deployed front ends, cached reports, operational report copies, and external artefacts were not inspected. Final replacement wording for the unsupported CBSL/IMF statement requires report-content owner approval.

## P3-EQ-02

- `title`: `At least three operational logs omit equity IRR`
- `disposition`: `confirmed`
- `confidence`: `high`
- `verification_level`: `finder_refuter`
- `status`: `open`

Retain current evidence refs and append the full `REF` path.

Replace `code_anchors` with:

- `analytics/evaluate_scenario.py:120-128`
- `analytics/pipeline_v14_enhanced.py:976-981`
- `analytics/pipeline_v14_enhanced.py:1011-1016`
- `analytics/pipeline_analytics_v14.py:173-176`

`reproduction_refs`:

- `REF:550-556`
- After separate persistence: `/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_Remediation_2026-08/reproductions/p3_equity_operational_log_inventory.json`

`canon_impact`:

```json
{
  "level": "none",
  "direction": "none",
  "detail": "Calculations and lender artefacts are unaffected. Operational triage and copied log excerpts can present an incomplete return picture."
}
```

- `owner_role`: `observability_owner`

`remediation_dependency`:

```json
[
  "Provide one canonical KPI-summary formatter.",
  "Add tests that require project and equity return metrics to remain paired in operational summaries."
]
```

`corrected_claim`:

> At least three production operational log messages print project IRR and other KPIs while omitting equity IRR. The returned API/report objects retain equity IRR, and no lender-deliverable numerical impact was demonstrated. This is an observability-consistency gap, not currently a finance-output defect.

`limitations`:

> The search covered literal and multiline logger calls in the audited repository. Deployed log processors and externally copied log excerpts were not inspected.

## P3-EQ-03

- `title`: `The report contains a live IRR bridge; dated rebaseline provenance remains comment-only`
- `disposition`: `partially_confirmed`
- `confidence`: `high`
- `verification_level`: `independent_reproduction`
- `status`: `open`

Retain current evidence refs and append the full `REF` path.

Replace `code_anchors` with:

- `scenarios/dutchbay_lendercase_2025Q4.yaml:683-732`
- `app/reports/report_model.py:2253-2291`
- `app/api/main.py:322-359`
- `app/reports/capital_risk_emit.py:203-220`
- `analytics/irr_bridge.py:83-108`
- `analytics/irr_bridge.py:165-211`
- `app/reports/templates/report.html.j2:1092-1145`
- `config/report_defaults.yaml:50-58`

`reproduction_refs`:

- `REF:585-613`
- After separate persistence: `/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_Remediation_2026-08/reproductions/p3_equity_irr_bridge_reproduction.json`

`canon_impact`:

```json
{
  "level": "none",
  "direction": "none",
  "detail": "There is no KPI impact. The remaining issue concerns controlled attribution, provenance, and disclosure."
}
```

- `owner_role`: `financial_analysis_and_report_content_owner`

`remediation_dependency`:

```json
[
  "Create a structured rebaseline register.",
  "Retain pre-change and post-change run hashes.",
  "Approve an attribution method that treats ordering and interactions.",
  "Project the controlled attribution into the report.",
  "Classify drivers as renegotiable, intrinsic, mitigated, or residual."
]
```

`corrected_claim`:

> The generated report already explains the current project-to-equity gap through a reconciled leverage/cost-of-debt/tax-shield/residual bridge. What remains comment-only is the dated ten-step rebaseline provenance and an explicit renegotiable-versus-intrinsic classification. The sequential comment deltas are not a controlled causal decomposition; do not claim “roughly half” without one-factor reruns plus interaction treatment or another approved attribution method.

`limitations`:

> No controlled one-factor-plus-interaction attribution was executed. No owner decision has classified each driver as renegotiable, intrinsic, mitigated, or residual.

## Meta-count deltas

With `EVAL-10` added and all existing severities preserved:

`record_count` changes from `107` to `108`.

Replace `counts_by_source_phase` with:

```json
{
  "EVAL": 10,
  "P2": 29,
  "P3_COVENANTS": 8,
  "P3_EQUITY_DISCLOSURE": 3,
  "P3_MC_FX": 6,
  "P3_WIND": 7,
  "P4": 27,
  "P5": 18
}
```

Delta: `EVAL +1`; all other phase counts are unchanged.

Replace `counts_by_disposition` with:

```json
{
  "confirmed": 29,
  "deferred": 14,
  "not_a_defect": 4,
  "partially_confirmed": 51,
  "refuted": 10
}
```

Deltas:

- `confirmed +2`: `P3-MCFX-04`, `P3-EQ-02`
- `deferred -1`: `P3-MCFX-02`
- `not_a_defect -2`: `P3-MCFX-06`, `P3-EQ-01`
- `partially_confirmed +1` net
- `refuted +1`: new `EVAL-10`

Replace `counts_by_severity` with:

```json
{
  "critical": 5,
  "high": 33,
  "low": 31,
  "medium": 38,
  "none": 1
}
```

Delta: `high +1` for `EVAL-10`; existing severities are unchanged.

Replace `counts_by_status` with:

```json
{
  "closed": 5,
  "deferred": 14,
  "open": 71,
  "requires_correction": 18
}
```

Deltas:

- `closed -2`: `P3-MCFX-06`, `P3-EQ-01`
- `deferred -1`: `P3-MCFX-02`
- `open +3`: `P3-MCFX-02`, `P3-MCFX-06`, `P3-EQ-01`
- `requires_correction +1`: `EVAL-10`

Add this non-counting assurance block under `meta`:

```json
"p3_mc_reporting_assurance": {
  "refuter_artifact": "/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_Remediation_2026-08/refuters/04_P3_MC_REPORTING_REFUTER_CHECKPOINT.md",
  "refuter_sha256": "2e150dc6b1f949418236256057b3e291f80d7c466873d436a15db37523631685",
  "audited_commit": "7e99f34d75b9c3d44a5c5b260cedbe403d2f79e8",
  "claim_count": 10,
  "claim_ids": [
    "EVAL-10",
    "P3-MCFX-01",
    "P3-MCFX-02",
    "P3-MCFX-03",
    "P3-MCFX-04",
    "P3-MCFX-05",
    "P3-MCFX-06",
    "P3-EQ-01",
    "P3-EQ-02",
    "P3-EQ-03"
  ],
  "verdict_counts": {
    "CONFIRMED": 3,
    "PARTIALLY_CONFIRMED": 6,
    "REFUTED": 1
  },
  "boundary": "The 256-trial FX comparison is illustrative; no production-scale finance-MC run or transaction-approved acceptance policy was evidenced."
}
```

The three confirmed claims are `P3-MCFX-03`, `P3-MCFX-04`, and `P3-EQ-02`; the refuted claim is `EVAL-10`.

Remove the repeated stale per-record limitation saying that, except for MCFX-03, these records were not independently refuted. It is now false for every record in this family.

Add this top-level limitation:

> P3-MCFX-01 through P3-MCFX-06, P3-EQ-01 through P3-EQ-03, and EVAL-10 received a documented independent refuter pass against commit `7e99f34`. The 256-trial FX comparison is illustrative, no production-scale finance-MC pack was evidenced, and transaction-policy choices remain unresolved. Narrative command/output evidence is preserved in refuter checkpoint 04; machine-readable reproduction artefacts remain a release dependency until separately persisted and hashed.

## Corrigendum patch map

### Replace COR-15

The current `COR-15` is too weak and contains a refuted sentence: “The fuller causal re-baseline chain remains absent from the generated report.” A live project-to-equity bridge is already rendered.

Keep ID `COR-15` and replace its superseded anchors with:

- `AUDIT/03_bankability_methodology.md:20,27,83,91`
- `AUDIT/raw/P3_d_equity_irr_and_synthesis.json:2,5`
- `AUDIT/99_SYNTHESIS_final_audit.md:11,27`

Use `P3-EQ-01.corrected_claim` above verbatim as the replacement wording.

Its controlling boundary should state:

> Canon’s current KPI vector and headline remain correctly value-destructive. The contradictory-verdict probe is synthetic and does not show that canon emits that payload. Deployed or cached report copies were not examined. The unsupported CBSL/IMF statement is present in the reproduced canonical HTML and requires correction.

### Add COR-17 through COR-25

Use one dolphin-sized correction row per distinct claim; do not combine independent methodology defects.

| Corrigendum ID | Register record | Superseded audit anchors | Replacement wording |
|---|---|---|---|
| `COR-17` | `EVAL-10` | `AUDIT/03_bankability_methodology.md:72,76-77`; `AUDIT/raw/P3_c_mc_fx_rigor.json:3-4,8`; `AUDIT/99_SYNTHESIS_final_audit.md:76-77` | Use `EVAL-10.corrected_claim` verbatim. |
| `COR-18` | `P3-MCFX-01` | `AUDIT/03_bankability_methodology.md:19,27,38,72,75`; `AUDIT/raw/P3_c_mc_fx_rigor.json:2`; `AUDIT/99_SYNTHESIS_final_audit.md:11,40,60,123` | Use `P3-MCFX-01.corrected_claim` verbatim. |
| `COR-19` | `P3-MCFX-02` | `AUDIT/03_bankability_methodology.md:72,76`; `AUDIT/raw/P3_c_mc_fx_rigor.json:3,8`; `AUDIT/99_SYNTHESIS_final_audit.md:76` | Use `P3-MCFX-02.corrected_claim` verbatim. |
| `COR-20` | `P3-MCFX-03` | `AUDIT/03_bankability_methodology.md:77`; `AUDIT/raw/P3_c_mc_fx_rigor.json:4`; `AUDIT/99_SYNTHESIS_final_audit.md:77` | Use `P3-MCFX-03.corrected_claim` verbatim. |
| `COR-21` | `P3-MCFX-04` | `AUDIT/03_bankability_methodology.md:78`; `AUDIT/raw/P3_c_mc_fx_rigor.json:5`; `AUDIT/99_SYNTHESIS_final_audit.md:84` | Use `P3-MCFX-04.corrected_claim` verbatim. |
| `COR-22` | `P3-MCFX-05` | `AUDIT/03_bankability_methodology.md:79`; `AUDIT/raw/P3_c_mc_fx_rigor.json:6`; `AUDIT/99_SYNTHESIS_final_audit.md:84` | Use `P3-MCFX-05.corrected_claim` verbatim. |
| `COR-23` | `P3-MCFX-06` | `AUDIT/03_bankability_methodology.md:19,27,72`; `AUDIT/raw/P3_c_mc_fx_rigor.json:1,7-8` | Use `P3-MCFX-06.corrected_claim` verbatim. |
| `COR-24` | `P3-EQ-02` | `AUDIT/03_bankability_methodology.md:85`; `AUDIT/raw/P3_d_equity_irr_and_synthesis.json:3`; `AUDIT/99_SYNTHESIS_final_audit.md:88` | Use `P3-EQ-02.corrected_claim` verbatim. |
| `COR-25` | `P3-EQ-03` | `AUDIT/03_bankability_methodology.md:85`; `AUDIT/raw/P3_d_equity_irr_and_synthesis.json:4`; `AUDIT/99_SYNTHESIS_final_audit.md:27,84` | Use `P3-EQ-03.corrected_claim` verbatim. |

Controlling boundaries:

- `COR-17`: no executed production finance-MC pack; trial count alone does not establish convergence.
- `COR-18`: 256 trials are illustrative; activation is not authorized.
- `COR-19`: risk inclusion and treatment are transaction-policy decisions.
- `COR-20`: observed 12.5 and 12.890625 percentage-point effects are seed/sample-specific.
- `COR-21`: no live production artefact quantified the two definitions’ operational difference.
- `COR-22`: the wind adapter fails before simulation; no executed A/k impact may be claimed.
- `COR-23`: metadata exists but no acceptance policy or sector benchmark was evidenced.
- `COR-24`: calculations and lender artefacts retain equity IRR; this is an operational-log gap.
- `COR-25`: the current-state IRR bridge exists, but the dated rebaseline sequence is not a controlled causal decomposition.

### Amend existing cross-cutting rows

- `COR-02`: state that later documented independent-refuter treatment now covers `EVAL-10`, `P3-MCFX-01` through `P3-MCFX-06`, and `P3-EQ-01` through `P3-EQ-03`; do not generalize this assurance to other P3 or P4 claims.
- `COR-14`: add `EVAL-10`, `P3-MCFX-04`, and `P3-MCFX-06` to controlling evidence. The refuter independently undermines the original “above typical practice,” CVaR-consistency, and convergence-sufficiency language.
- `COR-16`: add `P3-MCFX-01` and `P3-MCFX-05` to the boundary. Enabling `fx_calibrated` is syntactically small but not an adequate model-risk remedy; the wind knob is not activated by the finance path and its sidecar integration currently fails.

### Update release dependencies

Replace the future-tense statement that residual P3 claims still require a refuter with:

> The Critical/High P3 Monte Carlo/FX and bounded reporting-surface claims received a documented independent refuter pass in `REMED/refuters/04_P3_MC_REPORTING_REFUTER_CHECKPOINT.md`. Before issue, its corrected dispositions must be reconciled into the final findings register, each material scratch reproduction must be persisted in machine-readable form with hashes and run metadata, and the corresponding corrigendum rows must pass independent review.

### Update controlled evidence set

Add:

- `REMED/refuters/04_P3_MC_REPORTING_REFUTER_CHECKPOINT.md`
- The ten reproduction JSON files listed below
- The new MCFX-02 primary-source-register rows
- The refreshed `REMED/CHECKPOINT_MANIFEST.sha256`

After the edits, bump the corrigendum draft document ID from `v0.1` to at least `v0.2`, retain `HOLD`, and recompute the corrigendum and checkpoint-manifest hashes.

## Evidence persistence requirements

The narrative checkpoint is already durable and appears in `CHECKPOINT_MANIFEST.sha256`. The following reproductions are not yet separate machine-readable artefacts and must not be represented as existing standalone files until created:

1. `/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_Remediation_2026-08/reproductions/p3_mc_trial_routing_reproduction.json`
2. `/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_Remediation_2026-08/reproductions/p3_fx_calibration_seed42_n256_reproduction.json`
3. `/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_Remediation_2026-08/reproductions/p3_mc_parameter_inventory.json`
4. `/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_Remediation_2026-08/reproductions/p3_dscr_breach_ci_seed42_reproduction.json`
5. `/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_Remediation_2026-08/reproductions/p3_var_cvar_definition_vectors.json`
6. `/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_Remediation_2026-08/reproductions/p3_wind_mc_schema_probe.json`
7. `/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_Remediation_2026-08/reproductions/p3_convergence_metadata_probe.json`
8. `/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_Remediation_2026-08/reproductions/p3_equity_report_and_verdict_reproduction.json`
9. `/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_Remediation_2026-08/reproductions/p3_equity_operational_log_inventory.json`
10. `/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_Remediation_2026-08/reproductions/p3_equity_irr_bridge_reproduction.json`

Each JSON file must record, at minimum:

- Audited commit and worktree
- Exact interpreter and dependency environment
- Exact command or embedded probe source
- Configuration path and configuration hash
- Seed and trial count where applicable
- Raw numeric outputs at full precision
- Failure count and toy-fallback count
- Timestamp and timezone
- Explicit limitations
- File SHA-256 in the controlled manifest

`P3-MCFX-02` also requires three new claim-level primary-source rows. The current register ended at `PSR-0022` at patch-map cutoff; re-check immediately before allocation, then use the next available IDs for:

- IFC guidance on capex, opex, energy-production, interest-rate sensitivity, stress/scenario results, and financing-cost sensitivity.
- WBG PPP Handbook guidance on the comprehensive risk universe and qualitative and/or quantitative treatment of significant risks.
- World Bank Sri Lanka PAD precedent for Monte Carlo including capex overrun/construction delay and separate treatment of CEB payment risk.

The source PDFs and conversions are already archived and hashed; the missing control is the claim-level PSR mapping for these passages.

Until those ten reproduction files and three PSR rows exist, the safe immediate register reference is the relevant line range in `REF`, with the limitation that the result is preserved as a narrative checkpoint rather than a standalone machine-readable run artefact.

## Post-application QA

After applying this map to the controlled drafts:

1. Parse the findings register as JSON.
2. Confirm exactly 108 unique finding IDs.
3. Recompute all source-phase, disposition, severity, and status counts from records rather than hand-editing totals.
4. Confirm the ten P3 refuter records resolve to the disposition counts `3 confirmed`, `6 partially_confirmed`, and `1 refuted`.
5. Confirm every absolute evidence path exists.
6. Confirm every source-register ID resolves.
7. Run `scripts/validate_controlled_registers.py` from the remediation workspace using an available Python 3.11 environment.
8. Re-hash the findings register, corrigendum, reproduction files, source-register successors, and checkpoint manifest.
9. Perform a second clean read-only review against the immutable audit.
10. Keep the corrigendum on `HOLD` until all machine-readable evidence and transaction-policy dependencies close.

## Integrity footer

The hash below covers all UTF-8 file bytes before the `## Integrity footer` heading. It is deliberately scoped this way because a file cannot contain its own final SHA-256 without changing the value being hashed. The actual full-file SHA-256 is reported alongside the handoff and must be placed in the external controlled manifest.

Payload SHA-256: `1740004d861f404a6ba8c5727ee28d0f87e0b90da95046e5bf050f20e256bf7f`

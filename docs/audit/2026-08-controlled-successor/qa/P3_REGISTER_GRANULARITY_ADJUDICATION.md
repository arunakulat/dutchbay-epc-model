# DutchBay P3 Findings-Register Granularity Adjudication

**Document ID:** `DB-AUD-REMED-QA-P3-GRANULARITY-2026-08-12`
**Date:** 2026-08-12 (Asia/Colombo)
**Posture:** Independent, read-only adjudication. This memorandum changes no register, script, repository file, or prior QA/refuter artefact.
**Repository basis:** `arunakulat/dutchbay-epc-model@7e99f34d75b9c3d44a5c5b260cedbe403d2f79e8`
**Release posture:** `HOLD`; this is an exact implementation decision, not circulation approval.

## Evidence basis

| Artefact | SHA-256 |
|---|---|
| `refuters/04_P3_MC_REPORTING_REFUTER_CHECKPOINT.md` | `2e150dc6b1f949418236256057b3e291f80d7c466873d436a15db37523631685` |
| `refuters/05_P3_MC_REPORTING_REGISTER_PATCH_MAP.md` | `908555c86bd3c0c672e2ea17c1549731fce67b74a14de3b8765da0553696ba50` |
| `qa/CONTROLLED_REGISTERS_EXACT_PATCH_MAP.md` | `979d2e42076f7ae3a7e09805e9258b47ae6437b7d17324b93297db6e20655787` |
| `registers/findings_register.draft.json` baseline | `b64c8e4430ea9febd58226c4a8a039fb2001fbce5979e433631c53216c3864f8` |

## Adjudication

Adopt **four atomic P3 rows**, using IDs `P3-MCFX-07`, `P3-MCFX-08`, `P3-EQ-04`, and `P3-EQ-05`. Do **not** create a counted `EVAL-10` finding.

The single-`EVAL-10` proposal correctly identifies the false 100,000-trial finance-Monte-Carlo assertion, but it does not give separate machine-readable identity to three additional independently reproduced defects:

1. the wind-AEP adapter/list-schema incompatibility;
2. the current canonical report's false CBSL/IMF FX-source attribution; and
3. the latent positive-equity-NPV/negative-equity-IRR verdict contradiction.

Those three defects have distinct code anchors, owners, remediation actions, tests, and canon-impact boundaries. Keeping them embedded in `P3-MCFX-05` and `P3-EQ-01` would make closure non-auditable: one sub-defect could be fixed while the compound row remained partly open for an unrelated reason.

Creating both `EVAL-10` and `P3-MCFX-07` is also rejected. They would adjudicate the same superseded 100,000-trial assertion from the same evidence and require the same run-configuration/manifest remedy. That would inflate the finding and severity populations without adding a separately actionable proposition. The audit-level correction should point to `P3-MCFX-07` through the corrigendum and non-counting assurance metadata.

The controlled population therefore remains `EVAL=9`; the new claims are attributed to the P3 lenses that generated and refuted them.

## Applied granularity controls

A counted finding is atomic only if all five tests below are met:

1. **Single proposition:** one independently true, false, or partly true assertion can be adjudicated without relying on the state of another assertion.
2. **Single remediation boundary:** the row can be closed by one coherent implementation, validation, disclosure, or policy decision.
3. **Single owner boundary:** one accountable owner or tightly coupled owner pair can accept the remediation.
4. **Single canon-impact boundary:** current deterministic, current narrative, optional-path, and latent architecture impacts are not blended.
5. **No duplicate count:** the same defect may be cross-referenced elsewhere for context, but only one row owns its disposition, severity, status, canon impact, and blocking dependency.

Under these controls:

- `P3-MCFX-03` owns the tolerance-aware DSCR breach-comparator defect.
- `P3-MCFX-06` owns only the convergence-metadata/sufficiency-assurance boundary; it may cross-reference `P3-MCFX-03` but must not count or remediate that comparator again.
- `P3-MCFX-05` owns only provenance and activation ambiguity for the 10% Weibull uncertainty knob.
- `P3-MCFX-08` owns the list-schema wind-AEP adapter failure.
- `P3-EQ-01` owns only the bounded positive assurance and the refutation of repository-wide surface assertions.
- `P3-EQ-04` owns the false CBSL/IMF report statement.
- `P3-EQ-05` owns the contradictory-verdict logic.
- `P3-MCFX-07` alone owns the refuted 100,000-trial finance-MC assertion; no counted `EVAL-10` duplicate is permitted.

## Exact affected-row outcomes

All rows below use `confidence=high`. Verification levels are included because they are part of the closure logic, although this adjudication does not replace the separate reproduction-registry controls.

### Existing P3 MC/FX rows

#### `P3-MCFX-01`

- **Title:** `Canon omits calibrated FX; available calibration is a one-year spot mixture`
- **Severity:** `high` (from `critical`)
- **Disposition:** `partially_confirmed`
- **Status:** `open`
- **Verification:** `independent_reproduction`
- **Corrected claim:** No committed scenario activates the available BIS-history-calibrated FX path; canonical finance MC uses a symmetric uniform `[300,367]` spot band. The available feature is a one-year two-regime spot mixture followed by constant drift, not a full 20-year regime/path model. A seed-matched 256-trial reproduction shows wider and more skewed FX-sensitive tails, but it is illustrative rather than production validation. Its source vintage, horizon, tail, truncation, and transaction use require approval before activation.

The severity is `high`, not `critical`: no deterministic canonical KPI changes and no governed lender-scale MC result exists. The row remains material to lender tail-risk evidence, but the refuter narrowed the claim and impact.

#### `P3-MCFX-02`

- **Title:** `Canon samples six finance-MC drivers; wider risk treatment is transaction-specific`
- **Severity:** `high`
- **Disposition:** `partially_confirmed`
- **Status:** `deferred`
- **Verification:** `source_and_code_refuter`
- **Corrected claim:** Canonical finance MC jointly samples six operating/economic drivers and omits interest-rate/refinancing, construction-delay, tax-change, and offtaker-credit events from that joint distribution. Official guidance supports identification and appropriate treatment of all material risks, but does not require every material risk to be a Monte Carlo dimension. The approved risk register must state whether each material risk is treated by MC, deterministic stress, event tree, contract/mitigation, or qualitative analysis, together with residual risk.

`deferred` is the correct status because distribution choice, correlation, event frequency, recovery, and treatment method are transaction-policy decisions not authorized by the refuter. The disposition nevertheless changes from `deferred` to `partially_confirmed` because the six-driver population and named omissions are now evidenced.

#### `P3-MCFX-03`

- **Title:** `DSCR breach-probability diagnostic bypasses the tolerance-aware covenant comparator`
- **Severity:** `high`
- **Disposition:** `confirmed`
- **Status:** `open`
- **Verification:** `independent_reproduction`
- **Corrected claim:** `percentile_ci_diagnostic` uses a bare `< floor` count for the DSCR breach-probability point estimate and Wilson interval instead of the shared tolerance-aware covenant primitive. Seed-42 reproductions overstate the point estimate by 12.5 percentage points at 64 and 128 trials and by 12.890625 percentage points at 256 trials. Those magnitudes are sample-specific; the production impact must be recalculated on the eventual governed run. Other percentile intervals are not invalidated by this defect.

This row exclusively owns the breach-count implementation and regression remedy.

#### `P3-MCFX-04`

- **Title:** `VaR/ES definitions diverge and lean CASPER blocks omit CVaR while other surfaces expose it`
- **Severity:** `medium`
- **Disposition:** `confirmed`
- **Status:** `open`
- **Verification:** `independent_reproduction`
- **Corrected claim:** The finance-MC engine and capital-risk layer maintain different VaR/ES definitions and disagree on deterministic test vectors. Lean CASPER `monte_carlo` and `mc_risk` blocks omit CVaR, while async-analysis and opt-in capital-risk surfaces expose one of the definitions. The repository therefore needs one approved quantile/ES convention, golden vectors, and an explicit serializer contract; the evidence does not support a claim that CVaR is absent from every external surface.

#### `P3-MCFX-05`

- **Title:** `The 10% Weibull uncertainty knob lacks a claim-level derivation and is not the live finance-MC driver`
- **Severity:** `medium`
- **Disposition:** `partially_confirmed`
- **Status:** `open`
- **Verification:** `source_and_code_refuter`
- **Corrected claim:** The canonical scenario and legacy wind-AEP code contain an unattributed 10% Weibull A/k uncertainty setting that is not reconciled to an approved energy-yield uncertainty budget. It is not the live finance-MC wind driver, and no executed canonical A/k-band impact was evidenced. The value remains ambiguous until its provenance, intended consumer, and governed wind-AEP use are approved.

The adapter/list-schema failure is deliberately excluded from this row and belongs only to `P3-MCFX-08`.

#### `P3-MCFX-06`

- **Title:** `Convergence metadata quantifies uncertainty but does not certify sufficiency`
- **Severity:** `low`
- **Disposition:** `partially_confirmed`
- **Status:** `requires_correction`
- **Verification:** `independent_reproduction`
- **Corrected claim:** Successful finance-MC runs attach convergence and percentile-CI metadata, with per-metric diagnostics populated when at least 30 finite trials exist. The diagnostics quantify approximate sampling uncertainty for comparison with separately declared tolerances; they do not themselves certify convergence, sample sufficiency, lender fitness, or “above typical practice.” No governed acceptance thresholds or evidence-based cross-sector benchmark were found at the audited commit.

The DSCR breach-comparator defect is not part of this row's counted claim or remediation. It is owned by `P3-MCFX-03` and may appear here only as a typed cross-finding reference. `requires_correction` applies to the audit's unsupported sufficiency/benchmark assurance, not to a duplicated comparator defect.

### Existing P3 equity/disclosure rows

#### `P3-EQ-01`

- **Title:** `Named canonical decision surfaces are value-destructive, but repository-wide equity-presentation assurance is unsupported`
- **Severity:** `medium` (from `low`)
- **Disposition:** `partially_confirmed`
- **Status:** `requires_correction`
- **Verification:** `independent_reproduction`
- **Corrected claim:** In the reproduced canonical case, the main HTML/PDF report, full-finance API block, executive workbook, and IC red-flag logic co-locate the negative equity IRR with project IRR and correctly render the case as value-destructive. That positive assurance must be limited to the named reproduced decision surfaces. Several intentionally single-metric analytical sub-surfaces expose project IRR alone, so the audit's repository-wide “every surface” and “no code path” formulations are not supportable.

The CBSL/IMF source misstatement and the contradictory-verdict path are deliberately excluded from this umbrella assurance row. They belong only to `P3-EQ-04` and `P3-EQ-05` respectively. `requires_correction` applies to the audit's blanket assurance wording.

#### `P3-EQ-02`

- **Title:** `At least three operational logs omit equity IRR`
- **Severity:** `low`
- **Disposition:** `confirmed`
- **Status:** `open`
- **Verification:** `independent_code_refuter`
- **Corrected claim:** At least three production information-log messages print project IRR and other KPIs while omitting equity IRR. Returned API/report objects retain equity IRR and no lender-deliverable numerical impact was demonstrated. This is an operational-observability consistency gap, not a finance-output defect.

#### `P3-EQ-03`

- **Title:** `The report contains a live IRR bridge; dated rebaseline provenance remains comment-only`
- **Severity:** `medium`
- **Disposition:** `partially_confirmed`
- **Status:** `open`
- **Verification:** `independent_reproduction`
- **Corrected claim:** The generated report already explains the current project-to-equity gap through a reconciled leverage, cost-of-debt, tax-shield, and residual bridge. The dated ten-step rebaseline history and a controlled renegotiable-versus-intrinsic classification remain comment-only. Sequential comment deltas are not a causal decomposition; do not claim “roughly half” without approved one-factor reruns plus interaction treatment or another controlled attribution method.

## Exact new atomic rows

### `P3-MCFX-07`

- **Title:** `Claimed canonical 100,000-trial finance-MC run is not evidenced`
- **Source phase:** `P3_MC_FX`
- **Severity:** `high`
- **Disposition:** `refuted`
- **Status:** `requires_correction`
- **Confidence:** `high`
- **Verification:** `source_and_code_refuter`
- **Corrected claim:** The audit's assertion of a canonical 100,000-trial finance-Monte-Carlo run is refuted. The scenario's `n_scenarios: 100000` value belongs to the legacy wind-AEP path. Finance callers currently request 1,000 to 20,000 trials by default or policy, and no executed 100,000-trial finance pack was found. Statistical sufficiency requires declared mean, percentile, breach-probability, and ES/CVaR precision tolerances plus an actual effective-`n_trials` run manifest; trial count alone is not a certificate.
- **Canon-impact boundary:** No deterministic KPI impact. The audit's stochastic-evidence characterization is invalid; intended lender-run MC bands remain unestablished.
- **Action boundary:** Governed finance-MC configuration, declared precision tolerances, actual run manifest, and retained independently reviewed risk pack.

`refuted` applies to the superseded audit assertion, not to the truth of the corrected sentence. The schema or register README should preserve that disposition convention explicitly.

### `P3-MCFX-08`

- **Title:** `Wind-AEP adapter cannot consume the canonical list-form MC parameter schema`
- **Source phase:** `P3_MC_FX`
- **Severity:** `high`
- **Disposition:** `confirmed`
- **Status:** `open`
- **Confidence:** `high`
- **Verification:** `independent_reproduction`
- **Corrected claim:** The wind-AEP adapter expects `monte_carlo.parameters` to be a mapping, while the canonical finance-MC configuration correctly supplies a list. Exercising the adapter with the canonical scenario fails before wind-AEP simulation with `AttributeError: 'list' object has no attribute 'get'`; consequently no canonical 100,000-scenario wind sidecar was evidenced.
- **Canon-impact boundary:** Deterministic finance KPIs are unchanged; the current optional wind-AEP execution path is broken.
- **Action boundary:** Separate wind-AEP and finance-MC schemas, add a canonical-config adapter regression, and emit a governed wind-AEP run manifest.

### `P3-EQ-04`

- **Title:** `Canonical report falsely attributes FX stress to CBSL/IMF projections`
- **Source phase:** `P3_EQUITY_DISCLOSURE`
- **Severity:** `high`
- **Disposition:** `confirmed`
- **Status:** `requires_correction`
- **Confidence:** `high`
- **Verification:** `independent_reproduction`
- **Corrected claim:** The reproduced canonical report states that the FX path was stressed to CBSL/IMF projections, but the governed inputs use BIS-history-derived deterministic depreciation and an authored uniform finance-MC spot band; no IMF projection input used by canon was found. The current lender-facing methodology statement is unsupported and misattributed.
- **Canon-impact boundary:** No numerical KPI impact; the current canonical lender narrative is false and requires correction.
- **Action boundary:** Generate methodology wording from the governed run manifest, replace the static default, and add a report test that reconciles source/method wording to actual inputs.

### `P3-EQ-05`

- **Title:** `Positive equity NPV can yield a Bankable headline despite negative equity IRR`
- **Source phase:** `P3_EQUITY_DISCLOSURE`
- **Severity:** `medium`
- **Disposition:** `confirmed`
- **Status:** `open`
- **Confidence:** `high`
- **Verification:** `independent_reproduction`
- **Corrected claim:** A type-valid synthetic payload with positive equity NPV and negative equity IRR produces a `Bankable at the modeled assumptions` headline together with a negative-equity-IRR note. This confirms a latent verdict-consistency defect, not a defect in the current canonical output, whose headline remains correctly value-destructive.
- **Canon-impact boundary:** Potential/latent reporting impact only; current canonical KPIs and headline are unchanged.
- **Action boundary:** Approve an IRR/NPV consistency policy, fail or downgrade contradictory return signals, and add contradictory-payload regressions.

## Count reconciliation

### Baseline

The baseline register contains 107 rows:

- phase: `EVAL 9`, `P2 29`, `P3_COVENANTS 8`, `P3_EQUITY_DISCLOSURE 3`, `P3_MC_FX 6`, `P3_WIND 7`, `P4 27`, `P5 18`;
- disposition: `confirmed 27`, `deferred 15`, `not_a_defect 6`, `partially_confirmed 50`, `refuted 9`;
- status: `closed 7`, `deferred 15`, `open 68`, `requires_correction 17`; and
- severity: `critical 5`, `high 32`, `low 31`, `medium 38`, `none 1`.

### P3-granularity dolphin only

After the nine existing-row corrections above and four atomic additions, but before changing `P4-DC-5`, the register must contain exactly **111 unique findings**:

```json
{
  "record_count": 111,
  "counts_by_source_phase": {
    "EVAL": 9,
    "P2": 29,
    "P3_COVENANTS": 8,
    "P3_EQUITY_DISCLOSURE": 5,
    "P3_MC_FX": 8,
    "P3_WIND": 7,
    "P4": 27,
    "P5": 18
  },
  "counts_by_disposition": {
    "confirmed": 32,
    "deferred": 14,
    "not_a_defect": 4,
    "partially_confirmed": 51,
    "refuted": 10
  },
  "counts_by_status": {
    "closed": 5,
    "deferred": 15,
    "open": 70,
    "requires_correction": 21
  },
  "counts_by_severity": {
    "critical": 4,
    "high": 36,
    "low": 30,
    "medium": 40,
    "none": 1
  }
}
```

The 13-row P3 MC/FX/equity refuter population then contains:

- dispositions: `confirmed 6`, `partially_confirmed 6`, `refuted 1`;
- statuses: `open 8`, `requires_correction 4`, `deferred 1`; and
- severities: `high 6`, `medium 5`, `low 2`, `critical 0`.

The single refuted row is `P3-MCFX-07`; the six confirmed rows are `P3-MCFX-03`, `P3-MCFX-04`, `P3-EQ-02`, `P3-MCFX-08`, `P3-EQ-04`, and `P3-EQ-05`.

### Final target after the independently required B9 closure repair

If `P4-DC-5` is also conservatively changed from `not_a_defect/closed` to `deferred/deferred`, as required by the separate closure adjudication, the **record count, phase counts, and severity counts do not change**. The final controlled totals become:

```json
{
  "record_count": 111,
  "counts_by_source_phase": {
    "EVAL": 9,
    "P2": 29,
    "P3_COVENANTS": 8,
    "P3_EQUITY_DISCLOSURE": 5,
    "P3_MC_FX": 8,
    "P3_WIND": 7,
    "P4": 27,
    "P5": 18
  },
  "counts_by_disposition": {
    "confirmed": 32,
    "deferred": 15,
    "not_a_defect": 3,
    "partially_confirmed": 51,
    "refuted": 10
  },
  "counts_by_status": {
    "closed": 4,
    "deferred": 16,
    "open": 70,
    "requires_correction": 21
  },
  "counts_by_severity": {
    "critical": 4,
    "high": 36,
    "low": 30,
    "medium": 40,
    "none": 1
  }
}
```

These totals reconcile arithmetically to 111 in every dimension. Metadata must be recomputed from records; the validator must reject hand-authored totals that do not equal the row population.

## Exact exclusions and cross-reference rules

1. Do not add `EVAL-10` as a finding. Replace every proposed counted `EVAL-10` reference with `P3-MCFX-07`. Audit-level corrigendum and assurance metadata may reference that P3 row without creating a duplicate finding.
2. Remove adapter-failure wording, canon impact, and implementation dependencies from `P3-MCFX-05`; link `P3-MCFX-08` as a non-counting cross-finding relation if useful.
3. Remove CBSL/IMF and contradictory-verdict wording, canon impact, and implementation dependencies from `P3-EQ-01`; link `P3-EQ-04` and `P3-EQ-05` as non-counting cross-finding relations.
4. Remove breach-comparator remediation from `P3-MCFX-06`; link `P3-MCFX-03` as a non-counting cross-finding relation. `P3-MCFX-06` retains only the unsupported convergence-sufficiency/benchmark assurance correction.
5. Contextual references to the absent 100,000-trial finance run may remain in limitations for sample-specific reproductions, but only `P3-MCFX-07` owns the refuted disposition and run-manifest dependency.
6. A reproduction artefact may support multiple findings, but linking one artefact to several rows must not merge their owner, action, status, or canon-impact fields.

## Implementation and validator acceptance criteria

The register-ingress dolphin is acceptable only when all of the following hold:

1. Exactly the four new IDs exist and `EVAL-10` does not exist.
2. All 13 P3 rows match the exact severity/disposition/status matrix in this memorandum.
3. Each corrected claim observes the exclusions above; no compound defect is left embedded in an umbrella row.
4. `P3-MCFX-07` clearly states that `refuted` adjudicates the superseded audit assertion.
5. Every `independent_reproduction` row resolves to a completed, hashed reproduction record linked to that same finding; until then the register remains `HOLD` even if its counts are structurally correct.
6. `P3-MCFX-02` resolves to exact claim-level primary-source records and retains transaction-policy limitations.
7. The 111 IDs are unique and every phase/disposition/status/severity count is recomputed from rows.
8. The P3-only count checkpoint and the final post-B9 count checkpoint both reconcile exactly as stated above.
9. Corrigendum rows are one-to-one with these atomic propositions and use `P3-MCFX-07` rather than a duplicate `EVAL-10`.
10. A second independent semantic QA pass confirms the same atomic boundaries before the corrigendum leaves `HOLD`.

## Confidence and limitation

**Assessment:** Ready to implement as a controlled register/schema patch, but not ready for external circulation.
**Confidence:** High. The four-way split follows directly from separately reproduced propositions and produces internally reconciled counts.
**Limitation:** This adjudication addresses register granularity and control semantics only. It does not certify the underlying standalone reproduction files as complete, approve transaction-risk policy, authorize code changes, or release the corrigendum/Board synthesis.

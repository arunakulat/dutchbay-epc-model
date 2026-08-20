# DutchBay Comprehensive Audit 2026-08 — Corrigendum v1.0.1

**Document ID:** `DB-AUD-COR-2026-08-16-v1.0.1`
**Applies to:** received audit directory `DutchBay_Comprehensive_Audit_2026-08`
**Audited repository commit:** `7e99f34d75b9c3d44a5c5b260cedbe403d2f79e8`
**Evidence cutoff:** `2026-08-16T12:37:25+05:30`
**Status:** **CONTROLLED DRAFT — RELEASE HOLD**
**Original audit treatment:** immutable; no received file has been altered
**Predecessor:** `02_AUDIT_CORRIGENDUM_v1.0.0_2026-08-16.md`, SHA-256 `827ab4aeea57cc28c29facdbd104bcdb9cc9eddbcbe3e46723aa5cb53bbd029b`; preserved unchanged

## v1.0.1 revision delta

This additive successor makes three control-only changes. It states the exact ten-pointer P5 crosswalk outcome, updates the active validation artefact to the post-PR-#1031 controlled state, and clarifies that a new versioned manifest is required at each later controlled save boundary. It does not change any project KPI, finding disposition, severity, transaction assumption, or the release HOLD.

## Effect of this corrigendum

This document withdraws or narrows the statements listed below. Where the received audit conflicts with this corrigendum, the corrected statement controls for subsequent remediation work. The original audit remains preserved as historical evidence and must be distributed, if at all, together with the final approved successor of this corrigendum.

This corrigendum is not a lender reliance letter, transaction approval, independent engineer opinion, credit decision, or assertion that all audit findings have been remediated. The Board/lender synthesis must not be regenerated or circulated until the stated release gates close.

## Corrections to audit controls and population statements

### COR-01 — Overall score semantics

The audit's `3/10` overall bankability conclusion is retained only as a judgmental credit conclusion. It is not the arithmetic mean of the four displayed sub-scores.

- The four displayed sub-scores have a simple mean of `4.5/10`.
- The `2/10 arithmetic average` label is false and withdrawn.
- Neither `3/10` nor `4.5/10` is a model KPI; this correction changes no project economics.

### COR-02 — P2 candidate and verdict arithmetic

The statement that P2 contains 25 total candidates is withdrawn.

- The six immutable P2 finder files contain `29` unique candidates.
- The six immutable refuter files contain `14 confirmed`, `11 partially confirmed`, `1 refuted`, and `3 not-a-defect-by-design` verdicts.
- The audit's 25-row ranked table is the live subset. Four additional rows are separately closed, producing the complete population of 29.
- Individual P2 dispositions are not changed merely by correcting the population arithmetic.

### COR-03 — Architecture pointer count and examination coverage

The architecture map contains `72`, not 70, unique `RS-*` pointers:

- family A: 15;
- family B: 9;
- family C: 12;
- family D: 12;
- family E: 13; and
- family F: 11.

All percentages or coverage statements based on 70 are invalid. Registration must not be confused with examination: at this cutoff, 21 pointers have a substantive disposition and `51 of 72 (70.8%)` remain `not_examined`. Four of the 25 explicit overlay records—`RS-B9`, `RS-D12`, `RS-E13`, and `RS-F10`—also remain `not_examined`.

P5's assigned ten-pointer crosswalk is not complete examination or closure. Its exact controlled disposition is `1 confirmed`, `5 deferred`, and `4 not_examined`. Any statement that P5 completed all ten assigned pointers is withdrawn.

### COR-04 — Assurance method by phase

The received pack did not apply a uniform independent finder/refuter method across all phases.

- P1 used parallel readers and synthesis.
- P2 used explicit finder/refuter pairs.
- P3, P4, and P5 used sequential specialist lenses in the received edition.
- Later remediation refuters improve assurance only for the exact claims they reviewed; they do not retroactively transform an entire phase into a two-pass independent audit.

Phase names, agent counts, or role labels do not substitute for claim-level evidence, retained reproductions, or an identified refuter.

### COR-05 — Scenario and artefact counting rule

At commit `7e99f34`, the tracked `scenarios/` tree contains:

- `29` top-level YAML artefacts;
- `5` top-level JSON artefacts; and
- `39` YAML or JSON artefacts across the complete nested tree.

These are artefact counts, not counts of runnable production scenarios. The set includes examples, tests, overrides, invalid/scratch fixtures, frozen outputs, and a multi-document YAML stream. Structured JSON agent returns are evidence records, not raw conversational transcripts.

### COR-06 — Stale P6 status

Any final-run statement that P6 `remained` is a stale pre-closure checkpoint. It must be labeled historical/superseded wherever the pack also records P6 completion. The stale statement is not a current programme-status assertion.

### COR-07 — External evidence trail

The received audit did not contain a durable claim-level external-source trail. The remediation pack now contains a 42-row claim-level source register, 92 hashed evidence-artifact links, and a complete 74-file original/converted source manifest. This additive remediation does not retroactively cure the evidence controls of the received edition, and the successor register remains subject to the overall release hold.

## Corrections to standards, precedent, and policy characterizations

### COR-08 — MEASNET and IEC wind-resource wording

The project has no on-site measurement in the committed resource chain and is properly described as pre-measurement or screening-stage against the cited procedure. The source boundary is:

- the current MEASNET publication and PDF identify the document as `Version 3, September 2022`, not v3.1;
- MEASNET supports a complete consecutive 12-month site-measurement basis and requires deviations/incomplete measurement to be disclosed and treated in uncertainty;
- MEASNET does not state that a DutchBay deviation is universally hard, unwaivable, or a financing condition precedent;
- the public preview of IEC 61400-15-1 does not establish the cited 12-month clause; and
- the official IEC public catalogue returned no 61400-15-2 publication at the cutoff, while the same request shape returned `IEC 61400-15-1:2025` as a positive control.

The catalogue evidence establishes public publication status only. It does not prove that no unpublished committee draft exists. Code or audit language may describe a method as draft-inspired only if the dated draft is produced; it must not call the current implementation a final IEC 61400-15-2 default or convention on the available evidence.

Whether on-site measurement is a financial-close condition precedent remains lender, independent-engineer, and transaction-specific judgment pending the relevant documents.

### COR-09 — IFC/ADB covenant and reserve claims

The blanket claim of a universal IFC/ADB `1.35x-1.50x` minimum band applied equally to DSCR, LLCR, and PLCR is withdrawn.

- Official guidance and project examples use transaction- and ratio-specific definitions and thresholds.
- The cited material supports professional challenge of a thin covenant package, not a universal DutchBay policy fact.
- Canonical LLCR `1.2677278108569288` and PLCR `1.3068856980285766` are reproduced model outputs; acceptable thresholds remain lender- and transaction-specific.
- Sri Lanka payment-security examples concern PPA/offtaker payment support and must not be mislabeled as DSRA sizing requirements.

Professional credit judgment may still recommend more cushion, but must be identified as analyst judgment, with DSCR, LLCR, and PLCR defined separately.

## Corrections to finance, risk, and reporting assertions

### COR-10 — Scheduled-maturity balance and modeled treatment

The canonical scheduled-maturity balance is `48.892896%` of IDC-inclusive principal and breaches the model's internal 10% cap. The modeled treatment is `cash_sweep`, not a committed refinance or conventional bullet repayment.

- Structural scheduled-maturity balance: approximately USD `38.91m`.
- Modeled sweep recovered over six periods: approximately USD `22.02m`.
- Residual at project end: approximately USD `16.89m`.

The internal 10% cap is a model control, not evidence of a universal DFI policy. Facility and intercreditor documents are required before approving transaction treatment.

### COR-11 — DSRA, guarantee, PRI, and payment-support semantics

The scenario declares a six-month DSRA target but `fund_at_close=false`, so initial DSRA is zero and the reserve is built from operating cash.

- Year-one reserve funding is approximately USD `4.768m` against a requirement of USD `8.099m`.
- Year two adds approximately USD `2.653m` and reaches the then-current target of approximately USD `7.421m`.
- `receivables_guarantee_months` has no production consumer.
- `use_revenue_guarantee` does not create a guarantee cash-flow mechanism; it controls a separate WACC fee path.
- The debt engine charges a 0.75% guarantee fee plus 1.00% PRI premium—1.75% per year on opening senior debt, approximately USD `17.297m` in total—without modeling corresponding claim proceeds or recovery cash flow.

These facts identify modeling and disclosure gaps. They do not determine the legally required reserve or payment-security instrument without transaction documents.

### COR-12 — Covenant hard-stop flags and failure reporting

`fail_on_covenant_breach`, `fail_on_large_balloon`, and `enforce_hard_covenants` have no production runtime consumers at the audited commit. Merely changing them to `true` is a no-op.

This does not mean the model always hides failure. The reproduced debt snapshot returns `FAIL`, records three years below the 1.30 DSCR threshold, flags the balloon, and the canonical report can headline the case as not bankable. Remediation requires explicit, tested failure semantics rather than configuration-only edits.

### COR-13 — Claimed 100,000-trial finance Monte Carlo run

The claim that the canonical finance Monte Carlo was run at 100,000 trials is refuted.

- The scenario's `n_scenarios: 100000` belongs to the legacy wind-AEP path.
- Current finance callers request approximately 1,000 to 20,000 trials by default or policy.
- No executed 100,000-trial finance pack was found.
- Statistical sufficiency requires predeclared precision tolerances for means, percentiles, breach probabilities, and ES/CVaR plus an actual effective-trial manifest; trial count alone is not a certificate.

The current wind-AEP adapter also cannot consume the canonical list-form finance-MC parameter schema and fails before simulation with `AttributeError: 'list' object has no attribute 'get'`. No canonical 100,000-scenario wind sidecar is therefore evidenced.

### COR-14 — FX-source attribution and verdict consistency

The reproduced canonical report states that FX was stressed to CBSL/IMF projections. The governed inputs instead use BIS-history-derived deterministic depreciation and an authored uniform finance-MC spot band; no IMF projection input used by canon was found. The lender-facing sentence is unsupported and must be replaced with wording generated from the governed run manifest.

Separately, a type-valid synthetic payload with positive equity NPV and negative equity IRR can produce a `Bankable` headline together with a negative-IRR note. This is a latent verdict-consistency defect. The current canonical headline remains correctly value-destructive because its reproduced equity NPV and equity IRR are both adverse.

## Corrections to P5 benchmarking conclusions

### COR-15 — SOTA and primary-source score withdrawals

The blanket `AT-to-ABOVE SOTA`, `9/10`, and `primary-source benchmarked` conclusions are withdrawn.

Selected mechanics conform to conventional published or locked-library implementations. That does not establish research state of the art, calibrated DutchBay sample adequacy, converged RQMC error estimates, appropriate dependence/tail treatment, lender acceptance, transaction bankability, or primary-source completeness.

The source and methodology status must be assessed claim by claim. In particular:

- the Iman-Conover full algorithm text was not obtained and remains an explicit source gap;
- pending P5 impact programmes remain `required_not_run`, not completed evidence;
- Gaussian zero-tail dependence is a mathematical property, while transaction appropriateness remains an owner/transaction judgment;
- sample adequacy, convergence, and sensitivity heuristics require controlled reproductions; and
- facility/intercreditor, exact CFADS/coverage, LLCR-window, and related finance conventions remain transaction-specific where documents are unavailable.

## Controlled register and release status

The controlling remediation artefacts at this cutoff are:

- `registers/primary_source_register.v2.json` — 42 claim-level records;
- `reproductions/reproduction_register.json` — 15 completed, 12 required-not-run, and five unavailable records;
- `registers/findings_register.v2.json` — 111 controlled findings;
- `registers/architecture_pointer_dispositions.json` — all 72 architecture pointers with explicit examination coverage;
- `qa/CONTROLLED_REGISTERS_SEMANTIC_CLOSURE_2026-08-16T111136+0530.md` — B1-B14 closure check; and
- `qa/STRUCTURAL_VALIDATION_2026-08-16T123230+0530.json` — deterministic structural PASS with exact PR-#1030 and PR-#1031 remediation controls and `release_status=HOLD`.

The controlled registers retain F5-01 and F5-02 as completely separate findings. They require separate specifications, implementation changes, tests, canon reconciliations, commits, pull requests, and closure evidence. Their opposing financial effects must not be netted rhetorically or technically.

## Remaining release gates

This corrigendum remains a controlled draft. Release remains on HOLD until, at minimum:

1. the remaining required reproductions and independent reviews are completed or honestly deferred by an authorized decision;
2. transaction-specific evidence gaps are closed or explicitly accepted by the appropriate owner;
3. required code dolphins are implemented in isolated worktrees, tested, reviewed, merged through protected GitHub controls, and verified post-merge;
4. F5-01 and F5-02 are closed independently;
5. a new versioned current-state evidence manifest is issued at each controlled save boundary without rewriting the historical checkpoint manifest or any prior current-state manifest; and
6. the Board/lender synthesis is regenerated from the approved controlled registers and this corrigendum, then independently reviewed before circulation.

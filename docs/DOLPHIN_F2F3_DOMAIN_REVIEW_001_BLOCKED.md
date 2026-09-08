**Disposition: BLOCKED — two covenant-boundary defects require correction before I can accept this candidate.** The ordinary financial calculation is sound on the cases independently executed: all 29 evaluable committed scenarios preserve their headline KPIs, both CEB fold-dominated minima remain exact, and the annual coverage fold independently reconciles to cash flow and scheduled debt service. The blockers concern malformed or contradictory published covenant inputs being accepted and producing misleading breach dates or weaker covenant status.

```text
reviewer_role: independent project-finance/domain reviewer
reviewer_identity: /root/f2f3_domain
model: gpt-6-astra
reasoning_effort: xhigh
risk_class: R3_CONSEQUENTIAL
candidate_commit: cabc5f32d74f1111972121130d62708636934c81
candidate_tree: f39e0925f811661ff555d9fe216c12b7b85405dc
base_sha: 61c5956d0ec23d03b1ac472abf735d6172ef4dbd
merge_base_sha: 61c5956d0ec23d03b1ac472abf735d6172ef4dbd
branch: codex/f2f3-dscr-recovery
worktree: /Users/aruna/.codex/worktrees/c971/dutchbay-epc-model
subject_manifest_sha256: 5eb8b86bd7e3a33f1db7851bc6a538dd615ac7ecce2794c57e80fa8d75ca8826
disposition: BLOCKED
evidence_yield: EVIDENCE_RETURNED
initial_disposition_independence: No assurance conclusion received or consulted
mutation_attestation: No source, index, ref, branch, worktree, PR or issue writes performed by reviewer
hold_and_authority_effect: None; all existing HOLD and professional/release boundaries remain
```

**Findings requiring correction**

| ID | Severity / state | Location | Finding and independently observed consequence |
|---|---|---|---|
| F2F3-DOM-01 | P1 — `BLOCKS_CURRENT_CANDIDATE` | [pipeline_v14_enhanced.py:601](/Users/aruna/.codex/worktrees/c971/dutchbay-epc-model/analytics/pipeline_v14_enhanced.py:601) | A missing or `None` `covenant_dscr` silently falls back to the higher period DSCR even when the genuine, unchanged `dscr_by_year` table contains a defined folded ratio for that year. On the real CEB capacity-charge plan, deleting only the first operating entry’s `covenant_dscr` changes **3 breaches / first year 1 / FAIL** into **2 breaches / first year 2 / REVIEW**, while headline DSCR remains **0.9069456485322224**. Setting the value to `None` produces the same result. The guard must distinguish legitimate undefined coverage from a missing or contradictory fold. Require agreement with the authoritative annual table when present and reject an invalid redundant representation; do not replace the binding folded observation with the bare period ratio. |
| F2F3-DOM-02 | P2 — `BLOCKS_CURRENT_CANDIDATE` | [pipeline_v14_enhanced.py:596](/Users/aruna/.codex/worktrees/c971/dutchbay-epc-model/analytics/pipeline_v14_enhanced.py:596) | Positive-integer and uniqueness checks do not establish that a year label agrees with the published row-period map. On the same genuine plan, changing only the first operating entry’s `operating_year` from **1 to 99** is accepted while its map still says year 1. The resulting covenant dates become **first year 2 / last year 99**, rather than **1 / 7**. The map check at lines 549–557 verifies period presence only. Validate the period, annual-row index and operating-year relationship against the map, and reject conflicting labels. A wrong `annual_row_index=999` was also accepted in the same probe, corroborating the missing relationship check. |

Both findings were demonstrated by changing ordinary in-memory dictionaries returned by public `plan_debt`; no source file was modified. These are boundary-integrity failures within the newly introduced strict-label and folded-coverage contract. They are distinct from a change in the ordinary engine’s financial mathematics.

This compact reproduction matches the executed boundary probe:

```python
import copy
from analytics.scenario_loader import load_scenario_config
from analytics.pipeline_v14_enhanced import _build_debt_covenant_snapshot
from finance.cashflow_v14 import build_annual_rows
from finance.debt_v14 import plan_debt

cfg = load_scenario_config("scenarios/ceb_bess_10mw_capacity_charge.yaml")
original = plan_debt(annual_rows=build_annual_rows(cfg), config=cfg)
first = original["first_operating_period"]

control = _build_debt_covenant_snapshot(cfg, original)
assert (
    control.years_below_threshold,
    control.first_breach_year,
    control.last_breach_year,
    control.audit_status,
) == (3, 1, 7, "FAIL")

missing_fold = copy.deepcopy(original)
del missing_fold["dscr_periods"][first]["covenant_dscr"]
weaker = _build_debt_covenant_snapshot(cfg, missing_fold)
assert (
    weaker.years_below_threshold,
    weaker.first_breach_year,
    weaker.last_breach_year,
    weaker.audit_status,
) == (2, 2, 7, "REVIEW")  # Observed defect: should reject inconsistency.

wrong_year = copy.deepcopy(original)
wrong_year["dscr_periods"][first]["operating_year"] = 99
misdated = _build_debt_covenant_snapshot(cfg, wrong_year)
assert (
    misdated.first_breach_year,
    misdated.last_breach_year,
) == (2, 99)  # Observed defect: should reject map disagreement.
```

**Ingress and capability receipt**

I accepted the bounded domain role on the basis of direct work with debt-period indexing, CFADS/debt-service ratios, bridge-service allocation, lender covenant observations, compact versus positional result contracts, independent numerical reconstruction and hostile input probes. I hold no writer, merge, issue-closure, lender, Board, professional or HOLD authority.

The exact owner instruction and the GPT-6 Astra Extra High requirement were received in the assignment; the coordinator separately confirmed the actual spawn configuration. Project association was supplied as verified by the coordinator. I independently verified the persistent runtime and active imports.

Completed ingress included:

- The complete current canonical GWTF CSV, all four RECRUIT-01 modules, `AGENTS.md`, the full pinned external CASPER/CESSPIT/CCCDIR definitions, the September 7 handover and its bootstrap, and the preserved predecessor scope/HOLD provisions.
- The full F6/F2F3 charter, including sections 10–14; the current programme `F2F3_PROFILE.md`; the current candidate implementation record; and the full preserved original dirty F2/F3 implementation record.
- Both complete F6 review records, their complete September 2 rebind records and appended base-update dispositions, plus the F6 remediation account.
- The entire 19-file candidate diff, with the changed test bodies and relevant surrounding implementation/contract code.
- The author’s scenario comparison receipt, treated as a claim and then independently reproduced.
- A lightweight historical memory pass for the fold, index-space and predecessor-review pointers. Historical numeric and delivery claims were checked against current files and execution.

Current source identities:

```text
GWTF CSV:
0cc23891d3328d95e14031e07075d186b43545e4eb0d310303ff3c8d1c2148c1
74 rules, active=74

RECRUIT module 1:
32fb1ea5975713c7ab3d68bc7042484ad2a512f72021f281bf7e5df24343398e
RECRUIT module 2:
3a3eb5b016ba32f14a5822aefcc287ea8e9b1d3a05e1d6f288974a231bc91406
RECRUIT module 3:
2374dc23a0b40eb194766bcff05fa56d53c7c914b2e9164d59eef85cf2cb88f7
RECRUIT module 4:
15ba99012044709a9407a06161694a02a698d942dba27bb8d915e4b161a0d592

F6/F2F3 charter:
6c5b1a66311b5ef656768e3dc17dd508a41987a89d931babf3605032207f25ae
Programme F2F3 profile:
53ebd2bb7d2a30f8962defde983b3756e5f10e6a0d1c0a59d6bd00b3a5733fd7
VERSION:
72f61a8feefbe4ebd0157bb5624da47287269dd09237b3c7199d4df5f3b2f66d
```

The F6 merge `e90cfc2b6c196f17322bd1a7b52badd89a46d782` and A1 revert `4082ac57283fb8c3fea5af2c649e863212dd9fd9` are ancestors of this candidate. The prohibited A1/A2 implementation paths are absent. I did not fetch or change refs under the read-only mandate. The live GitHub read initially encountered a sandbox network failure, then succeeded through the permitted escalation: issue **#1110 is OPEN**, and no F2/F3 PR appeared in that ingress snapshot. That snapshot is not a final delivery-state attestation.

**Complete diff coverage**

All 19 manifest paths were read and dispositioned:

| Surface | Paths inspected | Domain conclusion |
|---|---|---|
| Financial computation | `finance/debt_v14.py` | Positional series, labelled map, operating-only period term and preserved annual fold are correct on independently executed ordinary and hostile calculations. Solver and fee/tax basis remain isolated from this change. |
| Covenant consumer | `analytics/pipeline_v14_enhanced.py` | Ordinary breach dates and folded ratios reconcile. The two integrity defects above block acceptance. Compact ScenarioResult compatibility is retained. |
| Contract façade | `analytics/feasibility_report_contract/result_facade.py` | Correctly keeps the new series opaque. The prior incomplete taxonomy explanation is corrected; no new report route is introduced. |
| Version and provenance | `VERSION`, `pyproject.toml`, `analytics/feasibility_report_contract/engine_identity.py`, `analytics/grid/synthetic_feeder_placeholder.py`, `conf/synthetic_feeder_placeholder.yaml` | Version 15.5.0 is warranted by the public-shape and covenant behavior change. Source-hash updates match VERSION’s actual bytes; no grid mathematics change appears in the diff. |
| Documentation | `CHANGELOG.md`, `changelog.d/f2-f3-dscr-series-unification.changed.md`, `docs/DEPRECATIONS.md`, `docs/DOLPHIN_F2F3_DSCR_UNIFICATION_IMPLEMENTATION_RECORD.md` | Scope, alias retention, financial impact, original recovery and authority boundaries are materially candid. The strict-boundary claims require the identified fixes. |
| Finance and covenant tests | `tests/finance/test_debt_dscr_series_unification.py`, `tests/finance/test_debt_period_taxonomy.py`, `tests/api/test_run_full_pipeline_v14_lender_stack.py`, `tests/analytics/test_pipeline_enhanced_coverage.py` | Old-shape assertions are revised substantively: exact set/tail, actual positional length, both minimum terms and genuine labelled observations are retained or strengthened. Missing fold/map-consistency cases remain unguarded. |
| Identity-dependent tests | `tests/contracts/test_d3b_execution_contract.py`, `tests/contracts/test_d3c_context_binding_contract.py`, `tests/grid/test_synthetic_feeder_placeholder.py` | Fixtures and derived identity pins move consistently with version provenance. Existing independent digest and corruption checks remain present and selected checks pass. |

**Independent execution and oracle results**

The common execution environment was:

```bash
PYTHONDONTWRITEBYTECODE=1
PYTHONPATH=/Users/aruna/.codex/worktrees/c971/dutchbay-epc-model
/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python
```

The base subprocess used the same interpreter with its working directory and first `PYTHONPATH` entry set to the real base worktree at:

`/Users/aruna/Downloads/DutchBay_Oldest_First_Programme_2026-09-07/f2f3/base_worktree`.

| Check | Exact command or executed method | Result |
|---|---|---|
| Runtime | `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python -VV` | Python **3.12.13**. |
| Environment | `DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv PYTHONDONTWRITEBYTECODE=1 ./check_venv.sh --no-bootstrap` | PASS; correct external prefix, active c971 imports, no editable installation or foreign checkout path. |
| Rules bootstrap | `DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python dutchbay_bootstrap_rules.py` | **74 active v3.0 rules**. |
| Independent financial sweep | Reviewer-authored stdin harness invoking separate real base/candidate subprocesses; every scenario passed through `evaluate_with_overrides(config_path=..., return_full_result=True)`, with a separate public `plan_debt` call on `build_annual_rows(cfg)`. | **37 attempted per tree, 29 evaluated, eight identical failures.** All KPI `repr` values, old debt values except authorized `dscr_series`, compact ScenarioResult series, config hashes and old key-order prefix matched exactly. |
| Independent annual fold | For each mapped row: original row CFADS minus its published senior fee, divided by its scheduled service; add the unmapped bridge service to the first mapped row’s denominator. No `dscr_periods` or fold helper was used to derive the expected ratio. | Reconstructed `dscr_by_year` matches exactly on **29/29** scenarios; headline equals the minimum over independently mapped operating-period and annual-fold observations. Candidate covenant counts and dates match the independently derived year set on **29/29**. |
| Public boundary probes | Genuine CEB `plan_debt` output, deep-copied and changed in memory one field at a time. | The two blocker classes reproduce; missing mapped period and duplicate-period constructions used in the probe reject; wrong annual-row index is accepted. |
| Input years | Public `plan_debt` with explicit `None`, `True`, `0`, `-1`, `1.5`, invalid text, NaN and infinity. | **8/8 rejected**. |
| Construction and absence | Public CEB plans at construction counts **0, 1, 3**; separate empty-row plans at **0, 3**. | Construction/bridge/first-operation and mapped labels agree; no-row bridge absence remains explicit `None`, labels remain absent and exact appended-key tail is preserved. |
| Post-tenor labels | Public lender plan. | Periods **17–22** retain operating years **15–20**, with both DSCR representations undefined. |
| Deprecated alias | `deprecated_raw_dscr_series` under `warnings.catch_warnings`. | Exact positional values, one `DeprecationWarning`. |
| Reviewer’s hostile function mutation | Real-worktree, in-memory replacement of `_operating_dscr_minimum` with an all-defined-period minimum; independent CFADS/service oracle before and after. | **Killed**: mutant **−0.4607016855231866** versus correct **−0.34759965955565236**. Fold minimum **−0.25238670859375845**. Passing controls before and after; valid nonordinal years **7–13** retained. |
| Manifest and source identity | Independently compared sorted manifest paths with the exact base-to-HEAD diff and working `git hash-object` values. SHA-256 inventory of **1,540 tracked regular files** before/after the financial sweep. | All unchanged. All **19/19** subject blobs still matched after focused execution. |
| Whitespace | `git diff --check` | Exit 0. |

The independent sweep preserved the important quantities at full precision:

| Scenario | Headline minimum | Annual-fold minimum | Operating-period minimum | Candidate covenant result |
|---|---:|---:|---:|---|
| CEB capacity-charge BESS | 0.9069456485322224 | 0.9069456485322224 | 1.2999999999999998 | 3 breaches, years 1–7, FAIL |
| CEB solar/nightpeak BESS | 0.8724193845452927 | 0.8724193845452927 | 1.2999999999999998 | 2 breaches, years 1–4, REVIEW |
| Lender case | 1.3 | 1.3 | 1.3 | 0 DSCR breaches |

The eight unevaluable files were `bad_missing_tax.yaml`, `contracts_edgecase_base_v14.yaml`, `dscr_sensitivity_example.yaml`, `dutchbay_mc_enhanced_2025Q4.yaml`, `dutchbay_sprint17_enhanced.yaml`, `example_fx_structured_blocks.yaml`, `kolonnawa_epc_100mw.yaml` and `sensitivity_parameters_examples.yaml`. Seven produced matching required-field validation failures; the structured-FX example produced the matching multiple-document YAML error. None was silently omitted.

The focused test commands were:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" \
/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python -m pytest \
-p no:cacheprovider --no-cov -o addopts='' \
tests/finance/test_debt_dscr_series_unification.py \
tests/finance/test_debt_period_taxonomy.py \
tests/finance/test_canon_vector_is_computed.py \
tests/api/test_covenants_v14.py \
tests/finance/test_multitech_generation.py::test_canonical_lendercase_economics_unchanged -q
```

Result: **237 passed, one Hypothesis collection warning, 8.65 seconds**.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" \
/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python -m pytest \
-p no:cacheprovider --no-cov -o addopts='' \
tests/contracts/test_d3c_result_projection_contract.py::test_real_public_gateway_is_an_independent_lossless_oracle \
tests/contracts/test_d3c_context_binding_contract.py::test_success_identity_matches_an_independent_like_for_like_oracle \
tests/contracts/test_d3b_execution_contract.py::test_constructive_path_is_one_call_and_returns_immutable_complete_result \
tests/contracts/test_d3b_execution_contract.py::test_success_constructor_detaches_caller_owned_proxy_backings \
tests/grid/test_synthetic_feeder_placeholder.py::test_production_configuration_compiles_opendss_and_has_exact_manifest_hash \
tests/grid/test_synthetic_feeder_placeholder.py::test_payload_hashes_are_exact_for_the_pinned_sources -q
```

Result: **6 passed, one Hypothesis collection warning, 4.59 seconds**.

One reviewer-harness failure must remain in the receipt: my first unmutated synthetic control incorrectly expected only the negative-CFADS year to breach. The other six serviced years had coverage **1.181838842489218**, so they also breached 1.3. The control failed before any function mutation. I diagnosed the assumption, changed the oracle to derive the breach-year set from CFADS and service, and then obtained passing controls around the killed mutation. The initial failure is not evidence of a killed mutant or a candidate defect.

**Predecessor finding matrix**

| Predecessor finding | Applicability and evidence | Disposition |
|---|---|---|
| F6 assurance: no-bridge behavior tested only below public boundary | Public `plan_debt([])` exercised independently and by retained tests at construction counts 0 and 3. | `CLOSED` |
| F6 assurance: taxonomy append order claimed without a guard | Exact tail assertion remains; independent sweep additionally proves the entire old key prefix on all 29 outputs. | `CLOSED` |
| F6 domain: first operating boundary claimed underivable | Published row map directly identifies it; corrected historical treatment retained. | `CLOSED` |
| F6 domain: façade explanation covered only two taxonomy keys | Changed comment now explicitly addresses the opaque row map and absence of period-series routes. | `CLOSED` |
| F6 domain: reconsider first-operating-period routing when series routing begins | No period series becomes routable in this candidate; independent D3C projection check retains 23 routes. | `DEFERRED_TO_NAMED_DOLPHIN`: separately chartered D3C series-routing work, contract coordinator; requires explicit route and provenance acceptance; no HOLD uplift. |
| F6/charter: preserve the economically real annual fold | Independent CFADS/service reconstruction and both CEB exact minima pass. Consumer corruption can still discard the fold. | Headline calculation `CLOSED`; boundary hazard `RECURS` as **F2F3-DOM-01**. |
| Archive-induced false positives | All current evaluation and mutation work used real Git worktrees; no archive-based acceptance. Controls bracket mutation. | `CLOSED` for this review |
| F2/F3: obsolete-shape test revisions might weaken assertions | Full changed test bodies read; public shape, both minimum terms and labelled observations strengthened. | `CLOSED`, subject to adding the missing integrity cases above |
| F2/F3: invalid input labels silently replaced with ordinals | Eight invalid explicit inputs reject; omission retains the established explicit ordinal default. Positive labels contradictory to the map still pass. | Input normalization `CLOSED`; consistency hazard `RECURS` as **F2F3-DOM-02**. |
| Original record: DOC-02 supposedly exempt because headline unchanged | VERSION, pyproject and impact records now recognize covenant/public-contract consequences. | `CLOSED` |
| Original record: stale green claim and anticipated thirteenth commit | Preserved original remains historical; current record names recovery and pending review. No historical acceptance was inherited. | `CLOSED` for recovery description; present candidate remains blocked |
| Raw-alias consumers and lifecycle | Plain-list compatibility and warning accessor work; removal explicitly deferred until release/sprint and consumer-migration gates. | `DEFERRED_TO_NAMED_DOLPHIN`: finance-maintenance alias migration/removal, separate review required; no current HOLD effect |
| Native full-suite reliability and canon ULP history | No broad duplicate suite run or native-crash cure claimed. Current base/candidate exact equality and existing canon/responsiveness tests pass. | Historical risks remain outside this bounded review; no stale full-suite receipt adopted |

**Limitations and final state**

I did not run the full suite, coverage gate, a full formatting/type/pre-commit bundle, GitHub required CI, QSTS execution, stochastic qualification, release checks or merge verification. The coordinator owns the complete-suite and delivery gates. The grid check above is a compile/hash check and confers no QSTS, convergence or real-feeder evidence.

No-row public-plan shape remains correct and explicit, but the existing snapshot behavior still reports zero observations as zero breaches/PASS; I do not treat that as evidence that an economic covenant was assessed. Balloon-note/status semantics likewise remain outside this F2/F3 correction. Neither limitation is a claim that this change resolved those separate model-reporting questions.

Final observed source identity remains **cabc5f32d74f1111972121130d62708636934c81 / f39e0925f811661ff555d9fe216c12b7b85405dc**. The worktree was clean at the final check; no untracked `:memory:.ses` was present. Tracking changed from `origin/main` to the coordinator’s pushed branch during review, while reviewed source objects remained unchanged. I performed no persistence writes; this text is ready for coordinator preservation verbatim.

Both blockers need public-boundary negative tests with passing unmodified controls and a new frozen subject for independent review. This disposition does not authorize F1, A1, A2, a canon rebaseline, professional reliance, release, lender/Board circulation, issue closure or removal of any HOLD.

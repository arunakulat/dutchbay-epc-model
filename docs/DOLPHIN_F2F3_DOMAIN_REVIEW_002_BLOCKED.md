**BLOCKED — fresh independent domain review of `df4720c36d7c5417ffd6ebdf2531a397fbc16a64`.** The original four domain/assurance findings are repaired for their demonstrated cases, but a new accepted-sentinel inconsistency can still suppress a real covenant breach and return `PASS`. This disposition is independent of the assurance reviewer’s successor conclusion, which I have not received.

**Reviewed object and capability.**

| Item | Verified value |
|---|---|
| Reviewer role | Independent read-only principal project-finance/domain reviewer; separate from writer and assurance |
| Actual execution setting | `gpt-6-astra`, Extra High / `xhigh` |
| Worktree | `/Users/aruna/.codex/worktrees/c971/dutchbay-epc-model` |
| Branch | `codex/f2f3-dscr-recovery` |
| Commit | `df4720c36d7c5417ffd6ebdf2531a397fbc16a64` |
| Tree | `0998a8b2ea8dc00031f46eb6331e4660f16facb6` |
| Base and merge-base | `61c5956d0ec23d03b1ac472abf735d6172ef4dbd` |
| Subject manifest | `/Users/aruna/Downloads/DutchBay_Oldest_First_Programme_2026-09-07/f2f3/subject_manifest_002.tsv` |
| Manifest SHA-256 | `8765df2d692586b8d49c5fd021b6b3bf3a03528e61a7f3c3d00487ff5cb3c5b3` |
| Subject verification | All 19 manifest entries match their working-file Git blobs before execution and at final verification |
| Environment | Governed `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python`; Python 3.12.13 |
| Final worktree state | Clean; branch equals its tracking branch; reviewed commit/tree unchanged |

Project association was supplied as verified by the coordinator. I independently verified the governed Python identity, active-worktree imports, `check_venv.sh --no-bootstrap`, and the canonical bootstrap’s 74 active GWTF rules. I made no source, index, ref, external-state or evidence-file changes, and did not delegate.

The complete governance ingress from the preceding review remains applicable: live AGENTS, full canonical GWTF CSV, all four RECRUIT-01 modules, the full external CESSPIT/CASPER/CCCDIR framework record, newest handover and applicable predecessor bootstrap/HOLD instructions, full F6/F2F3 charter including sections 10–14, programme profile, complete relevant predecessor domain/assurance and rebind records, and preserved original F2/F3 implementation record. For this successor I verified governance hash continuity, reran the bootstrap, reread the complete current profile and implementation record, and read both preserved initial blocked dispositions. No previous acceptance was transferred.

**Blocking finding: F2F3-DOM-03, P2 — validated undefined sentinels are assessed differently from their normalized meaning.**

Location: [analytics/pipeline_v14_enhanced.py:583](/Users/aruna/.codex/worktrees/c971/dutchbay-epc-model/analytics/pipeline_v14_enhanced.py:583), especially the raw-entry append at line 589 and fallback/skip logic at lines 641–656.

`_validated_covenant_periods` compares each coverage field after `_finite_dscr` normalization, but appends the original entry. Consequently, `None`, `nan`, `inf` and `"n/a"` all satisfy the same undefined reference during validation, while only raw `None` activates the documented fallback to period DSCR during assessment.

I independently executed this complete source contract:

```python
config = {"Financing_Terms": {"target_dscr": 1.3}}
debt = {
    "dscr_periods": [{
        "period": 0,
        "dscr": 0.9,
        "covenant_dscr": None,
        "operating_year": 7,
        "annual_row_index": 0,
    }],
    "dscr_series": [0.9],
    "annual_row_debt_period_map": [{
        "debt_period": 0,
        "annual_row_index": 0,
        "year": 7,
    }],
    "dscr_by_year": {7: None},
    "min_dscr": 0.9,
    "balloon_remaining": 0,
}
```

With this unmodified input, `_build_debt_covenant_snapshot` correctly reports one breach in year 7 and `REVIEW`. Changing **only** `dscr_periods[0]["covenant_dscr"]` gives:

| Redundant folded value | Boundary result | Breaches | First / last year |
|---|---|---:|---|
| `None` — control before | `REVIEW` | 1 | 7 / 7 |
| `float("nan")` | `PASS` | 0 | `None` / `None` |
| `float("inf")` | `PASS` | 0 | `None` / `None` |
| `"n/a"` | `PASS` | 0 | `None` / `None` |
| `None` — control after | `REVIEW` | 1 | 7 / 7 |

The corrupted variants return “All DSCR covenant requirements met” with the same `0.9` headline and unchanged authoritative sources.

This is a boundary-contract defect demonstrated with a synthetic valid fallback case. I did **not** observe this representation in the 29 evaluated production scenarios, whose canonical builder already normalizes its outputs. That limits the observed reach; it does not resolve the contradiction between the accepted sentinel contract and the assessment. The implementation explicitly permits undefined sentinels and documents period fallback when the annual source has no folded figure.

The correction should ensure assessment consumes the canonical normalized observations, or reject noncanonical representations consistently. The regression should vary undefined folded representations while retaining a defined, breaching period ratio and unchanged source fields. This finding blocks the current object.

**Full-diff coverage.**

I reviewed the complete final base-to-candidate change, not merely the four-file remediation delta:

- Financial and reporting behavior: `finance/debt_v14.py`, `analytics/pipeline_v14_enhanced.py`, and `analytics/feasibility_report_contract/result_facade.py`.
- Release identity and dependent pins: `VERSION`, `pyproject.toml`, `analytics/feasibility_report_contract/engine_identity.py`, `analytics/grid/synthetic_feeder_placeholder.py`, and `conf/synthetic_feeder_placeholder.yaml`.
- Impact, lifecycle and review claims: `CHANGELOG.md`, `changelog.d/f2-f3-dscr-series-unification.changed.md`, `docs/DEPRECATIONS.md`, and `docs/DOLPHIN_F2F3_DSCR_UNIFICATION_IMPLEMENTATION_RECORD.md`.
- All seven changed test modules: finance DSCR unification and period taxonomy; enhanced-pipeline coverage; lender-stack API; D3B execution; D3C context binding; synthetic feeder placeholder.

The two-term headline minimum and unchanged gearing target are financially distinct and remain correctly separated in the implementation. The new positional public series and compact `ScenarioResult` adaptation are consistent with their respective contracts. The release bump correctly discloses a consequential public-series and covenant-reporting change. The version/hash dependencies are necessary consequences of that bump; the inspected grid source delta changes the VERSION pin, without changing grid calculations.

**Fresh independent execution and oracle provenance.**

I reran an independently authored comparison harness in the real base worktree and candidate worktree, using the same governed interpreter and setting each active checkout first on `PYTHONPATH`. It invoked the canonical `evaluate_with_overrides(..., return_full_result=True)` gateway and separately executed public `plan_debt`.

All 37 current scenario files were attempted in each worktree:

- 29 evaluated successfully.
- All KPI values, headline minima, old debt-result values other than the authorized `dscr_series` shape, and compact `ScenarioResult.dscr_series` matched exactly.
- The old debt dictionary key order remained the exact prefix, with `dscr_periods` appended.
- Eight files failed identically: `bad_missing_tax.yaml`, `contracts_edgecase_base_v14.yaml`, `dscr_sensitivity_example.yaml`, `dutchbay_mc_enhanced_2025Q4.yaml`, `dutchbay_sprint17_enhanced.yaml`, `example_fx_structured_blocks.yaml`, `kolonnawa_epc_100mw.yaml`, and `sensitivity_parameters_examples.yaml`. Seven failed scenario validation; the structured-FX example failed single-document YAML loading. These remain unevaluable, not passes.

For every evaluated scenario I reconstructed the annual fold from raw annual CFADS, period fees and scheduled debt service, without using `dscr_periods` as the oracle:

- For the first mapped row, the denominator includes its own scheduled service plus the bridge’s scheduled service.
- Other rows use their own scheduled service.
- The numerator subtracts the mapped period’s senior fee once.
- An unserviced mapped period is undefined.

The independently reconstructed values matched `dscr_by_year` exactly. The headline equalled the minimum of the mapped operating-period ratios and those reconstructed annual ratios. Covenant counts and first/last years matched the reconstructed annual values and explicit map labels.

| Scenario | Operating-period minimum | Annual-fold minimum / headline | Covenant result |
|---|---:|---:|---|
| CEB capacity-charge BESS | `1.2999999999999998` | `0.9069456485322224` | 3 breaches, years 1–7, `FAIL` |
| CEB solar/BESS nightpeak | `1.2999999999999998` | `0.8724193845452927` | 2 breaches, years 1–4, `REVIEW` |
| Canonical lender case | `1.3` | `1.3` | 0 DSCR breaches, `PASS` |

The lender-case balloon warning remains present. Its existing relationship with the DSCR audit status is outside this correction.

I also replayed ten independently constructed CEB corruptions: omitted fold, null fold, wrong year, wrong row, erased coverage fields, all-year shift, invented bridge label, omitted period, duplicated period and replacement of the fold with the higher period ratio. **All ten raised `PipelineValidationError`**, with unchanged original controls before/after.

Fresh legitimate boundary probes passed for construction counts 0, 1 and 3; operating years 7–18; empty annual rows; explicit absent bridge; mapped undefined post-tenor observations; and alias compatibility with exactly one `DeprecationWarning` from the accessor. Eight invalid explicit input-year classes—`None`, Boolean, zero, negative, fractional, nonnumeric, NaN and infinity—were rejected. The lender’s mapped undefined tail retained `(period, year)` pairs `(17,15)` through `(22,20)`.

The focused command was:

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

Result: **268 passed, one Hypothesis collection warning, 9.41 seconds**.

A second focused command, using the same environment and pytest options, executed:

- D3C result projection’s real public-gateway lossless oracle.
- D3C context binding’s independent like-for-like identity oracle.
- D3B constructive immutable-result and detached-proxy controls.
- Synthetic feeder production compilation/exact-manifest check.
- Synthetic feeder exact payload-hash check.

Result: **6 passed, one Hypothesis collection warning, 4.62 seconds**.

These fresh runs complement the independent financial harness. The author’s `scenario_comparison.json` was inspected as a receipt, not substituted for independent execution. I did not duplicate the full suite or claim the coordinator’s full-suite result as my own.

**Mutation attestation.**

Two own in-memory function mutations fired against independently authored oracles:

1. Replacing `_validated_covenant_periods` with a pass-through caused the rejection oracle to fail on the real CEB null-fold corruption. The unmutated boundary oracle passed before and after restoration.
2. Replacing `_operating_dscr_minimum` with the minimum over all defined periods caused the financial oracle to fail: it returned the unmapped bridge ratio `-0.4607016855231866` instead of the correct headline `-0.34759965955565236`.

The independent hostile financial case used years 7–18, construction count 3, eight-year tenor, one interest-only year, a USD annuity schedule and negative first-year CFADS. Both unmutated controls returned:

```text
headline       = -0.34759965955565236
bridge ratio   = -0.4607016855231866
annual minimum = -0.25238670859375845
breach years   = [7, 8, 9, 10, 11, 12, 13]
```

Functions were restored in `finally` blocks. Source bytes remained unchanged. The earlier review’s first synthetic control had failed because I incorrectly assumed only the first year breached; that reviewer-oracle error remains disclosed in the preserved predecessor record. It was not counted as a mutation kill. The corrected cash-flow/service oracle was used successfully in this fresh review.

**Predecessor disposition matrix.**

| Predecessor finding or concern | Fresh disposition |
|---|---|
| F2F3-DOM-01: missing/null defined CEB fold downgrades assessment | **Demonstrated cases closed.** Both now raise typed validation errors. General undefined-fallback correctness remains blocked by DOM-03. |
| F2F3-DOM-02: unique but incorrect year / wrong annual row accepted | **Closed for reviewed object.** Independent replays reject both. |
| F2F3-ASR-01: erasing coverage can return zero breaches/PASS | **Closed for demonstrated case.** Erased coverage fields are rejected before assessment. |
| F2F3-ASR-02: shifted years, invented bridge and malformed period identity accepted | **Closed for demonstrated cases.** Independent shifted-year, bridge, missing-period and duplicate-period probes reject them. |
| F6 helper-only no-bridge evidence | **Resolved at public boundary.** Fresh `plan_debt([])` execution with construction 0/1/3 preserves explicit absence. |
| F6 published ordering claim | **Current-object order verified independently across all 29 scenarios.** Existing standing test still checks its old prefix as a set; arbitrary prefix reordering is an explicitly accepted residual. |
| F6 first-operating boundary claimed non-derivable | **Historical claim rejected.** The boundary is derivable from the public map. |
| F6 facade rationale covered only two taxonomy keys | **Corrected.** Rationale now covers the derived boundary and opaque labelled series. |
| Future first-operating/series routing | **Deferred unchanged.** Separate contract-coordinator work; no current series route or authority uplift. |
| F2/F3 fold-loss hazard | **Controlled.** Both CEB headline values and independent cash-flow/service reconstruction pass. |
| Archive-derived false-positive controls | **Avoided.** Real Git base and candidate worktrees were used. |
| Old-shape assertions weakened during migration | **No new blocking weakening found.** Exact timeline, additive-key and two-term minimum checks remain; ordering residual disclosed above. |
| Invalid explicit years silently replaced with ordinals | **Controlled.** Eight hostile classes rejected; valid nonordinal labels preserved. |
| Historical DOC-02 exemption claim | **Superseded.** Version 15.5.0 and impact disclosures reflect consequential behavior. |
| Raw-alias migration | **Retained/deferred.** Plain-list compatibility and warning accessor remain; no removal authorized. |
| Empty-row zero-breach/PASS behavior | **Preserved residual.** It is not evidence that an economic covenant was assessed. |

**Integrity, limitations and authority.**

The all-scenario harness captured and compared SHA-256 values for **1,540 tracked files** before/after execution, with no change. Final manifest verification again passed 19/19. Relevant final source hashes were:

```text
finance/debt_v14.py
438f34c631769befc9f9df5de0a4f557a1ad7c409c2bbae9bab14e0cbe1dbfa5

analytics/pipeline_v14_enhanced.py
835275f750cbbae28a339f2a6b1eac7caf7531492c30e8be3a8e257e84211fe1

VERSION
72f61a8feefbe4ebd0157bb5624da47287269dd09237b3c7199d4df5f3b2f66d
```

`git diff --check` passed. No untracked `:memory:.ses` file was present at final verification, and I deleted nothing. Recovered originals remain untouched.

This review verifies internal consistency, financial derivation within the scoped model and the stated compatibility boundaries. It does not authenticate coherently altered source dictionaries or establish a new finance policy. It authorizes no F1, A1, A2, fee/tax modification, canon rebaseline, release, shared-ledger change, or removal of any F5-02, #1110, professional, lender, Board or other existing HOLD. Required exact-head CI, a fresh corrected-object review and merge verification remain separate delivery requirements. **The reviewed object is not accepted because F2F3-DOM-03 remains open.**

**Disposition: BLOCKED for `df4720c36d7c5417ffd6ebdf2531a397fbc16a64`.** The repair closes the original missing-field and map-consistency counterexamples. A remaining normalization defect can still turn a defined covenant breach into `PASS`, and the implementation record needs a factual correction to a payload count that originated in my preceding review.

```text
reviewer_role: independent principal Python / assurance reviewer
reviewer_identity: /root/f2f3_assurance
model: gpt-6-astra
reasoning_effort: xhigh
risk_class: R3_CONSEQUENTIAL
candidate_commit: df4720c36d7c5417ffd6ebdf2531a397fbc16a64
candidate_tree: 0998a8b2ea8dc00031f46eb6331e4660f16facb6
base_sha: 61c5956d0ec23d03b1ac472abf735d6172ef4dbd
merge_base_sha: 61c5956d0ec23d03b1ac472abf735d6172ef4dbd
branch: codex/f2f3-dscr-recovery
worktree: /Users/aruna/.codex/worktrees/c971/dutchbay-epc-model
subject_manifest: /Users/aruna/Downloads/DutchBay_Oldest_First_Programme_2026-09-07/f2f3/subject_manifest_002.tsv
subject_manifest_sha256: 8765df2d692586b8d49c5fd021b6b3bf3a03528e61a7f3c3d00487ff5cb3c5b3
subject_count: 19
disposition: BLOCKED
evidence_yield: EVIDENCE_RETURNED
successor_disposition_independence: No domain successor conclusion received or consulted
mutation_attestation: No source, index, ref, branch, worktree, PR or issue writes performed by reviewer
hold_and_authority_effect: None
```

**Blocking findings**

| ID | Severity / state | Location | Finding |
|---|---|---|---|
| F2F3-ASR-03 | P1 — `BLOCKS_CURRENT_CANDIDATE` | [pipeline_v14_enhanced.py:589](/Users/aruna/.codex/worktrees/c971/dutchbay-epc-model/analytics/pipeline_v14_enhanced.py:589), with assessment at [line 641](/Users/aruna/.codex/worktrees/c971/dutchbay-epc-model/analytics/pipeline_v14_enhanced.py:641) | `_validated_covenant_periods` compares normalized coverage to the canonical reference but returns the original, unnormalized entry. When the annual source legitimately contains `None` and the period DSCR is defined, a redundant folded value of NaN, positive/negative infinity, or `"n/a"` passes validation as equivalent to `None`. Assessment then sees a non-`None` raw value, skips it, and fails to apply the documented period fallback. An independently constructed complete source contract changes from **REVIEW / one breach / year 7 / minimum 0.8** to **PASS / zero breaches / minimum 0.8**. Assessment must consume canonical normalized observations, or enforce an equivalent representation rule that prevents this suppression. |
| F2F3-ASR-04 | P2 — `BLOCKS_CURRENT_RECORD` | [DOLPHIN_F2F3_DSCR_UNIFICATION_IMPLEMENTATION_RECORD.md:157](/Users/aruna/.codex/worktrees/c971/dutchbay-epc-model/docs/DOLPHIN_F2F3_DSCR_UNIFICATION_IMPLEMENTATION_RECORD.md:157) | “All seven payload hashes match” is incorrect. There are **six** independently pinned feeder/profile payloads, all unchanged. The additional generated `MANIFEST.sha256` file changes because its `manifest.json` checksum changes. **This error originated in my initial assurance review**, which the implementation record accurately repeated. Preserve that initial review verbatim, but explicitly supersede its false count. Fresh execution proves that the checksum inventory changes solely at the `manifest.json` digest token; this does not indicate a grid-payload change. |

The first finding has a compact, complete reproduction independent of the author’s test helpers:

```python
import copy
from analytics.pipeline_v14_enhanced import _build_debt_covenant_snapshot

config = {"Financing_Terms": {"target_dscr": 1.3}}
original = {
    "dscr_periods": [{
        "period": 0,
        "dscr": 0.8,
        "operating_year": 7,
        "annual_row_index": 0,
        "covenant_dscr": None,
    }],
    "dscr_series": [0.8],
    "annual_row_debt_period_map": [{
        "debt_period": 0,
        "annual_row_index": 0,
        "year": 7,
    }],
    "dscr_by_year": {7: None},
    "timeline_periods": 1,
    "min_dscr": 0.8,
    "balloon_remaining": 0.0,
}

def observe(debt):
    s = _build_debt_covenant_snapshot(config, debt)
    return (
        s.audit_status,
        s.years_below_threshold,
        s.first_breach_year,
        s.last_breach_year,
        s.dscr_min,
    )

assert observe(original) == ("REVIEW", 1, 7, 7, 0.8)

for sentinel in [float("nan"), float("inf"), float("-inf"), "n/a"]:
    altered = copy.deepcopy(original)
    altered["dscr_periods"][0]["covenant_dscr"] = sentinel
    assert observe(altered) == ("PASS", 0, None, None, 0.8)  # Observed defect.

assert observe(original) == ("REVIEW", 1, 7, 7, 0.8)
```

This is within the candidate’s explicit contract: its docstring says that a period ratio is used when the authoritative annual table carries no folded figure, and its validator intentionally accepts normalized undefined sentinels. It is not a claim that the ordinary CEB engine currently emits this malformed redundant representation.

**Predecessor findings and fresh disposition**

Both initial reviews were already preserved before I consulted the domain predecessor. I independently replayed their concrete examples against this candidate.

| Predecessor concern | Fresh disposition | Evidence |
|---|---|---|
| ASR-01: erased coverage can yield false `PASS` | `CLOSED` for the original counterexample | Erasing both coverage fields now raises `PipelineValidationError`; genuine CEB controls remain three breaches, years 1–7, `FAIL`. |
| DOM-01: missing/null defined fold can replace a binding annual observation | `CLOSED` for the original counterexamples | Missing or null redundant fold conflicts with the unchanged defined annual source and is rejected. |
| ASR-02 / DOM-02: wrong year, row, period, or fabricated bridge label | `CLOSED` for the original counterexamples | Independently altered year 99, row 999, duplicate period, reversed periods and bridge operating label all reject. |
| Boundary treatment of legitimate undefined observations | `RECURS` in a distinct form | Consistent absence remains accepted, but ASR-03 shows normalized absence can suppress a defined fallback observation. |
| F6 helper-only no-bridge test | `CLOSED` for this candidate | Public empty-row tests at construction counts 0 and 3 passed, including during the firing-control experiment. |
| F6 ordering claim | `CLOSED` for this candidate identity; standing-test residual retained | Full old key order is an exact prefix across all 29 evaluated base/candidate outputs. The standing test still checks that prefix as a set; the implementation record now discloses this limitation. |
| F6 facade explanation and future routing | Explanation corrected; routing `DEFERRED` | New labels remain opaque, and route count remains 23. Future series routing remains a separately chartered contract-coordinator task. |
| Both-term headline minimum and CEB fold protection | `CLOSED` for ordinary current outputs | All old debt values other than the authorized public-series shape match the base; both CEB headlines remain exact. Existing canon and responsiveness tests passed. |
| Old-shape fixture/assertion preservation | `CLOSED` | Exact key-set and tail assertions, strengthened timeline length, both minimum terms, sentinel behavior, threshold fallback and balloon assertions remain substantive. |
| Initial assurance synthetic payload count | `SUPERSEDED_BY_CORRECTION_REQUIRED` | Six payloads are unchanged; the checksum inventory changes solely with `manifest.json`. ASR-04 corrects my prior erroneous seven-payload statement. |
| Historical DOC-02 exemption / raw alias lifecycle | Version-impact correction retained; alias migration `DEFERRED` | VERSION and package version remain 15.5.0; impact is disclosed; plain-list alias and warning accessor remain compatible. |

**Independent execution**

The governed interpreter was Python **3.12.13** at:

`/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python`

All Python execution used `PYTHONDONTWRITEBYTECODE=1`, with the applicable real worktree first on `PYTHONPATH`. Environment validation passed with active c971 imports, no foreign checkout paths and no editable project installation. The canonical rules bootstrap reported **74 active v3.0 rules**.

The focused command was:

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH="$PWD" \
/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python \
  -m pytest -o addopts='' -p no:cacheprovider --no-cov -q \
  tests/finance/test_debt_dscr_series_unification.py \
  tests/finance/test_debt_period_taxonomy.py \
  tests/finance/test_canon_vector_is_computed.py \
  tests/finance/test_multitech_generation.py \
  tests/analytics/test_pipeline_enhanced_coverage.py \
  tests/api/test_run_full_pipeline_v14_lender_stack.py \
  tests/contracts/test_d3b_execution_contract.py \
  tests/contracts/test_d3c_result_projection_contract.py \
  tests/contracts/test_d3c_context_binding_contract.py
```

Result: **670 passed, one Hypothesis collection warning, 30.07 seconds, exit 0**.

Additional independently authored stdin probes established:

- **16 genuine CEB corruption cases rejected**, with unchanged passing controls around each case. These covered missing observation fields, complete coverage erasure, null fold, wrong year/row, fabricated bridge label, duplicate period, reversed period list, absent annual fold year, absent source map, Boolean map year and wrong map row index.
- **Four consistent undefined representations**—`None`, NaN, infinity and `"n/a"` in both authoritative and redundant coverage—remain accepted as zero observations.
- **Zero and negative defined period ratios** remain breaches when the annual source explicitly has no folded observation.
- The **four inconsistent fallback-sentinel cases in ASR-03** produce false `PASS`, with passing before/after controls.

I independently executed a fresh firing control in three separate processes within the real candidate worktree. The in-memory mutant replaced only:

```python
pipeline._validated_covenant_periods = lambda debt: debt["dscr_periods"]
```

Each process invoked `pytest.main` with the prescribed cache/coverage options and these selectors:

```text
tests/finance/test_debt_dscr_series_unification.py::test_real_covenant_rejects_incomplete_or_contradictory_observations[null_fold]
tests/finance/test_debt_dscr_series_unification.py::test_real_covenant_rejects_incomplete_or_contradictory_observations[shift_year]
tests/finance/test_debt_dscr_series_unification.py::test_no_operating_rows_preserves_explicit_absence
```

| Run | Result |
|---|---|
| Unmutated control before | **4 passed**, exit 0, 0.28 seconds |
| Validator-bypass mutant | **2 failed, 2 passed**, exit 1, 0.33 seconds |
| Unmutated control after | **4 passed**, exit 0, 0.28 seconds |

Both substantive failures were `DID NOT RAISE PipelineValidationError`, for `null_fold` and `shift_year`. The empty-row controls remained green. This confirms that the new rejection tests discriminate against a disabled validator; it does not close ASR-03.

**Fresh base comparison and oracle provenance**

I independently ran every current scenario through the canonical `evaluate_with_overrides(config_path=..., return_full_result=True)` gateway in separate base/candidate processes. The base was the real clean worktree at:

`/Users/aruna/Downloads/DutchBay_Oldest_First_Programme_2026-09-07/f2f3/base_worktree`

The result was **37 attempted, 29 evaluated, eight identical failures**. Across every evaluated case:

- Every KPI key/value matched at full `repr` precision.
- Enriched annual rows matched exactly.
- Compact `ScenarioResult.dscr_series` matched exactly.
- Every pre-existing debt-result value matched except the intentional change to `dscr_series`.
- Candidate `dscr_series` matched base `raw_dscr_series`.
- The full old debt key order remained an exact prefix, with only `dscr_periods` appended.
- The facade route count remained **23**.

The identical failing files were `bad_missing_tax.yaml`, `contracts_edgecase_base_v14.yaml`, `dscr_sensitivity_example.yaml`, `dutchbay_mc_enhanced_2025Q4.yaml`, `dutchbay_sprint17_enhanced.yaml`, `example_fx_structured_blocks.yaml`, `kolonnawa_epc_100mw.yaml`, and `sensitivity_parameters_examples.yaml`. Checkout text was normalized before comparing exception type/message. None was counted as an evaluated case.

This fresh comparison uses the independently executable base as its compatibility oracle. Finance assurance additionally includes the pre-existing canon/driver tests, the preserved both-term minimum assertions and the new control-bounded mutation. Acceptance therefore does not depend solely on author-written tests or author receipts.

**Fresh identity-causality verification**

I verified all **15 unchanged subject blobs** against the preceding candidate, including VERSION, both identity-source files, the synthetic config and both golden-pin test files. I then regenerated the relevant objects in both real worktrees; I did not assume the preceding causal receipt transferred automatically.

For D3B, the pre-existing independent encoder `_independent_success_identity_json`, ordinary SHA-256 and the production digest’s `.value` agreed with each worktree’s golden pin:

```text
Base:
d6dfe823cec253092ffc88ee588f559cb0f39bce65823e1886969fc56117a048

Candidate:
23871193b0cb28d100fd65f3da9e67e0052f15812bbdcb1636bea8a23c8aa720
```

The complete preimage differs by **exactly two `15.4.0` → `15.5.0` substitutions**. Every other preimage byte matches. The independent encoder and altered-content responsiveness guard remain unchanged.

For synthetic generation, both production OpenDSS compile configurations returned `passed_compile_only_no_convergence_claim`, with exact pinned manifest digests:

```text
Base:
24a723f33e13035def1f3fa68140bf6dc22f1b380d230b44331caadde5b25b2f

Candidate:
04579a8ee748d79b16aec3e1769fea213e27c364f8747359e96bc2b723530956
```

All **six** independently pinned feeder/profile payload hashes matched exactly. The complete JSON manifest comparison found only:

1. `/generator/engine_version`;
2. `/source_snapshots/generator_source/sha256`;
3. `/source_snapshots/version_file/sha256`.

Both source hashes matched the actual respective file bytes. The generated `MANIFEST.sha256` text became identical after replacing only the base `manifest.json` digest with the candidate digest. Thus the two golden changes are attributable to version/source identity, with no changed feeder/profile payload or weakened contract.

Two unsuccessful reviewer-harness attempts remain disclosed:

- The first compared a digest string directly with the production digest model, rather than its `.value`; that assertion failed before synthetic generation.
- The next assumed every non-JSON generated file was an unchanged payload, thereby including `MANIFEST.sha256`; that assertion exposed my erroneous prior payload count.

The corrected harness passed all D3B, six-payload, source-hash, three-leaf and checksum-inventory assertions. Neither failed attempt is counted as a successful control or candidate regression.

**Ingress, complete diff coverage and preservation**

This is continuation of the same independent reviewer role. I reverified governance continuity against the complete ingress already performed: `AGENTS.md`, the canonical GWTF CSV, all four RECRUIT modules, unabridged CASPER/CESSPIT/CCCDIR definitions, applicable handovers/bootstrap, full F6/F2F3 charter including sections 10–14, programme profile, F6 implementation/review records and preserved original F2/F3 record. Current hashes remain:

```text
AGENTS.md:
215dd99e206203b8b859cc0c2b97cf2e0150ea9863a91ccab80a72cabe0f4bcd

Canonical GWTF:
0cc23891d3328d95e14031e07075d186b43545e4eb0d310303ff3c8d1c2148c1

RECRUIT modules 1–4:
32fb1ea5975713c7ab3d68bc7042484ad2a512f72021f281bf7e5df24343398e
3a3eb5b016ba32f14a5822aefcc287ea8e9b1d3a05e1d6f288974a231bc91406
2374dc23a0b40eb194766bcff05fa56d53c7c914b2e9164d59eef85cf2cb88f7
15ba99012044709a9407a06161694a02a698d942dba27bb8d915e4b161a0d592

F6/F2F3 charter:
6c5b1a66311b5ef656768e3dc17dd508a41987a89d931babf3605032207f25ae

Programme profile:
53ebd2bb7d2a30f8962defde983b3756e5f10e6a0d1c0a59d6bd00b3a5733fd7

Pinned framework definitions:
c98cb92332e250b82fa5adf21d12c7c816189f626f5b16d10da66ec08e2c20af
```

The role remains appropriate to Python contracts, exact JSON identity, finance index-space compatibility, independent oracles and mutation discrimination. Project association and the actual model configuration were supplied as verified by the coordinator; runtime and active imports were independently verified.

I inspected the complete final base-to-candidate diff across all 19 subjects:

| Surface | Complete subject coverage |
|---|---|
| Finance and covenant code | `finance/debt_v14.py`; `analytics/pipeline_v14_enhanced.py` |
| Contract and identity code | `analytics/feasibility_report_contract/result_facade.py`; `analytics/feasibility_report_contract/engine_identity.py` |
| Synthetic source/config | `analytics/grid/synthetic_feeder_placeholder.py`; `conf/synthetic_feeder_placeholder.yaml` |
| Version and documentation | `VERSION`; `pyproject.toml`; `CHANGELOG.md`; `changelog.d/f2-f3-dscr-series-unification.changed.md`; `docs/DEPRECATIONS.md`; `docs/DOLPHIN_F2F3_DSCR_UNIFICATION_IMPLEMENTATION_RECORD.md` |
| Finance/API/analytics tests | `tests/finance/test_debt_dscr_series_unification.py`; `tests/finance/test_debt_period_taxonomy.py`; `tests/api/test_run_full_pipeline_v14_lender_stack.py`; `tests/analytics/test_pipeline_enhanced_coverage.py` |
| Identity-dependent tests | `tests/contracts/test_d3b_execution_contract.py`; `tests/contracts/test_d3c_context_binding_contract.py`; `tests/grid/test_synthetic_feeder_placeholder.py` |

The four-file successor repair preserves all substantive synthetic-fixture assertions. The old public-series assertion changes remain justified by the authorized positional contract; compact `ScenarioResult`, plain-list raw alias and exact JSON freezing remain compatible.

Before/after inventories of all **1,540 tracked regular files** were identical:

```text
9337a6d957d543f763341a9ee5fb4743decaedce452ad6bb39700c3763bd2336
```

That inventory hashes the ordered JSON list of tracked paths and their SHA-256 values. Final HEAD/tree remained the exact reviewed object; all 19 working-file blobs still matched manifest 002. `git diff --check` passed, Git status was clean, and `:memory:.ses` was absent at the final check. I did not delete such a file or modify any source, ref or external application.

I did not duplicate the coordinator’s full suite or attest current-head GitHub CI. Their status cannot override ASR-03 or transfer acceptance to a later head. F1, A1, A2, canon rebaseline, fee/tax changes, release and all existing professional, lender, Board and evidence HOLDs remain outside this disposition.

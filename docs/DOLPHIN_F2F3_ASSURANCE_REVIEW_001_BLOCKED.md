**Disposition: BLOCKED — two covenant-boundary validation findings block this exact candidate.** The independent scenario comparison, compact-contract checks, golden-digest reconstruction and operating-minimum mutation control passed. Those results establish substantial correctness, but the new boundary validation still accepts incomplete observations and labels that contradict the published row map.

```yaml
reviewer_role: independent_principal_python_and_assurance
reviewer_identity: /root/f2f3_assurance
model: gpt-6-astra
reasoning_effort: xhigh
risk_class: R3_CONSEQUENTIAL
candidate_commit: cabc5f32d74f1111972121130d62708636934c81
candidate_tree: f39e0925f811661ff555d9fe216c12b7b85405dc
base_sha: 61c5956d0ec23d03b1ac472abf735d6172ef4dbd
merge_base_sha: 61c5956d0ec23d03b1ac472abf735d6172ef4dbd
branch: codex/f2f3-dscr-recovery
worktree: /Users/aruna/.codex/worktrees/c971/dutchbay-epc-model
subject_manifest: /Users/aruna/Downloads/DutchBay_Oldest_First_Programme_2026-09-07/f2f3/subject_manifest_001.tsv
subject_manifest_sha256: 5eb8b86bd7e3a33f1db7851bc6a538dd615ac7ecce2794c57e80fa8d75ca8826
subject_count: 19
disposition: BLOCKED
evidence_yield: EVIDENCE_RETURNED
independence: Independent initial disposition; no other current reviewer conclusion received.
mutation_attestation: No source, tracked-file, index, ref, branch, worktree, PR or issue mutation by this reviewer.
```

The actual reviewer dispatch and coordinator’s confirmation specified GPT-6 Astra Extra High. I followed the owner instruction:

> Do not wait for approval. work autonomously. Take your best, considered and safe decision. Use the Recruit-01 and verify-01 rules to reconsider and confirm your decisions. Start all new worktrees ingressing the rulesets - GWTF, CESSPIT, CASPER and CCCDIR. Follow these rules rigorously. Copy this instruction to all new tasks, worktrees, PR's

The additional owner instruction was received verbatim: “all new worktrees, PR's etc should also inherit the GPT-6 Astra Extra High setting from the coordinator”.

**Blocking findings**

1. **F2F3-ASR-01 — P1 — Missing coverage fields become a false compliance result.** State: `BLOCKS_CURRENT_CANDIDATE`.

   At [analytics/pipeline_v14_enhanced.py:601](/Users/aruna/.codex/worktrees/c971/dutchbay-epc-model/analytics/pipeline_v14_enhanced.py:601), `.get("covenant_dscr")` followed by `.get("dscr")` treats missing fields as explicitly undefined values and silently skips the observation. The new validation requires an `operating_year`, but does not require the coverage fields belonging to that labelled observation.

   I generated a genuine debt plan for `ceb_bess_10mw_capacity_charge.yaml`. Its unmutated snapshot returned:

   ```text
   count=3, first=1, last=7, status=FAIL, min=0.9069456485322224
   ```

   I then deep-copied that result and removed only `dscr` and `covenant_dscr` from each `dscr_periods` entry. The original `dscr_series`, `dscr_by_year`, row map, year labels and headline minimum remained available. The snapshot returned:

   ```text
   count=0, first=None, last=None, status=PASS, min=0.9069456485322224
   ```

   The post-probe unmutated control again returned the original three-breach `FAIL`. This reproduces the specific favorable failure mode the charter’s §14.5 and candidate’s new fail-loud behavior aim to remove: a result that cannot be assessed is reported fully compliant.

   **Required remedy:** distinguish a missing coverage field from the existing explicit `None` sentinel. Reject incomplete labelled records with `PipelineValidationError`; preserve legitimate undefined observations and any deliberately retained sentinel behavior. Add public-boundary corruption tests using a real `plan_debt` result, with a passing unmutated control and a negative control proving the guard fires.

2. **F2F3-ASR-02 — P2 — Label validation does not establish correspondence with the authoritative row map.** State: `BLOCKS_CURRENT_CANDIDATE`.

   The check at [analytics/pipeline_v14_enhanced.py:549](/Users/aruna/.codex/worktrees/c971/dutchbay-epc-model/analytics/pipeline_v14_enhanced.py:549) proves only that the mapped period numbers occur somewhere in the labelled list. The later checks establish positive, unique integer years; they do not establish that an entry’s year and row index match the year and row attached to that debt period in `annual_row_debt_period_map`.

   Using the same genuine CEB plan, adding `100` to every non-`None` `operating_year` was accepted despite leaving the authoritative map unchanged. The reported breach dates changed from `1..7` to `101..107`. Assigning the unmapped bridge a new unique year `100` and coverage `0.5` was also accepted and created a fourth covenant observation. Missing and duplicate `period` fields in unmapped entries were accepted as well.

   **Required remedy:** where the published map accompanies a debt result, validate the correspondence of period, row index and normalized operating year against that map, including the prohibition on assigning an operating year to an unmapped bridge or construction period. Validate the positional records’ required identifiers and uniqueness. Preserve deliberately supported map-free synthetic fixtures only through an explicit, documented contract; do not let their looser shape bypass validation of genuine engine output. Add hostile tests that alter these fields while preserving the original map.

These findings concern the newly guarded covenant boundary. I did **not** observe incorrect labels or missing coverage in an unmodified `plan_debt` result, and the ordinary committed-scenario calculations passed.

**Independent execution and results**

The persistent interpreter reported Python **3.12.13**. I ran:

```bash
DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv ./check_venv.sh --no-bootstrap

PYTHONDONTWRITEBYTECODE=1 \
DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" \
PYTHONPATH="$PWD" \
/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python dutchbay_bootstrap_rules.py
```

Results: environment `PASS`, active-checkout imports confirmed, no foreign-checkout paths, no editable project installation; canonical CSV loaded with **74 active v3.0 rules**.

The principal focused test command was:

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH="$PWD" \
DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv \
/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python -m pytest \
  -o addopts='' -p no:cacheprovider --no-cov -q \
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

Result: **639 passed, 1 warning in 30.29 seconds**, exit `0`. The warning concerned Hypothesis collection and the configured `norecursedirs`.

I independently captured every current scenario through `run_v14_pipeline(config=load_scenario_config(...), validation_mode="strict")` in two separate processes, rooted respectively in the real base worktree and candidate worktree, each using the same governed interpreter and its own checkout first on `PYTHONPATH`.

Result:

- **37 attempted; 29 evaluated; eight failed identically.**
- Every KPI key/value matched at full `repr` precision, with **37–40 KPI keys** depending on the scenario.
- Enriched annual rows matched exactly.
- Compact `ScenarioResult.dscr_series` matched exactly.
- Every pre-existing debt-result value matched except the intentionally changed `dscr_series`.
- The candidate’s positional `dscr_series` matched the base’s `raw_dscr_series`.
- The complete old debt-result key order remained an exact prefix; `dscr_periods` alone was appended.
- Facade route count remained **23** in both processes.
- CEB headline values remained exactly **`0.9069456485322224`** and **`0.8724193845452927`**.

The identical failing files were `bad_missing_tax.yaml`, `contracts_edgecase_base_v14.yaml`, `dscr_sensitivity_example.yaml`, `dutchbay_mc_enhanced_2025Q4.yaml`, `dutchbay_sprint17_enhanced.yaml`, `example_fx_structured_blocks.yaml`, `kolonnawa_epc_100mw.yaml`, and `sensitivity_parameters_examples.yaml`. Errors were compared after normalizing checkout-path text; none was silently counted as an evaluated scenario.

For an independent firing control, I replaced `_operating_dscr_minimum` **in process memory only** with:

```python
def include_bridge(periods):
    values = [p["dscr"] for p in periods if p.get("dscr") is not None]
    return min(values) if values else None
```

Each of three separate processes invoked `pytest.main` with:

```text
-o addopts=
-p no:cacheprovider
--no-cov
-q
tests/finance/test_debt_dscr_series_unification.py::test_a_bridge_period_below_every_view_still_cannot_set_min_dscr
tests/finance/test_debt_dscr_series_unification.py::test_no_operating_rows_preserves_explicit_absence
```

Results:

| Run | Result |
|---|---|
| Unmutated control before | **3 passed**, exit `0`, 0.44 seconds |
| Include-bridge mutant | **1 failed, 2 passed**, exit `1`, 0.48 seconds |
| Unmutated control after | **3 passed**, exit `0`, 0.45 seconds |

The mutant failed on the substantive distinction: reported `-0.36856134841854926` versus the required operating/fold minimum `-0.33617678960277536`. No archive extraction or source-file replacement was used.

**Golden digest causality**

I independently constructed D3B successes through the existing `_d3b_success` fixture in each real worktree. I computed each digest using the pre-existing `_independent_success_identity_json` encoder and ordinary `hashlib.sha256`, and checked it against both the production digest function and that worktree’s golden pin.

```text
Base:      d6dfe823cec253092ffc88ee588f559cb0f39bce65823e1886969fc56117a048
Candidate: 23871193b0cb28d100fd65f3da9e67e0052f15812bbdcb1636bea8a23c8aa720
```

The complete independent preimage comparison established **exactly two** `15.4.0` → `15.5.0` substitutions, corresponding to the two manifest engine-version appearances. Every other preimage byte matched. The existing independent encoder and its altered-content responsiveness test were preserved; only the golden pin changed in the context-binding test file.

I also generated the synthetic feeder with its **production OpenDSS compile configuration** in both real worktrees, using isolated output directories under `/private/tmp`. Both compile statuses were `passed_compile_only_no_convergence_claim`, and both generated manifests matched their respective exact pins:

```text
Base:      24a723f33e13035def1f3fa68140bf6dc22f1b380d230b44331caadde5b25b2f
Candidate: 04579a8ee748d79b16aec3e1769fea213e27c364f8747359e96bc2b723530956
```

All **seven generated payload hashes** were unchanged and matched the pre-existing payload pins. A complete recursive manifest comparison found only:

1. `/generator/engine_version`;
2. `/source_snapshots/version_file/sha256`;
3. `/source_snapshots/generator_source/sha256`.

The version and generator-source hashes independently matched the corresponding file bytes in each worktree. The generator’s sole source change is its VERSION source hash pin. Thus these two refreshed golden digests are explained by version/source identity; they do not conceal a changed synthetic payload or weakened contract.

My first synthetic-generation attempt failed before generation because the default temporary directory traversed the macOS `/var` symlink. This was a real guard rejection, not a failed model result. Repeating with a resolved `/private/tmp` directory passed. No guard was bypassed.

**Ingress, full-diff coverage and predecessor disposition**

I read the candidate `AGENTS.md`, complete canonical CSV, all four RECRUIT modules, unabridged pinned framework definitions, latest applicable September 8/September 7 handovers and bootstrap, complete external F6/F2F3 charter including §§10–14, programme profile, F6 implementation record, both complete F6 review records, original F2F3 implementation record including its historical failures and remediation, and the candidate implementation record. Earlier memory was used only to locate the historical concerns; the consequential conclusions above were reverified live.

Recorded governing identities:

```text
GWTF CSV:
0cc23891d3328d95e14031e07075d186b43545e4eb0d310303ff3c8d1c2148c1

AGENTS.md:
215dd99e206203b8b859cc0c2b97cf2e0150ea9863a91ccab80a72cabe0f4bcd

External F6/F2F3 charter:
6c5b1a66311b5ef656768e3dc17dd508a41987a89d931babf3605032207f25ae

Programme F2F3_PROFILE.md:
53ebd2bb7d2a30f8962defde983b3756e5f10e6a0d1c0a59d6bd00b3a5733fd7

Unabridged framework file:
c98cb92332e250b82fa5adf21d12c7c816189f626f5b16d10da66ec08e2c20af
```

All **19 changed files** in the subject manifest were reviewed: the three release/documentation surfaces `CHANGELOG.md`, `VERSION`, `pyproject.toml`; finance and pipeline implementation; facade and engine identity; synthetic generator and configuration; changelog fragment, deprecation record and implementation record; and all seven changed test files. I examined the complete base-to-candidate diff and relevant surrounding implementation and consumers.

The migrated old-shape assertions retain their substance: the additive key-set equality stays exact, the taxonomy tail remains ordered, the collision test is inverted and strengthened, timeline length becomes exact, and the headline assertion tests both operating and folded views without the old conditional no-op. Covenant sentinel and balloon tests retain their original behavior assertions and add explicit year/count assertions. The compact `list[float]` contract and exact JSON freeze justify retaining plain lists and placing the deprecation warning on the accessor.

| Predecessor concern | Disposition | Evidence |
|---|---|---|
| F6 helper-only no-bridge test | `CLOSED` | Public `plan_debt([])` tests retained; construction counts 0 and 3 independently exercised. |
| F6 ordering claim | `CLOSED` for current candidate identity | Exact base/candidate key-prefix comparison passed across all 29 evaluated scenarios. |
| F6 overstated “underivable boundary” | `CLOSED` in current explanation | Public row map remains the definitional source; candidate facade explanation is corrected. |
| F6 facade reason covered only two taxonomy keys | `CLOSED` | Revised explanation accounts for no period-indexed route; route count remains 23. |
| Future D3C series routing | `DEFERRED` | Separate contract-coordinator dolphin; unchanged opaque disposition and no HOLD effect. |
| Fold removal could flatter coverage | `CLOSED` for this candidate | Independent exact CEB comparison, both-term tests and retained fold source. |
| Archive-based false-positive mutations | `CLOSED` for this review | Real worktrees; passing before/after mutation controls. |
| Old-shape test weakening | `CLOSED` | Complete changed assertion bodies inspected; focused tests passed. |
| Invalid labels silently becoming ordinals | `CLOSED` at `plan_debt` input for covered invalid labels; `RECURS` at snapshot coherence boundary | Invalid explicit-year tests pass; F2F3-ASR-02 remains. |
| Incomplete data reported compliant | `RECURS` | F2F3-ASR-01 produces an independently reproduced false `PASS`. |
| Historical DOC-02 exemption claim | `CLOSED` | VERSION/pyproject 15.5.0 and explicit covenant/shape impact disclosure. |
| Raw alias migration | `DEFERRED` | Finance-maintenance owner and minimum retention are documented; current alias values remain exact. |

One nonblocking limitation remains in the inherited ordering test: it checks the four-key tail as an ordered list, but the preceding keys through a `set`. Therefore its comment about the complete prefix being guarded “in order” is stronger than the test itself. My independent all-scenario comparison establishes that the **current candidate** preserves the complete prefix. This is an `ACCEPTED_RESIDUAL_WITHIN_SCOPE`, not a claim that the standing test detects arbitrary prefix reordering.

**External state, mutation attestation and limits**

The live GitHub read confirmed protected main at `61c5956…` and issue **#1110 OPEN**. No F2F3 PR existed at that query. F6 merge `e90cfc2` and A1 revert `4082ac5` are ancestors of the candidate; the A1/A2 files checked were absent. I used `git ls-remote` instead of `git fetch` for the reviewer bootstrap because the reviewer role prohibits ref mutation. The initial GitHub read encountered sandbox network failure; the required escalated repeat succeeded.

All **1,540 tracked files** had the same SHA-256 inventory digest before and after independent execution:

```text
9ee672a02b314cffb8b75bf64e2ab0791dc8612154120d307c8adf1b316ff029
```

Every one of the 19 subject blobs matched the frozen manifest at the final check. Final HEAD, tree and merge base remained exactly as stated above; final porcelain status was empty. The native `:memory:.ses` file was absent at the final check. I did not delete it or any repository file. Temporary fixture/output directories were managed by their test/context lifecycles.

`git diff --check 61c5956 HEAD` passed.

The full suite and full local coverage gate were **not run by this reviewer**, because the coordinator was already running the full suite and the assignment expressly prohibited duplication. Hosted required CI and final-head rebind were **not executed by this reviewer**. Author full-suite, mutation and preservation receipts were treated as hypotheses; they are not substituted for the independent results listed here. No full-suite success, hosted-green state or merge authorization is claimed by this disposition.

Both blocking findings require a fresh bounded writer lease, a new frozen candidate and fresh exact-object reviews. F1, A1, A2, fee/tax changes, canon rebaseline, F5-02 and issue #1110’s professional/release/Board/lender/HOLD boundaries remain unchanged.

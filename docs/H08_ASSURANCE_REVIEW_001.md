**ACCEPT — substantive assurance review of the frozen H08 candidate.** The adapter preserves the examined windpowerlib 0.2.2 listing behavior while removing the downcasting warning in pandas 2.3.3. Independent challenges found no blocker within the declared scope. This disposition does **not** bind a later receipt commit or authorize delivery.

```text
reviewer_role: independent assurance
reviewer_identity: /root/h08_assurance; Gibbs; task 01a0843d-7905-7e30-b68c-981838eb5a25
actual_model: gpt-6-astra
actual_reasoning_effort: xhigh
risk_class: R2_LOAD_BEARING
candidate_commit: 00123e4af2f7b8988fb2583fc9a7fc20955d972e
candidate_tree: e3b931d27385701ad90781aa1677201ca24e9875
base_sha: 172af0398e8cd3c8c4622a54504d6d8562cb764b
merge_base_sha: 172af0398e8cd3c8c4622a54504d6d8562cb764b
subject_manifest: SUBJECT_MANIFEST_003.tsv
subject_manifest_sha256: 14368d0c70dd725eb69621a274ee3d4943336f8869fb652bfef8b1c88aab9266
subject_manifest_objects: 31
worktree_and_index: clean
review_scope: listing compatibility, exact table/error behavior, H01 integrity, verification and provenance
disposition: ACCEPT
evidence_yield: EVIDENCE_RETURNED
```

**Identity, recovery and corpus_and_rule_identities.** I independently verified my actual session metadata, including the resumed `turn_context` at line 190, timestamp `2026-09-09T03:56:29.528Z`, which records `gpt-6-astra` and `xhigh`. The parent linkage identifies the separate coordinator/writer task. Project creation evidence names `DutchBay_EPC_Model`; the runtime check independently confirmed Python 3.12.13, the governed persistent environment, and imports from this worktree.

The earlier provider interruption remains **NO_EVIDENCE for a completed disposition** in `REVIEW_INTERRUPTION_001.json`. Following the single authorized retry, I read `RECOVERY_001.json`, reconciled the profiles and all 31 subject blobs, and verified unchanged source, governing-document and installed-oracle hashes. Completed checks below remain attributable to their original tool receipts; no acceptance was inferred from the interrupted attempt. I did not read the other reviewer’s substantive conclusion.

I ingressed the full canonical CSV, unabridged framework definitions, AGENTS, four RECRUIT modules, applicable September 7/8 handovers, H08 profiles and diagnoses, original hygiene report, leases, implementation record, four sourcing test modules, installed upstream source, and mutation programs/results/correction. Bootstrap confirmed **74 active rules**. Key SHA-256 identities independently matched:

| Source | SHA-256 |
|---|---|
| Canonical GWTF CSV | `0cc23891d3328d95e14031e07075d186b43545e4eb0d310303ff3c8d1c2148c1` |
| Pinned framework definitions | `c98cb92332e250b82fa5adf21d12c7c816189f626f5b16d10da66ec08e2c20af` |
| Installed `windpowerlib/data.py` | `99527d395b02430f86770390cb4bf65450dab1b5b19e7799fcfb59adf8e188b4` |
| Packaged turbine CSV | `d379379ba20fe41ec151f74ad5ddf368f9e1cce596756ccea73888d0614c3840` |
| Original hygiene report | `751b8b46ed3210c65ddd53fcdfcffff74a594dc75f8bc8254be09d64abd1d22c` |

All ingress pins, both diagnosis pins, five implementation-program/result pins, initial lease preimages, manifest entries and changed-path membership verified. Manifest 001’s incompleteness is superseded by manifest 003; the candidate itself did not change.

**checks_executed_and_exact_results.** Python commands used `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python`, `PYTHONDONTWRITEBYTECODE=1`, and the active checkout first on `PYTHONPATH`.

| Check and command | Independent result |
|---|---|
| `DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv ./check_venv.sh --no-bootstrap` | PASS; Python 3.12.13, expected prefix and active-worktree imports |
| `DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" PYTHONPATH="$PWD" /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python dutchbay_bootstrap_rules.py` | Exit 0; 74 active rules |
| `python -m pytest -o addopts='' -p no:cacheprovider --no-cov -q --tb=short -W error::FutureWarning tests/wind/test_power_curve_sourcing.py tests/wind/test_power_curve_sourcing_coverage.py tests/wind/test_power_curve_sourcing_skip_integrity.py tests/wind/test_power_curve_sourcing_compatibility.py` | **463 passed in 4.44s**, no warnings or skips |
| `ruff check --no-cache wind_resource/power_curve_sourcing.py tests/wind/test_power_curve_sourcing_compatibility.py tests/wind/test_power_curve_sourcing_skip_integrity.py` | All checks passed |
| `ruff format --check --no-cache` on those same three files | Three files already formatted |
| `mypy --no-incremental --cache-dir=/dev/null --follow-imports=silent wind_resource/power_curve_sourcing.py tests/wind/test_power_curve_sourcing_compatibility.py` | Success, two source files; scoped unused-configuration-section warnings disclosed |
| `git diff --check 172af0398e8cd3c8c4622a54504d6d8562cb764b HEAD` | Exit 0 |
| Original `source_mutation_probe.py wrong_order`, invoked with governed Python | Exit 1, **no pytest summary**, final `AssertionError`: harness failure reproduced |
| Corrected `source_mutation_probe_002.py wrong_order`, invoked with governed Python | Exit 1, **286 failed / 177 passed in 2.47s** |
| `git ls-remote origin refs/heads/main`; scoped GitHub reads | Protected head matched the declared base; issue #1110 OPEN; no H08 PR yet at observation |

The packaged public oracle returned **140 × 4 raw** and **67 × 4 filtered** tables. Candidate and oracle matched exactly, including `RangeIndex(0, 67)`, ordered columns and values, object label dtypes and boolean availability dtypes. Upstream emitted one warning; the candidate emitted zero. Recounting the writer’s matrix independently confirmed **350 successful tables, 57 KeyErrors and 392 baseline FutureWarnings**.

The unchanged manufacturer expression retains case-insensitive regex behavior. Repository-wide `git grep` found only the listing definition and its tests as Python references. AST comparison proved all twelve other production functions/classes unchanged, including the WTG parser whose edit only moves a comment.

**independent_oracles_or_counterexamples.** I constructed a fresh **450-case** matrix using duplicate and named indexes, malformed flags, missing labels, five flag dtypes, empty tables and input permutations. Its oracle executed the installed upstream function’s existing bytecode in a private globals namespace with an in-memory data source. This avoided recreating the filtering algorithm in the new test.

Results were **130 exact DataFrame matches and 320 matching exception types/messages**; candidate calls ran with FutureWarnings as errors. The upstream side emitted 479 FutureWarnings. Inputs, installed function identity, global pandas options and warning filters remained unchanged.

A separately constructed six-row example required **eight ordered outer-merge rows**. This explicitly checks Cartesian duplicate contributions and a coefficient-only turbine.

Six mutations of the actual candidate function were independently rejected, each bracketed by passing controls:

- Collapse the outer merge to a row filter.
- Replace the outer merge with an inner merge.
- Reverse output rows.
- Coerce malformed flags to boolean.
- Restore implicit downcasting.
- Convert availability output columns to object dtype.

I also called the original H01 listing test with an empty result, observed its assertion failure, inserted a deliberate broad-exception-to-skip defect, and observed the real `_without_skip` guard fail. A restored installed-package control passed.

The exact inline programs remain in my session’s tool receipts for owner extraction:

| Programme | Tool-call line | Exact tool-program SHA-256 |
|---|---:|---|
| Independent matrix, six mutants and H01 challenge | 145 | `26eb5742020d5170e478da82a3f43f676301a5ab6ae789beb8b7df4d9a15326c` |
| Provenance verification and ordering-harness replays | 162 | `746a04c7ac27601f7909433ed27b057f05016e6860a21df50d2d3ae5e155475a` |
| Packaged comparison, matrix recount and AST check | 170 | `7a7006641810b6b38ae468f6bdbfbc9b58a8722d748e8e3a74682356c5984f44` |

These checks corroborate the public unfiltered API and existing merge expressions in the [official windpowerlib source](https://windpowerlib.readthedocs.io/en/stable/_modules/windpowerlib/data.html), and the explicit inference approach documented by [pandas](https://pandas.pydata.org/docs/whatsnew/v2.2.0.html#deprecated-automatic-downcasting).

**predecessor_finding_matrix.**

| Finding | Applicability and evidence | Result |
|---|---|---|
| H08 downcasting warning | Exact packaged oracle, strict-warning suite and independent challenges | CLOSED |
| Row-filter duplicate defect | Existing five-row fixture plus independent eight-row Cartesian oracle; row-filter source mutant rejected | CLOSED |
| Malformed flag behavior | Original 57 KeyErrors plus independent matching-error cases; boolean-coercion mutant rejected | CLOSED |
| H01 failure-to-skip | Full integrity module and direct original-test/guard challenge; fixtures alone changed | CLOSED |
| Initial ordering harness | Original failure reproduced before pytest; corrected source mutation demonstrably fails pytest | CLOSED; original attempt remains NO_EVIDENCE |
| Incomplete initial manifest | All 31 manifest-003 objects verified against commit blobs and disk | CLOSED; earlier manifests superseded |

**findings_and_residual_limitations.**

- **ACCEPTED_RESIDUAL_WITHIN_SCOPE:** Compatibility evidence is bounded to the governed Python 3.12.13 / pandas 2.3.3 / windpowerlib 0.2.2 envelope and stated cases. It does not establish every extension dtype or future dependency version.
- **ACCEPTED_RESIDUAL_WITHIN_SCOPE:** Historical preparation evidence reported 306 baseline synthetic warnings. The current implementation matrix independently produces 392, as its current record states; I do not adopt the earlier count as current evidence.
- **ACCEPTED_RESIDUAL_WITHIN_SCOPE:** Local full suite, coverage, QSTS and qualification were **not run** under the capacity/scope restriction. Black, isort and pre-commit were not independently repeated in this read-only review; their writer receipts are distinguished from my executed checks.
- **DEFERRED_TO_NAMED_DOLPHIN:** H08 coordinator owns receipt insertion, final-head rebind, capacity reconciliation and exact-head hosted gates. Those are subsequent delivery steps, not missing substantive-adapter evidence. No HOLD is lifted.

**hold_and_authority_effect.** This accepts only the named substantive candidate and manifest. Both reviewers must separately rebind after the named receipt-only commit, proving unchanged subject blobs and accurate receipts. Issue #1110 and all professional, lender, Board, release, evidence and other HOLD boundaries remain unchanged. I exercised no merge, publication, issue-closure or release authority.

**mutation_attestation.** No repository source, index, ref, installed-package file, shared environment or external evidence artifact was changed. Source mutants and dependency seams existed only in process memory and were restored; focused pytest used its ordinary temporary fixtures. Final verification found the same clean candidate/tree and all 31 subject blobs unchanged.

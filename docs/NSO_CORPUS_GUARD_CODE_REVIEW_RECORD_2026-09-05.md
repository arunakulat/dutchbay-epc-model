# NSO corpus manifest guard — independent CODE / CI review record

RECRUIT-01 independent reviewer, code and CI mandate. 2026-09-05.

> **COORDINATOR NOTE — appended 5 September 2026. The reviewer's record below is unaltered.**
>
> **1. The disposition is bound to a superseded SHA, and I am the reason.** The reviewer was
> recruited against `3e4b79f` and told the tree was frozen. It was not: CI went red on that
> commit while the review was running, and under this session's drive-to-green obligation I
> pushed `4ac60d9` and then edited the tree again while the reviewer was still working. The
> reviewer detected both events from the reflog and file mtimes and recorded them in §0.1/§0.2.
> That is a `RECRUIT-01` breach on my part — a writer moving a tree under a read-only reviewer —
> and it is recorded here rather than quietly absorbed. The right move would have been to tell
> the reviewer the freeze had broken.
>
> **2. Every finding is addressed, at SHAs this record does not cover.** B1 and B2 were fixed in
> `4ac60d9` before this record was written; B1's fix is the reviewer's own proposed remedy
> (derive the spans from the manifest at run time), which also removes B3's root cause. B3's
> residual — `--showlocals` printing the clause out of the test's locals — plus A1, A2, A3, A4,
> A7, A8, A9 and A10 were fixed afterwards. A5 and A6 fall out of the B1 remedy: deleting the
> clause from its home now fails the guard rather than passing it, and a derived span cannot
> drift from its source. A11 is proved closed: a planted failure with `--showlocals` active
> prints zero clause fragments.
>
> **3. There is no second round.** The project owner limited this change to one `RECRUIT-01`
> round. The post-`3e4b79f` work is therefore **unreviewed**, and this record must not be read as
> accepting it. Each fix carries its own reproduced-failure receipt in the commit that made it.
>
> **4. One matter the reviewer correctly refused to adjudicate.** The failing run put a fragment
> of clause 6 into a public GitHub Actions log — `arunakulat/dutchbay-epc-model` run
> `33959805520`, job `101289585809`. The guard has been changed so this cannot recur, but the
> existing log is a live disclosure and its handling is the project owner's decision, not mine.
> It is raised with the owner directly.

## 0. DISPOSITION

REJECT

- **Candidate head:** `3e4b79f1898bd7a2ec10064e6a7941757ebc5160` (branch `claude/nso-25x10-bess-tender-8ehomm`, PR #1233)
- **Base:** `1240a9ae0f300a2379825970cd38583f50948631` (`origin/main`)

This disposition binds to that exact commit and tree and **transfers to no other tree,
implementation or base**. Any further delta — including a fix for the findings below —
requires a fresh SHA-bound review. Acceptance is not implied for any part of the change by
the fact that a finding is recorded as advisory rather than blocking.

The rejection rests on receipts, not judgement: the candidate turns **two** GitHub Actions
jobs red, one of them (`fastlane`) the very job this change wires the new guard into and a
context the repository's own records name as required. Both failures are reproduced below
locally, in a runner-equivalent shallow clone, and in the actual Actions logs of this PR.

### 0.1 TARGET DRIFT DURING REVIEW — the candidate tree was not frozen

**The branch moved while this review was in progress.** I was dispatched against a frozen
`3e4b79f`. At `2026-09-05 10:21:19 +0000`, partway through my verification, a new commit landed on
`claude/nso-25x10-bess-tender-8ehomm`:

```
$ git reflog -3
4ac60d9 HEAD@{0}: commit: fix(nso): derive the clause-6 search terms from the manifest, and black-format
3e4b79f HEAD@{1}: commit: fix(nso): state the offer handling once, and give the corpus a test
a7dbbad HEAD@{2}: reset: moving to HEAD
$ git log -1 --format='%an <%ae> %ad' 4ac60d9
Claude <noreply@anthropic.com> Sat Sep 5 10:21:19 2026 +0000
$ git rev-parse 3e4b79f^{tree}   -> 9eaa2d7620d95a9b76f3ea31544faf9eb4f92e84
$ git rev-parse 4ac60d9^{tree}   -> dc2eca627c416fd13f861f8dc87b22e1b572a3f6
$ git diff --stat 3e4b79f 4ac60d9
 .../nso-corpus-manifest-integrity-guard.added.md   | 14 +++-
 tests/lint/test_nso_corpus_manifest_integrity.py   | 86 ++++++++++++++++------
```

**I did not create this commit.** I ran no `git commit`, `git add`, `git checkout`, `git reset` or
any other mutating git command in this repository; the reflog attributes it to the implementation
worker. RECRUIT-01 requires that reviewers be dispatched only *after* the candidate tree is frozen,
and names unexpected writer activity during review as an event that returns the chain to
`READ_ONLY` and revokes continuity. Recording it here as required.

**Consequences for this record, stated precisely:**

1. **My disposition is unaffected and still binds to `3e4b79f`.** Every receipt in §3 is either
   SHA-addressed (`git grep <sha>`, `git show <sha>:`, `git archive <sha>`), taken from a clone
   pinned at `3e4b79f`, or taken from the GitHub Actions run of PR #1233 at that head. After
   discovering the drift I re-derived the formatter receipts against the pinned blob
   `3e4b79f:tests/lint/test_nso_corpus_manifest_integrity.py` (`4ff74aab7d2099cbd798b08ad72e8ee4b2766567`)
   rather than the working tree, and they are unchanged (§3.10).
2. **`4ac60d9` is NOT reviewed and this disposition does not extend to it.** Spot-checking only, so
   the coordinator knows where things stand: at `4ac60d9`, `black --check` reports "1 file would be
   left unchanged" and `git grep` for the clause-6 span returns only the offers manifest — i.e. B1
   and B2 appear to have been addressed by that commit. **That is an observation, not an
   acceptance.** I have not read its diff, not re-run the mutation suite against it, not checked
   whether B3 and advisories A1–A11 survive, and not seen a CI run on it. The base fast-forward
   carve-out does not apply: this is a change to the candidate's own tree, which RECRUIT-01 says
   "still requires a fresh review with no exception".
3. A fresh SHA-bound code/CI review of `4ac60d9` (or of whatever head is frozen next) is required
   before merge, and it should treat the advisories below as open unless it verifies otherwise.

### 0.2 SECOND DRIFT EVENT — the tree was still being written as this record was finalised

The drift was not a single commit. While writing §6 I found the candidate file **modified in the
working tree**, uncommitted, timestamped seconds earlier:

```
$ git status --short
 M tests/lint/test_nso_corpus_manifest_integrity.py
?? docs/NSO_CORPUS_GUARD_CODE_REVIEW_RECORD_2026-09-05.md
$ stat -c '%y  %n' tests/lint/test_nso_corpus_manifest_integrity.py
2026-09-05 10:24:21.691743921 +0000  tests/lint/test_nso_corpus_manifest_integrity.py
$ date -u '+%F %T UTC'
2026-09-05 10:24:34 UTC
$ git diff --stat tests/lint/test_nso_corpus_manifest_integrity.py
 1 file changed, 65 insertions(+), 45 deletions(-)
```

**These edits are not mine.** I wrote nothing to that path at any point; my only write in this
repository is this record. The content identifies the author unambiguously as the implementation
worker acting on review findings in flight — the uncommitted diff introduces
`ENTRY = re.compile(r"([0-9a-fA-F]{64}) [ *](.*)")` with a comment about binary-mode `-b` and
upper-case digests being "accepted by `sha256sum -c`, so rejecting them here would fail a manifest
the tool itself verifies" (advisory **A2**), `text.lstrip("\ufeff")` (A2, BOM), a comment that
"Do NOT strip beyond that: a path with trailing whitespace would be silently rewritten"
(advisory **A3**), and a rewrite of the `refresh_corpus_manifest.py` remediation string
(advisory **A1**).

So at the time of writing, the branch has moved once by commit and is being edited again
uncommitted. This is the condition RECRUIT-01 describes as target drift and unexpected writer
activity during a review: the reviewed object is not frozen. I have not reviewed these uncommitted
edits, they form no part of this record, and none of them changes my disposition — which binds to
`3e4b79f` and to nothing else. The coordinator should freeze a head and re-dispatch.

## 1. Scope and mandate

**Assessed:** `tests/lint/test_nso_corpus_manifest_integrity.py`; the `fastlane` step added to
`.github/workflows/ci_v14_fastlane.yml`; the workflow-behaviour and CI claims made in the
commit message, in the added `AGENTS.md` prose, in the module docstring, and in
`changelog.d/nso-corpus-manifest-integrity-guard.added.md`; the guard's ability to fail on each
defect it claims to catch; its false-positive surface; its `sha256sum`-format parsing; its fit
with `tests/lint/` convention and its cost in the fastlane lane.

**Not assessed (other reviewer's lane, or out of mandate):**

- The substance of the documentation consolidation across `docs/source_materials/nso_bess_250mw_2026/README.md`,
  `.../source_packages/README.md`, `changelog.d/nso-commercial-offer-resupply.fixed.md` and
  `docs/..._RESUPPLY_DOCUMENTATION_REVIEW_RECORD_2026-09-04.md` — whether the single-source
  statement is *correct*, whether the paraphrases on the review record are adequate, and whether
  the disclosure decision itself was right.
- The evidence-handling and provenance questions around the offer package.
- Whether the four manifest defects between #1226 and #1234 are correctly characterised.
- The AGENTS.md prose as documentation; I assessed only its factual claims about what CI now does.
- Finance, KPI and domain correctness — no such surface is touched.
- The 5 known `test_cloud_audit_review_sandbox.py` failures the commit message sets aside.

One out-of-mandate observation is noted at the end of §4 because it is a direct consequence of a
blocking code finding and concerns published material.

## 2. What the candidate changes, in my own words

1. **A new guard, `tests/lint/test_nso_corpus_manifest_integrity.py` (272 lines, 6 test functions
   / 7 parametrised items).** It classifies the corpus manifests into two declared sets —
   `IN_REPO_MANIFESTS` (subject files committed here) and `EXTERNAL_MANIFESTS` (subject files held
   outside this repository) — deliberately declaring rather than inferring, so that a genuinely
   missing file cannot be mistaken for a by-design absent one. Over the in-repo set it runs the
   `sha256sum -c` direction (every recorded entry present and hashing as recorded). It then adds
   the direction `-c` cannot see: every file git tracks under the corpus must appear in the parent
   manifest. It also asserts that the parent manifest's pin of each nested manifest is current,
   that no nested manifest sits unclassified, that the single-source handling anchor
   `NSO250MW-OFFERS-HANDLING-2026-09-04` is defined in the offers manifest and cited by three named
   referrers, and — via `git grep` over three hard-coded verbatim spans — that clause 6 of the
   Envision offers appears in no file but the offers manifest.

2. **A `fastlane` step** running only that module, placed there rather than in the sharded suite
   because `test-suite.yml` skips its pytest shard for docs-only diffs.

3. Documentation consolidation across four files, plus an `AGENTS.md` amendment turning a
   "three ways a corpus commit goes wrong" checklist into four and asserting that CI now catches
   most of them, plus a changelog fragment.

The design intent is sound and, on the parts I could test, the mechanism does what it claims. The
problem is that the guard does not pass on the tree that introduces it.

## 3. Verification log

All commands run from `/home/user/dutchbay-epc-model` unless stated. Nothing in the candidate tree
was modified; every mutation was performed on a throwaway clone under the scratchpad.

### 3.1 The `sha256sum -c` blindness claim at `782c958` — VERIFIED, exactly

Reconstructed the corpus at that commit with `git archive` (no checkout, no working-tree change):

```
$ git ls-tree -r --name-only 782c958 -- docs/source_materials/nso_bess_250mw_2026/ | wc -l
131
$ git show 782c958:docs/source_materials/nso_bess_250mw_2026/MANIFEST.sha256 | grep -c '^[0-9a-f]\{64\}  '
119
```

Set difference (tracked − recorded − the manifest itself):

```
     1	README.md
     2	oem/envision/compliance_evidence/README.md
     3	oem/envision/extracted/DC_Sri_Lanka_10MW_40MWh_35C.markitdown.md
     4	oem/envision/extracted/README.md
     5	oem/envision/extracted/Standards_Compliance_List.markitdown.md
     6	oem/envision/product_docs/README.md
     7	reviews/NSO250MW_Checklist_Package_Ingress_Evaluation_2026-08-21.md
     8	source_packages/NSO250MW_checklist_2026-08-21.MANIFEST.sha256
     9	source_packages/README.md
    10	third_party/README.md
    11	third_party/extracted/Technical_Requirement_Lakdhanavi_v1.markitdown.md
=== unrecorded count ===
11
=== recorded minus tracked ===   (empty)
```

And `sha256sum -c` against that reconstructed tree:

```
=== files extracted ===
131
EXIT CODE: 0
--- OK lines: 119 ---
--- FAILED lines: 0 ---
--- stderr ---   (empty)
```

**Verdict: the claim is true and materially demonstrated.** `sha256sum -c` returned `119/119 OK`,
exit 0, on a corpus with eleven tracked files it never looked at. The commit message's "130
tracked" is the tracked count *excluding the manifest itself* (`git ls-tree` reports 131); that is
the right denominator for the guard's own arithmetic and is not a misstatement, though it is worth
noting that "130 tracked" and `git ls-tree | wc -l` do not agree numerically.

`sha256sum -c 138/138 OK, exit 0` on the candidate head is also verified (138 entries, 0 comment
lines, 139 tracked = 138 + the manifest).

### 3.2 The guard on its own commit — FAILS

```
$ python -m pytest tests/lint/test_nso_corpus_manifest_integrity.py -q
...
FAILED tests/lint/test_nso_corpus_manifest_integrity.py::test_clause_six_is_quoted_in_exactly_one_file
1 failed, 6 passed, 1 warning in 1.07s
```

Cause: `CLAUSE_SIX_SPANS` stores three verbatim spans of clause 6 as string literals in the guard
itself, and `git grep` finds them there once the file is tracked.

```
$ git grep --name-only --fixed-strings "<CLAUSE_SIX_SPANS[0]>" -- .
docs/source_materials/nso_bess_250mw_2026/source_packages/NSO250MW_Commercial_Offers_2026-09-03.MANIFEST.sha256
tests/lint/test_nso_corpus_manifest_integrity.py
```

(The spans are not reproduced in this record. That is the point of the finding.)

The same holds when grepping the committed tree object directly, so this is a property of the
commit and not of my working copy:

```
$ git grep --name-only --fixed-strings "<span 0>" 3e4b79f1898bd7a2ec10064e6a7941757ebc5160 -- .
3e4b79f…:docs/source_materials/…/NSO250MW_Commercial_Offers_2026-09-03.MANIFEST.sha256
3e4b79f…:tests/lint/test_nso_corpus_manifest_integrity.py
```

### 3.3 Runner simulation — the shallow-clone hypothesis is DISPROVEN; the failure is not

`actions/checkout@v7` is shallow by default. I reproduced that exactly:

```
$ git clone --depth 1 --branch claude/nso-25x10-bess-tender-8ehomm file:///home/user/dutchbay-epc-model <scratch>/shallow
$ git rev-parse HEAD                 -> 3e4b79f1898bd7a2ec10064e6a7941757ebc5160
$ git rev-parse --is-shallow-repository -> true
$ git log --oneline | wc -l          -> 1
$ git ls-files -- docs/source_materials/nso_bess_250mw_2026 | wc -l -> 139
$ git grep --name-only --fixed-strings "<span 0>" -- .   -> rc=0, 2 files
```

`git ls-files` and `git grep` (working-tree mode, no revision argument) read the **index and
working tree**, not history, so `fetch-depth: 1` does not affect them. The candidate's use of both
is safe under `actions/checkout@v7`. **This was the brief's leading hypothesis for a CI break and
it is wrong.** The break is elsewhere:

```
$ cd <scratch>/shallow && python -m pytest tests/lint/test_nso_corpus_manifest_integrity.py -q
1 failed, 6 passed in 1.33s
EXIT: 1
```

### 3.4 The actual GitHub Actions result for this PR — CONFIRMS both failures

`fastlane` on PR #1233, job `101289585809`, conclusion **failure**:

```
tests/lint/test_nso_corpus_manifest_integrity.py:267: AssertionError
FAILED tests/lint/test_nso_corpus_manifest_integrity.py::test_clause_six_is_quoted_in_exactly_one_file
1 failed, 6 passed in 2.02s
##[error]Process completed with exit code 1.
```

`Code Quality Checks`, job `101289585999`, conclusion **failure**:

```
Oh no! 💥 💔 💥
1 file would be reformatted, 743 files would be left unchanged.
##[error]Process completed with exit code 1.
```

The reformat diff in that log is entirely within the new module (the `_entries` digest/duplicate
assertions and the `key in recorded` assertion). Reproduced locally:

```
$ .venv/bin/black --check --diff tests/lint/test_nso_corpus_manifest_integrity.py
-        assert key in recorded, (
-            f"the parent manifest does not pin nested manifest {key}"
-        )
+        assert (
+            key in recorded
+        ), f"the parent manifest does not pin nested manifest {key}"
EXIT: 1
```

while `ruff check`, `ruff format --check` and `mypy --follow-imports=skip` on the same file are all
clean, and `isort --check-only` is clean too (exit 0). black 26.5.1 and ruff-format genuinely
disagree on this construct — black's own output is rejected by `ruff format --check` (§3.10) — but
only `black` is a gate here.

That gate is mandatory and it feeds the required summary check:

```
$ grep -n "black\|Lint" .github/workflows/test-suite.yml
328:    - name: Run black (mandatory gate)
331:      run: black --check --diff .
435:        gate "Lint" "${{ needs.lint.result }}" "the ruff/black/isort/mypy gate failed"
```

so a black failure fails the `lint` job, which fails `Test Summary`.

### 3.5 How "harness 7/7 passed" was obtained — reproduced

The commit message's receipt is reproducible only with the guard file **untracked**:

```
$ git rm --cached -q tests/lint/test_nso_corpus_manifest_integrity.py   # on the throwaway clone
$ git grep --name-only --fixed-strings "<span 0>" -- .
docs/source_materials/…/NSO250MW_Commercial_Offers_2026-09-03.MANIFEST.sha256      # 1 file
$ python -m pytest tests/lint/test_nso_corpus_manifest_integrity.py -q
7 passed in 1.31s
```

`git grep` does not search untracked files. The green run was real; it was a run of a state CI
never sees. This is precisely the VERIFY-01 distinction the mandate names — the receipt proved the
*presence* of a passing run, not the *truth* of the proposition "this module passes on the
committed tree."

### 3.6 Mutation testing — every assertion can fail (9/9)

Performed on the throwaway clone, each file backed up and restored from my own copy, never from
git. Every mutation produced the expected failure:

| # | Injected defect | Target assertion | Result |
|---|---|---|---|
| M1 | recorded file deleted | direction 1 `missing` | FAILED |
| M2 | recorded file content altered | direction 1 `altered` | FAILED |
| M3 | new unclassified `*.MANIFEST.sha256` in `source_packages/` | `unclassified` | FAILED |
| M4 | declared nested manifest removed from disk | `vanished` | FAILED |
| M5 | tracked corpus file absent from manifest | direction 2 `unrecorded` | FAILED |
| M6 | nested manifest edited, parent pin not refreshed | `stale` | FAILED |
| M7 | parent drops its pin line for a nested manifest | `does not pin` | FAILED |
| M8 | handling anchor renamed in the offers manifest | anchor assertion | FAILED |
| M9 | a referrer stops citing the anchor | `orphaned` | FAILED |
| M10 | genuine extra copy of clause 6 (as wrapped in the manifest) | clause-6 test | FAILED |
| M11 | reflowed/unwrapped copy of clause 6 | clause-6 test (span 1) | FAILED |

`git status --short` on the clone was empty after the sequence, i.e. every mutation was restored.

**The commit message's claim that each failure mode was reproduced and confirmed to fail its
assertion is TRUE and I independently confirm it.** The guard is not decoration. This is the
strongest thing in the change and it should survive whatever remediation follows.

One mutation that *should* have failed did not:

```
M13: delete the entire clause-6 quotation from the offers manifest
     -> 1 passed
```

### 3.7 `sha256sum` format parsing

Fed `_entries` the formats GNU coreutils actually emits and accepts:

```
1 text mode (2 spaces)               -> ACCEPTED
2 BINARY mode (sha256sum -b)         -> REJECTED  "not a sha256sum entry"
3 CRLF line endings                  -> ACCEPTED
4 UTF-8 BOM                          -> REJECTED  "malformed digest '﻿aaa…'"
5 comment + blank lines              -> ACCEPTED
6 duplicate path                     -> REJECTED  "duplicate entry for file.txt"
7 path with a space                  -> ACCEPTED  {'dir/My File.pdf': …}
8 path with LEADING space            -> ACCEPTED  {' leading.txt': …}      (preserved)
9 path with TRAILING space           -> ACCEPTED  {'trailing.txt': …}      (SILENTLY STRIPPED)
10 UPPERCASE digest                  -> REJECTED  "malformed digest 'AAA…'"
11 backslash-escaped name            -> REJECTED  "malformed digest '\\aaa…'"
12 path with 2 consecutive spaces    -> ACCEPTED  {'dir/two  spaces.txt': …}
```

Cross-checked against the tool the manifests are generated by:

```
$ sha256sum f.txt | awk '{print toupper($1)"  "$2}' > M.up && sha256sum -c M.up
f.txt: OK          sha256sum -c exit: 0
$ sha256sum -b f.txt > M.bin && sha256sum -c M.bin
f.txt: OK          exit: 0
```

So `sha256sum -c` accepts uppercase digests and binary-mode `*` entries; the guard rejects both.
Two-space separator, CRLF, comment lines, blank lines and duplicate detection are all handled
correctly, and `partition("  ")` correctly takes the first occurrence so a path containing two
consecutive spaces is parsed intact.

### 3.8 Convention, cost and wiring

```
$ grep -l "pytestmark" tests/lint/*.py | wc -l     -> 0   (of 35 modules)
$ grep -l "subprocess" tests/lint/*.py | wc -l     -> 13  (incl. the new module)
```

`tests/lint/test_ci_driver_targets_exist.py` opens with the identical `"""CESSPIT ... guard:`
docstring form and the identical `REPO_ROOT = Path(__file__).resolve().parents[2]` idiom;
`test_gwtf_canonical_source.py` uses the same module-constant-then-plain-function shape. Shelling
out to git is established practice in this directory. **Placement in `tests/lint/` is correct by
this repository's conventions.** TEST-01 (finance regression pins) and TEST-03 (bounded stochastic
evaluations) do not bear on where this test lives; neither is engaged by the change.

Cost:

```
full module run          real 1.990s
--collect-only           real 1.038s     (pytest startup + tests/conftest.py import)
python -c "import libcst, yaml, analytics"   real 0.218s
```

Corpus is 72 MB across 139 tracked files; direction 1 hashes the 138 recorded entries once.
**Fast enough for fastlane, and it does not hash more than it needs to** — it hashes exactly the
recorded set, which is what the gate it replaces does. Roughly half the wall time is pytest
startup, not the guard.

`test-suite.yml`'s docs-only skip is real and works as described:

```
          case "$f" in
            *.md) ;;            # markdown anywhere (README, CHANGELOG, memory docs)
            changelog.d/*) ;;   # changelog fragments (incl. deletions on flush)
            docs/*) ;;          # docs tree
            *) code=true; break ;;
          esac
...
    - name: Skip note (docs-only PR)
      if: needs.changes.outputs.code_changed != 'true'
```

`ci_v14_fastlane.yml` has no path filter and no `if:` on the job or the new step, so `fastlane`
does run on every PR into `main`. **The rationale for placing the guard in fastlane rather than the
sharded suite is sound and I endorse it.**

### 3.9 The remediation the guard prints

```
$ ls -la scripts/analysis/refresh_corpus_manifest.py
-rw-r--r-- 1 root root 2717 Aug 29 04:29 scripts/analysis/refresh_corpus_manifest.py
```

The script exists. But the direction-2 failure message says "**Add them with**
`scripts/analysis/refresh_corpus_manifest.py`", and that script's docstring says it "refuses to
touch a path that is not already in the manifest, so it cannot be used to quietly add an
unrecorded file." Following the advice verbatim:

```
$ python scripts/analysis/refresh_corpus_manifest.py <corpus>/MANIFEST.sha256 NEW_EVIDENCE.md
refusing to add an unrecorded path: NEW_EVIDENCE.md
This tool only refreshes hashes already in the manifest.
EXIT: 1
```

### 3.10 Which formatters are actually gates

```
.github/workflows/test-suite.yml:328:    - name: Run black (mandatory gate)
.github/workflows/test-suite.yml:331:      run: black --check --diff .
.github/workflows/test-suite.yml:333:    - name: Run isort (mandatory gate)
.github/workflows/test-suite.yml:336:      run: isort --check-only --diff .
.pre-commit-config.yaml: black, ruff (check), isort --profile=black
```

`ruff format` appears in neither. The `fastlane` job runs `ruff check` and `mypy` over a focused
five-file surface that does not include `tests/`. So the new module's formatting is policed by
`black` alone, and it fails that check.

## 4. Findings

### BLOCKING

**B1 — The guard fails on the commit that introduces it, turning the `fastlane` job red.**

*What is wrong.* `CLAUSE_SIX_SPANS` (module lines 82–86) stores three verbatim spans of clause 6 as
Python string literals. `test_clause_six_is_quoted_in_exactly_one_file` then runs `git grep` for
each span across tracked files and asserts the only match is the offers manifest. Once the module
is committed it is itself a tracked file containing all three spans, so `git grep` returns it and
the assertion fails. The guard is a self-referential contradiction: it can only pass while it is
not part of the repository it guards.

*Why it matters.* This is not a style problem or a latent risk — it is the observed state of the
PR. `fastlane` is `failure` on the real run (job `101289585809`, `1 failed, 6 passed in 2.02s`,
exit 1), reproduced identically here and in a runner-equivalent shallow clone. The repository's own
session handovers name `fastlane` among the required contexts (`docs/SESSION_HANDOVER_2026-08-24_3.md:72`:
"required contexts remain `Test Summary`, `fastlane` and `smoke`"), so this blocks merge outright.
Worse in kind: a guard that is red from birth trains reviewers to treat that lane's red as expected
noise, which is the failure mode CESSPIT exists to prevent. And the AGENTS.md prose added in the
same commit asserts in the present tense that "CI now catches most, but not all, of what follows" —
that sentence is false at this SHA.

*Proposed remedy.* Do not store the spans in source at all. Derive them at run time from the single
home: read `OFFERS_MANIFEST`, extract the quoted clause-6 block from the `# 3. CLAUSE 6, VERBATIM.`
header section, strip the `#` continuation prefixes, and search for the resulting line fragments.
The guard then carries no copy of the clause, self-updates if the clause text is ever corrected, and
`elsewhere` needs to exclude only the home file. Do **not** remedy this by adding the guard's own
path to the exclusion set — that keeps a verbatim copy of the confidentiality clause in the public
repository and merely silences the detector (see B3).

**B2 — `black --check` fails on the new module, turning `Code Quality Checks` red.**

*What is wrong.* The module uses the parenthesised-message `assert cond, (\n "msg"\n)` form in three
places. `ruff format` accepts it; `black` 26.5.1 rewrites it to `assert (\n cond\n), "msg"`. The
repository runs both — `ruff format` is not a substitute for `black` here.

*Why it matters.* `Code Quality Checks` is `failure` on the real run (job `101289585999`,
"1 file would be reformatted, 743 files would be left unchanged"), and the reformat diff is
entirely within the new file, so this is a regression introduced by this commit and not
pre-existing drift. `black --check --diff .` is an explicitly **mandatory** gate in that job
(`test-suite.yml`: "MANDATORY (no '|| true' ...): black --check now blocks the merge on any
un-black'd file"), and the `Test Summary` job gates on it directly —
`gate "Lint" "${{ needs.lint.result }}" "the ruff/black/isort/mypy gate failed"` — so **this
failure blocks merge through `Test Summary`, which the repository's records name as a required
check.** B2 is merge-blocking independently of B1.

Under VERIFY-01 there is a second problem: the commit message's receipt line declares "ruff check
and ruff format clean; mypy clean" and is silent on `black`. A check that was not run must be
*declared* as not run, not omitted; here the omitted check is the one that is red. `ruff format` is
neither a CI gate nor a pre-commit hook in this repository, so it is not a substitute receipt for
the gate that actually runs.

*Proposed remedy.* Run `black tests/lint/test_nso_corpus_manifest_integrity.py` and commit the
result. Note that `ruff format --check` **rejects** black's preferred output for these constructs —
I verified this rather than assuming it:

```
$ black -q <copy>.py && ruff format --check <copy>.py
Would reformat: <copy>.py        ruff exit: 1
$ black --check <copy>.py
1 file would be left unchanged.
```

The two formatters are in genuine mutual conflict on the parenthesised-assert-message form. This
does not create a deadlock, because CI and `.pre-commit-config.yaml` run `black`, `ruff check` and
`isort` — **not** `ruff format`; so black wins and the file should be black-formatted. If the author
wants both tools to agree, restructure the three assertions so neither reformats them (e.g. assign
the message to a local first, or shorten it to fit on one line). `isort --check-only` is already
clean on the file (exit 0). Add `black --check` to the commit's declared receipts.

**B3 — The change adds a verbatim copy of the confidentiality clause to the public repository, in
the commit whose stated purpose is to reduce it to one copy.**

*What is wrong.* Independently of B1's CI consequence, `tests/lint/test_nso_corpus_manifest_integrity.py`
now contains three verbatim fragments of clause 6 in a public repository. The commit message states
"Clause 6 ... is quoted in exactly one file"; at this SHA it is in two, and the second one is the
guard that asserts there is only one.

*Why it matters.* The clause is the instrument that forbids third-party communication of the offer,
and the repository is public. This is the exact class of defect the change exists to close, and item
3 of the amended AGENTS.md checklist ("a review record can re-publish what the fix removed") names
it. It has already had a real consequence: because B1 makes the test fail, and because
`addopts` in `pyproject.toml` includes `--showlocals`, the assertion message *and* the local
variable `span` are now printed in the **public GitHub Actions log** for this PR — the run log I
retrieved contains a clause-6 fragment in plain text. The guard has published the material it was
written to keep unpublished.

*Proposed remedy.* The B1 remedy (derive the spans from the manifest at run time) resolves this too
and is the reason to prefer it over an exclusion list. Separately, once the spans are no longer
literals, keep the failure message free of the matched text — report the offending file paths and
a span index, not the span — so that a future genuine failure does not republish the clause into a
public log. Whether the Actions log for the current run needs handling is an
**out-of-mandate** matter I flag for the coordinator and the documentation/evidence reviewer rather
than adjudicate: the run is `arunakulat/dutchbay-epc-model` run `33959805520`, job `101289585809`.

### ADVISORY

**A1 — The direction-2 failure message sends the operator to a tool documented to refuse the
operation.** The message says "Add them with `scripts/analysis/refresh_corpus_manifest.py`"; that
script raises `SystemExit("refusing to add an unrecorded path: …")` by design (verified, §3.9). A
developer who hits the guard and follows its instruction is stuck. *Remedy:* point at the actual
procedure for adding an entry (regenerate the manifest, or state the `sha256sum >>` + re-verify
sequence), or extend the script with an explicit `--add` mode and cite that.

**A2 — The parser is stricter than `sha256sum -c` in two ways that can legitimately arise, and one
of its messages is factually wrong.** Binary-mode lines (`<digest> *<path>`, emitted by
`sha256sum -b`) are rejected with "not a sha256sum entry" — but they *are* a sha256sum entry, and
`sha256sum -c` accepts them (§3.7). Uppercase digests are likewise accepted by `-c` and rejected
here. A BOM is reported as a "malformed digest". Backslash-escaped filenames (the format coreutils
uses for names containing `\` or newline) are rejected. These all fail loud, which is CESSPIT-correct,
but they are false positives against manifests that `sha256sum -c` would pass, and a future
regeneration with `-b` would turn fastlane red with a misleading diagnosis. *Remedy:* parse with
`re.fullmatch(r"([0-9a-fA-F]{64}) [ *](.*)", line)`, lower-case the digest, and strip a leading BOM
on the first line.

**A3 — `raw.strip()` silently mutates recorded paths.** A manifest entry for a path with trailing
whitespace is parsed as the path without it (§3.7 case 9). That is a silent wrong answer rather than
a loud failure: the guard then hashes a different file than the manifest names, or reports a present
file missing. *Remedy:* strip only the line terminator (`raw.rstrip("\r\n")` or `.splitlines()`
alone, which already removes it), never the path.

**A4 — `found.stdout.split()` splits on whitespace where it must split on lines.** `git grep
--name-only` emits one path per line and does not quote plain spaces. This repository already
contains tracked paths with spaces — `legacy/dev_scripts/AAA - instructions for make clean zip.md`
and `legacy_scripts/archive/.../validate (1).sh` — so if a clause-6 span ever appeared in such a
file, its path would be shredded into several bogus tokens and the failure message would name files
that do not exist. If the *home* path ever acquired a space, `home` would never match and the test
would fail unconditionally. Latent today, cheap to fix. *Remedy:* `found.stdout.splitlines()`, or
pass `-z` and split on `\0`.

**A5 — The test name overstates what it asserts, and the gap is real.** `test_clause_six_is_quoted_in_exactly_one_file`
asserts *at most* one: deleting the clause entirely from the offers manifest leaves the test green
(mutation M13, §3.6). The docstring is honest ("It belongs in one place, or nowhere"); the name is
not. Since `test_offer_handling_is_stated_once` already asserts the *anchor* is present in its home,
the same treatment for the clause is one line. *Remedy:* rename to `..._is_quoted_in_at_most_one_file`,
or assert presence in the home file and keep the name.

**A6 — One of the three spans never matches its declared home.** `CLAUSE_SIX_SPANS[1]` spans a line
break in the offers manifest (the clause is wrapped with `#       ` continuation prefixes), and
`git grep` is line-oriented, so it matches zero lines there:

```
$ grep -c "<span 1>" …/NSO250MW_Commercial_Offers_2026-09-03.MANIFEST.sha256
0
```

It is not dead — it catches a *reflowed* copy elsewhere (mutation M11) — but the docstring's
premise that the spans are "quoted verbatim in the offers manifest" is untrue for this one, and
nothing in the module would notice if a span silently stopped corresponding to the source text.
*Remedy:* falls out of the B1 remedy — derived spans cannot drift from their source. Otherwise, add
an assertion that each span (or its reflowed equivalent) is found in the home file.

**A7 — Classifying a manifest as `EXTERNAL` leaves its *contents* checked by nothing.** The
`EXTERNAL_MANIFESTS` tuple is used only as a set of declared paths in
`test_every_nested_manifest_is_classified`; those manifests are never passed through `_entries`, so
a malformed digest, a duplicate entry or a corrupted line in the 21-August checklist manifest or the
offers manifest is not detected. Their bytes are pinned by the parent, which catches tampering, but
not malformedness at the moment of authoring. This partially undercuts the docstring's claim that
classification is what prevents "a manifest ... covered by nothing at all". *Remedy:* run `_entries`
over the external manifests too (parse-and-validate without resolving paths against the tree) — it
is the same function and costs nothing.

**A8 — "needs only stdlib + git" and "~1s" are both inaccurate.** The workflow comment and the
changelog fragment both make these claims. Running the module under pytest imports
`tests/conftest.py`, which imports `libcst`, `yaml` and the `analytics` package (which pulls the
scientific stack); collection alone costs 1.04 s of the 1.99 s total (§3.8). The step is still
comfortably fast, but it depends on the full `[dev]` install, not on stdlib. *Remedy:* state
"~2 s; needs the dev extra, git, and no network".

**A9 — Direction 2 has one hard-coded exemption and no declarative mechanism for another.** The
module goes out of its way to make manifest classification *declared rather than inferred* — good
design, and the docstring argues for it well — but the tracked-file exemption is the bare literal
`{PARENT_MANIFEST.name}` with the comment "nothing else is exempt". Any future file that
legitimately belongs in the corpus tree but not in the evidence index (a `.gitattributes`, a
`CODEOWNERS`, an LFS pointer config) turns fastlane red with no supported way to express the
exception except recording it as evidence. *Remedy:* a module-level `NOT_EVIDENCE: frozenset[str]`
with a comment per entry, matching the pattern the module already uses twice.

**A10 — `fastlane` and `test-suite.yml` do not cover the same branches.** `ci_v14_fastlane.yml`
triggers on `pull_request: branches: [main]`; `test-suite.yml` on `[main, develop]`. A PR into
`develop` would run the sharded suite but not the guard — the reverse of the gap this change
exists to close. Currently theoretical: `git ls-remote --heads origin develop` returns nothing.
*Remedy:* align the fastlane trigger to `[main, develop]`, or drop `develop` from `test-suite.yml`.

**A11 — `--showlocals` is in the repo-wide `addopts`.** Any failure of this module dumps its locals,
which include whole manifest texts and, today, clause-6 spans, into a public CI log. This is a
repo-wide setting and not this change's doing, but this module is unusually sensitive to it.
*Remedy:* keep confidential text out of locals in this module (read and test in a helper that
returns a boolean), which the B1 remedy largely achieves.

## 5. Claims I could not verify

- **That `fastlane` is a required status check**, as its header comment asserts. `gh` is not
  installed and no branch-protection or ruleset endpoint is reachable from the tools available here.
  I corroborated it only from the repository's own records — `docs/SESSION_HANDOVER_2026-08-24_3.md:72`
  ("required contexts remain `Test Summary`, `fastlane` and `smoke`"),
  `docs/DOLPHIN_3A_REMEDIATION_REREVIEW_RECORD.md:814-815` ("All four required checks passed: Test
  Summary, Verification receipts, fastlane, and smoke") — which is repository self-report, not an API
  receipt. Treat B1's merge-blocking consequence as very likely rather than proven; B1 stands
  regardless, because a red required-or-not job on the introducing commit is disqualifying either way.
  Whether the `Code Quality Checks` context is itself required I could not establish — but I did not
  need to: its `lint` job is gated by `Test Summary` in `test-suite.yml`, so B2 blocks merge through
  that path whatever the ruleset says about `Code Quality Checks` directly.
- **"Four manifest defects reached `main` between #1226 and #1234"** and **"two of the four defect
  commits carried nothing else"** (i.e. were docs-only). Not enumerated; this is evidence-history
  territory and sits closer to the parallel reviewer's lane. The *mechanism* the claim rests on —
  that a docs-only diff skips the pytest shard — I did verify (§3.8).
- **"the coupling ... broke twice on one branch, the second time reporting `FAILED` on a present
  file"** and **"the parent-pin guard ... caught a scripted revert"**. Historical assertions about
  events in a previous session. Not checkable from the tree. I can confirm the *mechanism* is real:
  mutation M6 shows an unrefreshed parent pin makes `sha256sum -c` report `FAILED` on a present,
  uncorrupted file.
- **"tests/lint 422 passed"**. Not re-run; the module-level result I did reproduce contradicts the
  companion claim "harness 7/7 passed" for the committed tree (§3.5), so the 422 figure should be
  re-established after remediation rather than carried forward.
- **"No hash line changed. All 22 entries of the nested manifest are byte-identical"** — a
  documentation/evidence claim, out of my mandate. I note only that `sha256sum -c` passes 138/138
  at this head, and that `test_nested_manifest_parent_pins_are_current` passes, which is consistent
  with it.
- **The 5 `test_cloud_audit_review_sandbox.py` failures** described as known container
  process-group-reaping issues. Not investigated.

## 6. Read-only attestation

I modified no file in the candidate tree. I ran no `git checkout`, `git stash`, `git restore`,
`git reset`, `git add`, `git commit`, `git push` or any other mutating git command inside
`/home/user/dutchbay-epc-model`. All mutation testing was performed on a throwaway `--depth 1`
clone under
`/tmp/claude-0/-home-user-dutchbay-epc-model/7f38d383-eda6-5940-bbb7-c624b079362c/scratchpad/shallow`
and on a `git archive` extraction of `782c958` under the same scratchpad; every file mutated there
was restored from a backup copy I made myself, never from git. Formatter checks that needed a
writable file were run on copies under the scratchpad, never in place.

Mid-review, and immediately before writing this record, the tree was verified clean at the bound
head:

```
$ git status --short
(no output)
$ git rev-parse HEAD
3e4b79f1898bd7a2ec10064e6a7941757ebc5160
$ git diff --stat HEAD
(no output — tree identical to 3e4b79f)
```

**Final state, after the concurrent writer activity described in §0.1 and §0.2:**

```
$ git status --short
 M tests/lint/test_nso_corpus_manifest_integrity.py
?? docs/NSO_CORPUS_GUARD_CODE_REVIEW_RECORD_2026-09-05.md
$ git rev-parse HEAD
4ac60d957a0e6f32849f123412daa407f3196628
```

The `??` entry is this record — the only file I created or modified. The ` M` entry is **not
mine**: it is the implementation worker's uncommitted in-flight edit, written at
`10:24:21` while I was drafting §6, and its content applies advisories A1, A2 and A3 from this
review (§0.2). HEAD likewise advanced from `3e4b79f` to `4ac60d9` by that worker's commit at
`10:21:19`, not by any action of mine.

I state without qualification: **I created, staged, committed, pushed, reverted and deleted
nothing in this repository except `docs/NSO_CORPUS_GUARD_CODE_REVIEW_RECORD_2026-09-05.md`.**
Every check I ran against the candidate was read-only and SHA-addressed; every mutation was
performed on a copy under the scratchpad. Because the tree was mutated by another actor during the
review window, the clean `git status` I can attest to is the one taken at the bound head before that
activity began (above), together with the fact that the residual dirt is attributable by timestamp
and content to the writer, not the reviewer.

This record lives under `docs/` and not under `docs/source_materials/nso_bess_250mw_2026/`, so it
does not interact with the guard's direction-2 assertion. It reproduces no span of clause 6 —
verified:

```
$ for s in <span 0> <span 1> <span 2>; do grep -qF "$s" <this record> && echo LEAK || echo clean; done
clean (span absent)
clean (span absent)
clean (span absent)
```

---

*Reviewer: independent CODE/CI reviewer under GWTF `RECRUIT-01`. Bound to
`3e4b79f1898bd7a2ec10064e6a7941757ebc5160` on base `1240a9ae0f300a2379825970cd38583f50948631`.
Transfers to no other tree.*

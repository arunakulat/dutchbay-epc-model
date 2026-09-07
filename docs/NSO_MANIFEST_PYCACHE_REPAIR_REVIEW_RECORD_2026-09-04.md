# RECRUIT-01 Documentation Review Record — PR #1234

**Reviewer role:** Documentation / evidence-record reviewer (single reviewer; RECRUIT-01 permits
one for a documentation-only change).
**Date:** 2026-09-05
**Mandate:** STRICTLY READ-ONLY on `/home/user/dutchbay-epc-model` and `/home/user/dutchbay_rag`.
No writer lease. One permitted write: this file.

## DISPOSITION

**ACCEPT WITH ADVISORY**, bound to:

```
candidate commit : 28ab36a0b4562900cfacb3cc93080b877af0f335
candidate tree   : b51deba54362d984f81e3e46470430012750f66e
base             : 4082ac57283fb8c3fea5af2c649e863212dd9fd9
branch           : fix/corpus-manifest-pycache-entry     PR #1234
```

Blocking findings: **0**. Advisory findings: **4** (plus one process note).
The one-line repair is correct, complete, and the right remedy. Every advisory concerns
**prose accompanying** the fix, not the fix. None blocks merge.

Acceptance binds to this exact commit, tree and base only. Any further delta to the candidate's
own tree requires a fresh review (RECRUIT-01, no exception). A pure base fast-forward may carry
this disposition ONLY with all three RECRUIT-01 proofs recorded in the PR (blob-hash identity,
bidirectional import isolation, complete reviewed-to-updated diff); absent any one, this
disposition LAPSES.

## DRIFT CHECK — NONE

Verified before any other work.

```
$ git rev-parse HEAD          -> 28ab36a0b4562900cfacb3cc93080b877af0f335   MATCHES BOUND
$ git rev-parse HEAD^{tree}   -> b51deba54362d984f81e3e46470430012750f66e   MATCHES BOUND
$ git rev-parse --abbrev-ref HEAD -> fix/corpus-manifest-pycache-entry      MATCHES BOUND
$ git rev-parse 4082ac5       -> 4082ac57283fb8c3fea5af2c649e863212dd9fd9   MATCHES BOUND
$ git merge-base --is-ancestor 4082ac5 28ab36a -> base IS ancestor of candidate
$ git log --oneline 4082ac5..28ab36a -> 28ab36a (exactly one commit)
```

Live PR #1234 (`mcp__github__pull_request_read`): `head.sha` = `28ab36a…`, `base.sha` = `4082ac5…`,
state `open`, **draft `true`**, `mergeable_state` `clean`, `changed_files` 2, `+8/-1`, 1 commit.
Head and base both match the bound SHAs. No concurrent-writer drift observed.

## WHAT I INGRESSED (RECRUIT-01 order)

1. `go_with_the_flow_rules_v3_0_clean.csv` — rows `RECRUIT-01`, `DATA-01`, `VERIFY-01`, `MERGE-01`
   (read in full via csv.DictReader; all four `status=active`).
2. `docs/source_materials/nso_bess_250mw_2026/source_packages/README.md` — the manifest-only
   scheme and its purpose; plus the parent corpus `README.md` context it references.
3. `git show --stat 4082ac5`; `git log --all -S'__pycache__' --oneline -- <manifest>`;
   full history of the manifest across all branches.
4. `git diff 4082ac5..28ab36a` (the complete change, read in full).
5. `AGENTS.md`, live PR #1234 body/state/status, and the sibling branch #1233 commit messages
   (`2a25050`, `e777ead`, `cd35987`, `f884e55`, `ec4265c`) for the provenance of the reused claims.

## CLAIM-BY-CLAIM VERIFICATION

Every number below is from a command I ran myself. No figure quoted to me was accepted.

### C1 — Both manifest states reproduce as claimed. CONFIRMED.

Reproduced from clean `git archive` exports into `/tmp` (tracked files only, no working-tree
contamination), `sha256sum -c` run from the corpus root.

**Base `4082ac5`:**
```
$ sha256sum -c MANIFEST.sha256
EXIT=1
entries in manifest: 139   OK lines: 138   FAILED lines: 1
registers/__pycache__/build_ltl_comparative_recommendation_2026-09-03.cpython-312.pyc: FAILED open or read
sha256sum: ... No such file or directory
sha256sum: WARNING: 1 listed file could not be read
```

**Candidate `28ab36a`:**
```
$ sha256sum -c MANIFEST.sha256
EXIT=0
entries in manifest: 138   OK lines: 138   FAILED lines: 0
(no non-OK stdout; stderr empty)
```

Exactly `138 OK, 1 FAILED, exit 1` before and `138/138 OK, exit 0` after, as claimed.

### C2 — The defect's origin and the gitignore interaction. CONFIRMED.

```
$ git check-ignore -v docs/source_materials/nso_bess_250mw_2026/registers/__pycache__/
.gitignore:2:__pycache__/	docs/source_materials/nso_bess_250mw_2026/registers/__pycache__/
```
`.gitignore:2` is `__pycache__/`, exactly as the PR states.

```
$ git log --all --diff-filter=A --name-only -- '*.pyc'
(no output)
```
**No `.pyc` has ever been added to this repository, on any branch, in its entire history.** The
path was therefore never in the tree and, while `.gitignore:2` stands, never can be. "Impossible
entry" is the correct characterisation.

Introduced by `0a18364` (#1226), which is an ancestor of the base:
```
$ git merge-base --is-ancestor 0a18364 4082ac5 -> YES
```
The `+` hunk in `0a18364` adds precisely the one line the candidate removes.

Note: the sibling repairs (`2a25050`, `e777ead`, `cd35987`, `f884e55`, `ec4265c`) are **not**
ancestors of the base or of the candidate — verified — so this candidate is genuinely independent
of #1233's unmerged work.

### C3 — Deletion is the right remedy, not committing the file. CONFIRMED, on evidence.

I did not take this on the coordinator's reasoning. Two independent tests, both run on a
throwaway control file in `/tmp` containing **invented values only** (no real register was
compiled, read for content, or copied):

**(a) A `.pyc` retains every literal of its source.**
```
$ strings -n 4 demo_register.pyc | grep -Ei 'ACME|MWh|PRICE|VENDOR'
ACME-CONTROL-VENDOR / 10MW/40MWh / 11MW/44MWh / UNIT_PRICE_USD_PER_KWH / VENDOR / PRICE_TABLE
$ marshal.load(...) -> co_consts:
[137.42, 'ACME-CONTROL-VENDOR', 4321000.0, 4765500.0, ('10MW/40MWh', '11MW/44MWh'), None]
```
CPython bytecode carries the full `co_consts` table. Committing the `.pyc` of a register that
carries price tables **as source literals** into a *public* repository would publish exactly the
gated figures, recoverable with `strings` alone. That the source `.py` is withheld would be
worthless. Committing the file, or negating the ignore rule, is categorically wrong.

**(b) A `.pyc` hash is not reproducible from its source.**
```
$ (compile same .py twice, differing only in source mtime)
07aa228770567f4a...  demo_register.pyc
9b31103e3dabcdac...  demo_register_b.pyc
DIFFERENT -> hash of a .pyc is not reproducible from its source alone
```
The `.pyc` header embeds source mtime and size. The recorded hash was therefore **permanently
unverifiable** — not merely unsatisfied today, but unsatisfiable in principle even by a holder of
the private `.py`. An evidence manifest cannot carry an entry no one can ever discharge.

Deletion is the only correct remedy. **The fix is complete: there is no missing `.py` that should
also have been added** (see C4).

### C4 — Nothing leaked, and the `.py` should NOT be public. CONFIRMED.

The private source exists and is tracked exactly where the coordinator said:
```
$ ls /home/user/dutchbay_rag/corpus/nso_bess_250mw_2026_offers/registers/
build_ltl_comparative_recommendation_2026-09-03.py
build_ltl_offer_recommendation_2026-09-03.py
$ git ls-files --error-unmatch corpus/.../build_ltl_comparative_recommendation_2026-09-03.py
corpus/nso_bess_250mw_2026_offers/registers/build_ltl_comparative_recommendation_2026-09-03.py
```
It is absent from the public tree (`git ls-files` under `registers/` returns only
`build_gap_dossier_2026-08-27.py` and `render_advisory_issue_2026-08-27.py`). No `.pyc` of it
exists anywhere in either repository.

It is already recorded — deliberately — in the **public** nested manifest
`source_packages/NSO250MW_Commercial_Offers_2026-09-03.MANIFEST.sha256`, under the header
`# --- document registers; these carry the price tables as source literals ---`. That manifest
verifies against the private corpus:
```
$ cd /home/user/dutchbay_rag/corpus/nso_bess_250mw_2026_offers
$ sha256sum -c .../NSO250MW_Commercial_Offers_2026-09-03.MANIFEST.sha256
EXIT=0   OK=17   FAILED=0
```

**Leak analysis.** What reached the public repository via the bad line was one SHA-256 and one
path stem. The stem `build_ltl_comparative_recommendation_2026-09-03` is *already* public by
design, in the nested manifest above; and a SHA-256 is not a disclosure of content — that is the
manifest-only scheme's own founding premise, stated in `source_packages/README.md`: record the
hash "so a future session can verify that a re-supplied copy is the same artifact without the
artifact being public." **Nothing leaked.** Deletion neither creates nor cures a disclosure; it
repairs an integrity record. The `.py` is correctly private and must stay so.

### C5 — Completeness of the repaired manifest. CONFIRMED — exactly complete.

Against the candidate's own `git archive` export:
```
present=138  recorded=138
present but NOT recorded : (none)
recorded but NOT present : (none)
duplicate recorded paths : (none)
malformed lines (not 64hex + 2sp + path) : 0
recorded paths that git would ignore     : (none)
```
Every tracked corpus file is recorded and every recorded path is present. No second impossible
entry, no stale entry, no duplicate, no malformed line.

### C6 — The other manifests and the nested parent pins. CONFIRMED — clean, no stale pin.

The parent pins all three nested manifests; all three verified inside the 138/138 run above, so
**no parent pin is stale**. Independently:

| Manifest | Check | Result |
|---|---|---|
| `NSO250MW_oem_supply_2026-08-27` (declares "COMMITTED IN FULL") | `sha256sum -c` at candidate | `EXIT=0  OK=38  FAILED=0` |
| same, at base `4082ac5` (regression control) | `sha256sum -c` | `EXIT=0  OK=38  FAILED=0` — no regression |
| `NSO250MW_Commercial_Offers_2026-09-03` | `sha256sum -c` vs private corpus | `EXIT=0  OK=17  FAILED=0` |
| all three | `grep -nE '__pycache__|\.pyc'` | **no matches in any of them** |

The 38 entries match the corpus README's stated 14 certificates + 11 binaries + 13 extracts.
`NSO250MW_checklist_2026-08-21` is manifest-only by design (content held outside the repo) and is
not `-c`-checkable against this tree; its 72 lines are well-formed.

### C7 — "No test covers either corpus manifest." CONFIRMED TRUE.

```
$ grep -rn 'source_materials' tests/ --include='*.py'
(no output)
$ grep -rn 'nso_bess_250mw_2026' tests/ scripts/ .github/
tests/fixtures/grid/envision_enpcs01_gridcode.yaml:12  (a comment, not a test)
tests/fixtures/grid/envision_enpcs01_gridcode.yaml:15  (a comment, not a test)
$ grep -rlni 'manifest' .github/workflows/
(no output)
```
Manifest tests do exist — `tests/lint/test_cloud_audit_review_sandbox.py` pins
`docs/audit/2026-08-controlled-successor/PUBLICATION_MANIFEST.sha256`, and
`tests/lint/test_audit_recovery_portability.py` handles `SOURCE_ARCHIVE_MANIFEST.sha256` — but
those cover a **different corpus**. Nothing touches `docs/source_materials/` at all. The claim
holds, and the audit-pack tests are a working in-repo precedent for the gate the PR proposes.

### C8 — Changelog fragment. CONFIRMED CORRECT.

The compiler does strip all blank lines, as warned —
`scripts/compile_changelog.py:158`:
```python
frag_lines = [ln for ln in body.split("\n") if ln.strip() != ""]
```
The fragment is immune to it:
```
$ grep -c '^$' changelog.d/corpus-manifest-pycache-entry.fixed.md -> 0    (8 lines, no blank lines)
$ python3 scripts/compile_changelog.py --dry-run                  -> EXIT=0
```
It renders as one intact bullet at output lines 694–701, under the `### Fixed` heading at line
591, with the next bullet correctly separate at 702. No structure depends on a blank line, so the
failure mode recorded as A1 on the sibling branch cannot recur here.

## FINDINGS

### BLOCKING — none.

### ADVISORY

**A1 — "a `sha256sum -c` gate … would have caught all four" is demonstrably false for the
omission class.** (commit message, changelog fragment, PR body)

`sha256sum -c` validates *recorded → present*. It cannot detect *tracked → unrecorded*: a manifest
that silently omits files passes with exit 0. Proven on this repository's own history — I verified
the parent manifest at every main-ancestor commit that touched it:

```
commit    entries  OK   FAILED exit   tracked  recorded  omitted
637aad3   13       13   0      0      16       13        3
08c673e   13       13   0      0      19       13        6
3a3529a   24       24   0      0      30       24        6
0e63f7a   108      108  0      0      119      108       11
782c958   119      119  0      0      130      119       11
8c07d09   135      135  0      0      135      135       0
be19564   136      136  0      0      136      136       0
0a18364   139      138  1      1      138      139       1  (+1 impossible)
4082ac5   139      138  1      1      138      139       1  (+1 impossible)
28ab36a   138      138  0      0      138      138       0
```

At `782c958` the manifest omitted **11 tracked files** and `sha256sum -c` still returned
`119/119 OK, exit 0`. A `-c` gate would have caught the #1226 defect and **none** of the earlier
ones. The correct gate is two checks: `sha256sum -c` (recorded → present) **and** a coverage
assertion (tracked → recorded). Worth correcting before this text is published, since the fragment
is the artifact that will be read later, and it slightly misprices the follow-up it recommends.

**A2 — "the fourth manifest defect … to reach `main`" is not verifiable as stated.**
No enumeration is given and "defect" is not individuated. Empirically, this is the **first**
defect that made the parent manifest *fail* `sha256sum -c` on `main` — it was clean at every prior
main commit that touched it (table above). Prior defects on main were of the omission class:
5 consecutive main commits (`637aad3` … `782c958`) carried an incomplete manifest, closed at
`8c07d09`. So a count greater than one is defensible, but "fourth" cannot be confirmed from the
repository. Either cite the four, or soften to what is provable. This is inherited from `2a25050`
on the sibling branch; correcting it here would also correct it there.

**A3 — commit-message receipt understates the diff.** The commit message records
`git diff --stat  ->  1 file changed, 1 deletion(-)`. The actual value for the stated range is:
```
$ git diff --stat 4082ac5..28ab36a
 changelog.d/corpus-manifest-pycache-entry.fixed.md        | 8 ++++++++
 docs/source_materials/nso_bess_250mw_2026/MANIFEST.sha256 | 1 -
 2 files changed, 8 insertions(+), 1 deletion(-)
```
The **PR body states this correctly** ("`1 file changed, 1 deletion(-)` (plus the changelog
fragment)"); only the commit message omits the qualifier. Minor VERIFY-01 precision point; the
commit message is immutable in practice, so this is noted, not asked for.

**A4 — delivery state, not a defect.** PR #1234 is a **draft** and reports **zero** status checks
on `28ab36a` (`get_status`: `state: pending, total_count: 0`). Under MERGE-01 it is not
merge-eligible until it leaves draft and every required check — including
`Verification receipts (VERIFY-01)` — reports success on this exact head. MERGE-01's standing
authorization applies only from that point.

### PROCESS NOTE (addressed to the coordinator, not a finding against the candidate)

RECRUIT-01 requires review records be written to `docs/` **the moment they land** (PERSIST-01):
"a review chain that lives only in a session's context is lost, and the pass must be redone." My
lease confines my single write to `/tmp`, so **this record is not yet durable**. The coordinator
must persist it into `docs/` for the review chain to exist. I have not done so, as that would
exceed my read-only mandate.

## MUTATION ATTESTATION

I made no change to either repository. My one permitted write is this file, outside both trees.
All scratch work (archives, the compile control, the history sweep) is under
`/tmp/claude-0/…/scratchpad/`. `PYTHONDONTWRITEBYTECODE=1` was exported in every shell that ran
Python, so I created no `.pyc` in either judged tree — the defect under review.

| | BEFORE | AFTER |
|---|---|---|
| `dutchbay-epc-model` HEAD | `28ab36a0b4562900cfacb3cc93080b877af0f335` | `28ab36a0b4562900cfacb3cc93080b877af0f335` |
| `dutchbay-epc-model` tree | `b51deba54362d984f81e3e46470430012750f66e` | `b51deba54362d984f81e3e46470430012750f66e` |
| `dutchbay-epc-model` `git status --porcelain` | *(empty)* | *(empty)* |
| `dutchbay-epc-model` `git stash list` | *(empty)* | *(empty)* |
| `dutchbay_rag` HEAD | `840e1383d9387f29b8bb0717ec158e1c6079b27b` | `840e1383d9387f29b8bb0717ec158e1c6079b27b` |
| `dutchbay_rag` `git status --porcelain` | *(empty)* | *(empty)* |
| `dutchbay_rag` `git stash list` | *(empty)* | *(empty)* |

```
$ find /home/user/dutchbay-epc-model /home/user/dutchbay_rag -name '*.pyc' -newermt '2026-09-05 00:00'
(no output — no .pyc created by this review)
```

Pre-existing ignored `__pycache__` artifacts elsewhere in both trees (e.g.
`scripts/__pycache__/`, `tests/lint/__pycache__/`, and the corpus's own
`registers/__pycache__/build_gap_dossier_2026-08-27.cpython-312.pyc`) predate this review; both
repos report clean, so all are correctly ignored.

## AUTHORITY BOUNDARY

This disposition is a **documentation / evidence-record review** of PR #1234 at commit `28ab36a`,
tree `b51deba`, base `4082ac5`, and nothing else. Specifically it does **not**:

- confer achieved-grade, report-grade, release, deployment, audit, lender or Board authority;
- constitute merge authority — CI and branch protection remain the merge boundary (MERGE-01),
  and the PR is currently a draft with no checks reported;
- extend to any other commit, tree or base, to PR #1233, or to the private repository's contents
  beyond the hash-verification and existence checks recorded above;
- review the substance of the confidentiality decision, the offer terms, or the private
  register's contents — I read no price figure and reproduced none;
- discharge RECRUIT-01's `docs/` persistence requirement (see PROCESS NOTE);
- substitute for the second reviewer that RECRUIT-01 would require were this load-bearing code,
  contract or finance work. It is documentation-only, so one reviewer suffices — but that
  judgement is itself part of this record and open to challenge.

I am one reviewer. This record is evidence, not authority.

---
*Reviewer: Claude Opus 5, recruited under RECRUIT-01 as single documentation reviewer.*
*Session: https://claude.ai/code/session_01JcdWoDgBuFgGSBJmke37wZ*

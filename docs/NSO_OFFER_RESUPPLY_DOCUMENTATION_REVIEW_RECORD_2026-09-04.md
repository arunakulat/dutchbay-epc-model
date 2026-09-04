# NSO 4 September Offer Re-supply — INDEPENDENT DOCUMENTATION REVIEW RECORD

**Reviewer:** single documentation / evidence-record reviewer, recruited under GWTF `RECRUIT-01`
(documentation-only change → one reviewer suffices) · **Date:** 2026-09-04 · **Role:** STRICTLY
READ-ONLY, no writer lease.

---

> **COORDINATOR NOTE — why this record is unredacted.** The reviewer flagged at advisory A6 that
> copying this record verbatim would re-publish the offer terms quoted in it as evidence, and asked
> that it be redacted **if** blocking finding B2 were resolved by removing that text. It was not:
> the project owner's decision of 4 September 2026 retains the disclosure, and the offers manifest
> now states that it does rather than denying it. The A6 condition therefore does not apply and the
> record stands as the reviewer wrote it. Disposition, findings, commands and outputs are unaltered.

## 0. DISPOSITION

# REJECT

Bound to the exact candidate below. This disposition transfers to **no other implementation, tree or
base**; any further delta requires a fresh review (`RECRUIT-01`).

| | |
|---|---|
| **Candidate commit** | `d86955da55e1af33f1f0772367cc887ae304d3fa` |
| **Candidate tree** | `63e5a92e581a1ec21937f71d530b5ce300fc6b76` |
| **Base commit** | `4082ac57283fb8c3fea5af2c649e863212dd9fd9` |
| **PR / branch** | `#1233` · `claude/nso-25x10-bess-tender-8ehomm` (draft) |

**3 blocking findings, 6 advisory findings. No SHA drift detected.**

`REJECT` rests on two independent grounds, either sufficient on its own:

1. **The change does not do the thing it exists to do.** Its headline claim is that
   `sha256sum -c MANIFEST.sha256` passes again. At this head it **fails** — and fails in a strictly
   worse class than the base it repairs (base: a listed file was absent; head: a listed file's
   content **does not match its recorded hash**, which is the signal that means evidence has been
   altered). §5.1.
2. **The committed prose asserts "Content remains manifest only … recorded here by hash only" while
   the same commit publishes verbatim offer content** that was absent from the public repository at
   base — on the candidate's own stated basis that clause 6 forbids exactly that, with no
   authorization instrument held. §5.2.

Most of the candidate's substantive factual work is **correct and, if anything, understated** — see
§4.3, which I verified from primary sources without relying on any statement in the change. The
rejection is not a judgement on the analysis; it is that the artifact does not verify and
misdescribes itself.

---

## 1. Candidate identity — verified before review

```
$ git rev-parse HEAD
d86955da55e1af33f1f0772367cc887ae304d3fa
$ git rev-parse HEAD^{tree}
63e5a92e581a1ec21937f71d530b5ce300fc6b76
$ git rev-parse --abbrev-ref HEAD
claude/nso-25x10-bess-tender-8ehomm
$ git merge-base HEAD origin/main
4082ac57283fb8c3fea5af2c649e863212dd9fd9
$ git status --porcelain
(empty)
```

All three bound SHAs match. The merge-base equals `origin/main`'s head (`4082ac5`), so the branch is
current and the declared base is the real base. GitHub confirms the same pair
(`head.sha d86955da…`, `base.sha 4082ac57…`). **No drift.**

---

## 2. Ingress performed (`RECRUIT-01` order)

1. **Canonical GWTF CSV** `go_with_the_flow_rules_v3_0_clean.csv` (75 rows, all `v3.0`, all
   `active`). Read in full from the CSV, not from summaries: `RECRUIT-01`, `DATA-01`, `VERIFY-01`,
   `MERGE-01`, `R26`, and `FRAMEWORK-01/02/03` (CASPER / CESSPIT / CCCDIR).
2. **Governing corpus documents** —
   `docs/source_materials/nso_bess_250mw_2026/source_packages/README.md` in full; and, for the
   confidentiality chain, `.../compliance_evidence/README.md`,
   `.../reviews/NSO250MW_Session_Archive_2026-08-29.md` §6,
   `.../reviews/Envision_Corporate_Brochure_2603_and_Archive_Ingress_Evaluation_2026-09-01.md` §2.1.
3. **Prior accepted work** — `docs/DOLPHIN_F6_DOMAIN_REVIEW_RECORD.md` §0, §0.1, §0.2, §10, **§10.1**
   and **§11**, for the review-record form this repository expects (SHA table, per-claim receipts,
   findings split blocking/non-blocking, mutation attestation, handover point, authority boundary).
   This record follows that form.
4. **The live change** — `git diff 4082ac57..d86955da` read in full (3 files, +67/−2), plus both
   constituent commits `2a25050` and `d86955d` and their full messages.
5. **`AGENTS.md`** in full; branch, remote and PR state (`#1233`, draft, `mergeable_state: clean`,
   20 check runs).

`FRAMEWORK-01/02/03` are code-architecture rules (module interfaces, config-first schema validation,
contract gateways). This change touches no Python and no config, so they are **not engaged**; I
record that I read them and found them inapplicable rather than silently omitting them.

**Every statement in the recruiting brief, the commit messages and the PR body was treated as a
claim to verify. Several did not survive.**

---

## 3. What the change actually is

Three files, no code, no binaries:

```
$ git diff --stat 4082ac57..d86955da
 changelog.d/nso-commercial-offer-resupply.fixed.md | 24 +++++++++++++
 .../nso_bess_250mw_2026/MANIFEST.sha256            |  3 +-
 ...MW_Commercial_Offers_2026-09-03.MANIFEST.sha256 | 42 ++++++++++++++++++++++
 3 files changed, 67 insertions(+), 2 deletions(-)
```

---

## 4. Claims verified — command and actual output

### 4.1 Claim 1 — manifest repair: the diagnosis

Every element of the diagnosis is **correct**.

```
$ grep -n '__pycache__\|\.pyc' .gitignore
2:__pycache__/

$ git check-ignore -v docs/source_materials/nso_bess_250mw_2026/registers/__pycache__/build_ltl_comparative_recommendation_2026-09-03.cpython-312.pyc
.gitignore:2:__pycache__/	docs/source_materials/nso_bess_250mw_2026/registers/__pycache__/build_ltl_comparative_recommendation_2026-09-03.cpython-312.pyc

$ git log --all --oneline -- 'docs/source_materials/nso_bess_250mw_2026/registers/__pycache__/*'
(empty — never tracked in any tree, on any branch)

$ git log --oneline -3 -- docs/source_materials/nso_bess_250mw_2026/MANIFEST.sha256
2a25050 fix(nso): repair the corpus manifest and record the 4 Sep offer re-supply
0a18364 docs(nso-bess): record the 3 Sep OEM commercial offers by manifest only (#1226)
be19564 docs(nso): retain archive member dedupe map (#1212)
```

So: gitignored at `.gitignore:2`; never in any tree; entered via #1226. All three confirmed.

**Did it genuinely fail on the base?** Yes. Verified on a clean, tracked-only extraction of the base
tree (`git archive` — reads the object database, touches neither working tree nor index):

```
$ git archive 4082ac57 | tar -x -C $SCRATCH/base_tree
$ cd $SCRATCH/base_tree/docs/source_materials/nso_bess_250mw_2026 && sha256sum -c MANIFEST.sha256
… 138 lines ": OK" …
sha256sum: registers/__pycache__/build_ltl_comparative_recommendation_2026-09-03.cpython-312.pyc: No such file or directory
registers/__pycache__/build_ltl_comparative_recommendation_2026-09-03.cpython-312.pyc: FAILED open or read
sha256sum: WARNING: 1 listed file could not be read
exit=1
```

**138 OK, 1 FAILED, exit 1 — exactly as claimed.**

The intermediate commit `2a25050` did repair it:

```
$ cd $SCRATCH/mid_tree/docs/source_materials/nso_bess_250mw_2026 && sha256sum -c MANIFEST.sha256
exit=0 ;  OK count: 138 ;  failures: none
```

**138/138, exit 0 — the claim was true at `2a25050`.** It is not true at the bound head. See §5.1.

### 4.2 Claim 2 — no offer content, price or scope text committed

**Prices and binaries: clean.** Confirmed by four independent probes.

```
$ git diff --name-only 4082ac57..d86955da
changelog.d/nso-commercial-offer-resupply.fixed.md
docs/source_materials/nso_bess_250mw_2026/MANIFEST.sha256
docs/source_materials/nso_bess_250mw_2026/source_packages/NSO250MW_Commercial_Offers_2026-09-03.MANIFEST.sha256
```

No PDF, no binary, no extract. Scanning every added line for currency or thousands-separated
figures returned **no hits**. I then took the seven headline and line-item figures from the offers'
own price tables (read by me from the private corpus; **deliberately not transcribed into this
record** — see A6) and searched for each:

```
$ for n in <7 figures>; do git diff 4082ac57..d86955da | grep -c -- "$n"; done
0 0 0 0 0 0 0
$ for n in <4 headline figures>; do git grep -c -- "$n" d86955da; done
(no match in any file at the candidate head)
```

**No price figure from either offer appears in this diff or anywhere in the public repository at
this head.** That part of the claim holds, and holds strongly.

**Scope and commercial-term text: NOT clean.** See blocking finding B2 (§5.2).

### 4.3 Claim 3 — the factual substance, verified from primary sources

I extracted all four PDFs myself under `R26` (governed MarkItDown, from the active checkout) and
compared them. I did not rely on any figure in the brief, the commit messages, or the private
repository's own comparison document.

```
$ python3 -c "import markitdown; print(markitdown.__version__)"
0.1.7                       # matches the version the manifest declares
$ python3 -m markitdown <each of the 4 PDFs> > $SCRATCH/extract/<name>.md
sep03_10MW exit=0  sep03_11MW exit=0  sep04_10MW exit=0  sep04_11MW exit=0   (stderr empty)
```

The raw `diff -u` is noisy because both documents reflow across page breaks. I therefore also ran an
**order-independent line-multiset comparison**, which cancels reflow and leaves only real edits:

**10 MW — exactly two substantive changes:**

```
ONLY IN 3 SEP:
  - 1. PCS and AC equipment are not included in supply scope.
  - o Warranty Period: 5 years upon Substantial Completion Date for BESS.
  (+ renumbering of the two surviving notes)
ONLY IN 4 SEP:
  + o Warranty Period: 2 years upon Substantial Completion Date for BESS.
```

**11 MW — exactly one substantive change:**

```
ONLY IN 3 SEP:
  - 1. PCS and AC equipment are not included in supply scope.
  (+ renumbering of the two surviving notes)
ONLY IN 4 SEP:
  (no term change)
```

Every other difference is pagination reflow — the same lines present in both, relocated across a
page boundary.

**Prices.** Multiset comparison of every numeric token of ≥5 characters:

```
10 MW: 3 Sep count=63  4 Sep count=63  IDENTICAL MULTISET = True
11 MW: 3 Sep count=58  4 Sep count=58  IDENTICAL MULTISET = True
```

Not merely the headline prices — **every number in both documents is unchanged.** The candidate's
claim is *understated*; I record the stronger result.

**Point-by-point:**

| Assertion in the changed prose | Verdict | Evidence |
|---|---|---|
| 10 MW BESS warranty cut 5 y → 2 y | **CORRECT** | `sep03_10MW:223` "5 years upon Substantial Completion Date" → `sep04_10MW:223` "2 years …" |
| 11 MW warranty stayed at 5 y | **CORRECT** | `sep03_11MW:418` and `sep04_11MW:417` both "5 years upon Substantial Completion Date" |
| Exclusion "PCS and AC equipment are not included in supply scope" removed from **both** | **CORRECT** | present `sep03_10MW:197`, `sep03_11MW:341`; `grep` returns **no match** in either 4 Sep copy |
| 10 MW exec summary still promises "5 years' BESS Warranty" → internally inconsistent | **CORRECT** | `sep04_10MW:31–36` §1 Executive summary reads "with 5 years' BESS Warranty" while §3.3 reads "2 years" |
| Both headline prices unchanged | **CORRECT (understated)** | all 63 / 58 numeric tokens identical |
| Both still "Version: 01" / "Date of Submission: August 31, 2026" | **CORRECT** | all four: 10 MW lines 7–8; 11 MW lines 13, 15 |
| Price tables charge separately for "PCS & MV Transformers" | **CORRECT** | 10 MW line 214 and 11 MW line 375–376 — a distinct priced line item inside §3.2's "Price for all supplies according to the scope of works described in 3.1", so the deleted §3.1 exclusion did contradict it |
| Clause 6 quoted verbatim | **CORRECT — exact** | programmatic whitespace-normalised exact-substring match returned `True` for **all four** documents |
| Validity 30 days from 31 Aug 2026 → lapse 30 Sep 2026 | **CORRECT** | all four: "The offer is valid until 30 Days from the Date of Submission"; `date(2026,8,31)+30d = 2026-09-30` |
| "Repeats a pattern … 5 Aug design calculation silently revised the 29 Jul one, both labelled V1.0" | **CORRECT** | `oem/envision/compliance_evidence/README.md:31`: "**Silently revises the 29 July document while still labelled V1.0.**" |
| "Fourth manifest defect in this programme" | **SUBSTANTIATED** | 2 defects (`NSO250MW_Session_Archive_2026-08-29.md:117-119` "Two such defects were found and repaired by hand in this thread") + 1 (`Envision_Corporate_Brochure_…_2026-09-01.md:45` "This was a manifest-coverage defect", 119 → 136 entries) + this one = 4 |
| "No test covers either corpus manifest" | **CORRECT** | no test or workflow references `docs/source_materials`; `grep -rn 'source_materials' tests/ scripts/ .github/` returns only `tests/fixtures/grid/envision_enpcs01_gridcode.yaml`, a fixture, not a manifest check |

**Claim 3's factual substance is accurate in every particular I could test.** The correction of the
earlier "same content: a re-export" note was necessary and is correctly made.

### 4.4 The two new hashes are genuine

All 19 hash entries in the nested manifest verify against the private corpus, including the two
added by this change:

```
$ cd /home/user/dutchbay_rag/corpus/nso_bess_250mw_2026_offers && sha256sum -c <19 entries>
…17 pre-existing entries: OK…
raw/resupply_2026-09-04/Srilanka_Envision_Commercial_Offer_10MW_40MWh.pdf: OK
raw/resupply_2026-09-04/Srilanka_Envision_Commercial_Offer_11MW_44MWh.pdf: OK
exit=0
```

### 4.5 Parent-manifest completeness

```
tracked under corpus dir: 139     listed in MANIFEST.sha256: 138
TRACKED BUT NOT LISTED:  MANIFEST.sha256        (correct — a manifest cannot hash itself)
LISTED BUT NOT TRACKED:  (none)
```

**Complete.** Separately, the sibling `NSO250MW_oem_supply_2026-08-27.MANIFEST.sha256` verifies
38/38, exit 0, so the PR's third receipt row is accurate.

---

## 5. FINDINGS

### 5.1 BLOCKING B1 — the manifest does not verify at this head; the repair was undone by the next commit

The change's central claim — *"Removed; the manifest verifies again"* — is **FALSE at the SHA I am
bound to**.

```
$ cd docs/source_materials/nso_bess_250mw_2026 && sha256sum -c MANIFEST.sha256
source_packages/NSO250MW_Commercial_Offers_2026-09-03.MANIFEST.sha256: FAILED
sha256sum: WARNING: 1 computed checksum did NOT match
exit=1
OK count: 137
```

Reproduced identically on a clean tracked-only extraction of the candidate tree, so this is a
property of the tree and not of my working copy.

**Root cause — the manifest hashes a file that this PR edits twice:**

```
commit    nested manifest ACTUAL sha256      parent manifest RECORDS
4082ac5   05b613a5dc4357ae…                  05b613a5dc4357ae…   consistent (but .pyc entry broken)
2a25050   4c80a094a0a60f60…                  4c80a094a0a60f60…   consistent — 138/138, exit 0
d86955d   576deb7aa0bbcb63…                  4c80a094a0a60f60…   MISMATCH
```

`2a25050` correctly updated both sides. `d86955d` — the corrective commit — rewrote the nested
manifest's re-supply note but left the parent's recorded hash of it pointing at the superseded
`2a25050` content.

**This is worse than the defect it repairs, not merely equal to it.** The base failure was
`FAILED open or read`: a listed file is absent — visibly a bookkeeping error. The head failure is
`FAILED`: a listed file **is present and its content does not match its recorded hash**. In an
evidence corpus that is the signal reserved for *an evidence file has been altered*. A manifest that
cries wolf in that specific way is a worse governance artifact than one that is merely stale, and
this change ships it onto a corpus whose entire purpose is hash-verifiable provenance.

**Minimal fix:** the parent entry must read
`576deb7aa0bbcb6384aa072681f4ba610386336c4e840883ba04b5f5516afa35`.

**Structural hazard the coordinator should note beyond the one-line fix:** the parent manifest hashes
a child manifest that the same PR edits, so *every* future edit to the nested manifest silently
re-breaks the parent. This PR is the second time in three commits that this exact coupling produced
a broken manifest. The candidate's own recommendation — that this pattern now warrants a test rather
than another hand repair — is well founded, and this finding is direct evidence for it: a hand
repair was applied and then undone by hand nine minutes later.

### 5.2 BLOCKING B2 — "manifest only" is not what this commit does

The nested manifest states, of the material it records:

> Held on the SAME basis as the rest of this manifest: content in the private repository, **recorded
> here by hash only**.

and the changelog fragment states:

> Content remains **manifest only**.

Both are false at this head. At the **base**, the public repository contained no verbatim text from
either offer — the nested manifest characterised them only in the abstract ("marked Confidential on
every page and their clause 6 requires prior, explicit and written authorization"). Verified:

```
$ git grep -n 'PCS and AC equipment'  4082ac57   → (no match)
$ git grep -n 'Warranty Period'       4082ac57   → (no match, in these paths)
$ git grep -n 'broadcasted, published' 4082ac57  → (no match)
```

At the **candidate head**, the same searches return hits in both changed files. The commit publishes,
on a public repository:

- the scope-exclusion sentence verbatim — *"PCS and AC equipment are not included in supply scope"*
  (manifest line 64; changelog line 13);
- **both** warranty durations with their contractual trigger — "5 years … 2 years upon Substantial
  Completion" (manifest line 60; changelog line 10);
- the executive-summary phrase quoted — *"5 years' BESS Warranty"* (manifest line 62; changelog
  line 12);
- the price-table line-item label — "PCS & MV Transformers";
- **clause 6 itself, verbatim** (new in this PR — absent at base);
- version, submission date and the 30-day validity window.

These are commercial terms of a live, unawarded bid, not metadata. A warranty period is a
bid-evaluation criterion; that this OEM cut one bidder-facing warranty by three years while holding
price is competitively material and is now public.

**Two distinct defects here, and I separate them deliberately:**

1. **Within my mandate — the record misdescribes itself.** A document may not simultaneously assert
   "recorded here by hash only" and disclose the document's commercial terms. Whichever way the
   coordinator resolves this, the self-description must stop being false. This alone is blocking:
   under `DATA-01`'s candour requirement and this repository's own practice of *recording* handling
   reversals rather than quietly applying them (`source_packages/README.md` does exactly that for
   the 27 August reversal), a change that materially widens the publication surface must **say so**
   and state its authority. This one says the opposite, and nothing in the commit message, the PR
   body or the fragment acknowledges that the disclosure surface moved at all.
2. **Outside my mandate — whether the disclosure is permitted.** Clause 6 forbids the offer being
   "broadcasted, published, or, more generally, communicated to any third party" absent Envision's
   prior written authorization. The candidate states no such instrument is held, and
   `PUBLICATION_AUTHORIZATION.md` and the 27 August reversal do not reach pre-award supplier
   pricing — that reasoning is the manifest's own and I found it sound. Whether quoting terms
   (rather than prices) crosses that line is a **project-owner decision on recorded authority**, per
   the precedent this corpus already sets. It is not mine, and I do not purport to decide it.
   I flag that publication to a public repository is **effectively irreversible**, so this is
   properly decided before merge rather than after.

I record in fairness that a governance record arguably *must* state what changed in order to be
useful, and that the candidate's disclosure is restrained — no prices. The defect is not that the
analysis exists; it is that it was published as though it were hash-only, without disclosure or
stated authority.

### 5.3 BLOCKING B3 — `VERIFY-01`: the PR receipts table is false on the bound head

PR #1233's receipts table and body still describe `2a25050`, not the head:

| PR body says | Actual at `d86955da` |
|---|---|
| "Corpus manifest, after — `138/138 OK`, exit 0" | **137 OK, 1 FAILED, exit 1** |
| "Nothing in this PR carries offer content, pricing or scope" | scope and warranty text **are** carried — §5.2 |
| "the **same logical documents** … a re-export or a second transmission" | **retracted by the head commit itself** — the content differs materially |

The third row is the sharpest: the PR description still advances, as the PR's own summary, precisely
the claim that `d86955d` exists to correct. A reader of #1233 is told the offers are unchanged
re-exports.

`Verification receipts (VERIFY-01)` reports **success** on this head, alongside 19 other green or
skipped checks and `mergeable_state: clean`. That is not a contradiction — it is the LIMIT the rule
documents in its own text: *"a receipts table carrying plausible but stale numbers passes it … A
green receipts check therefore means 'nothing was left silent', never 'the checks were verified';
the reviewer still reads the table."* I read the table. Three of its assertions are false on the head
they are attached to. Under `VERIFY-01` a claimed check whose stated result is wrong is worse than a
declared not-run.

The PR is currently a **draft**, so `MERGE-01` is not yet engaged; this must be corrected before it
leaves draft.

### 5.4 ADVISORY A1 — the manifest's provenance pin is stale for the material it now records

The nested manifest's header still reads:

> The content is held in the PRIVATE repository arunakulat/DutchBay_RAG at
> `corpus/nso_bess_250mw_2026_offers/`, **commit 652f8a5**.

The newly recorded files are not at `652f8a5`:

```
$ git -C /home/user/dutchbay_rag ls-tree -r --name-only 652f8a5 corpus/nso_bess_250mw_2026_offers/ | grep resupply
(empty)
$ git -C /home/user/dutchbay_rag branch -a --contains 133833a
* claude/offer-resupply-2026-09-04          ← local only; not on origin
```

A future session following the manifest's own pointer will not find the material the manifest
records. The pin should advance to the commit that actually contains it, and that commit should be
pushed — otherwise the public record points at private work that exists on one machine.

### 5.5 ADVISORY A2 — the re-supply is recorded less completely than the tranche it extends

The 3 September tranche pins raw **and** derived extracts **and** evaluation documents, in labelled
sections. The 4 September re-supply pins only the two raw PDFs. The private repository's own manifest
pins three further files that the public manifest omits:

```
evaluation/Envision_Offer_Resupply_Comparison_2026-09-04.md
extracted/resupply_2026-09-04/Srilanka_Envision_Commercial_Offer_10MW_40MWh.markitdown.md
extracted/resupply_2026-09-04/Srilanka_Envision_Commercial_Offer_11MW_44MWh.markitdown.md
```

The first is the comparison document that `d86955d`'s own message cites as where "the full comparison
is held" — the evidence base for the entire correction — and its identity is not pinned publicly, so
it can be revised without trace. `source_packages/README.md` states the purpose of these manifests as
recording "the SHA-256 of **every** file" so that a re-supplied copy can be verified. Recording the
inputs but not the analysis is a `DATA-01` lossiness against that stated purpose. Adding three hashes
costs nothing and discloses nothing.

### 5.6 ADVISORY A3 — the changelog fragment does not render as authored

`scripts/compile_changelog.py --dry-run` (read-only) shows the blank line between the sub-bullet list
and the "This repeats a pattern…" paragraph is stripped, so the paragraph is emitted directly after
`    warranty was reduced.` at two-space indent. In Markdown it then attaches as a lazy continuation
of the **third sub-bullet** (headline prices) rather than of the top-level entry. Cosmetic, but the
compiled `CHANGELOG.md` will read wrongly. Restructuring as a fourth sub-bullet, or removing the
blank line and the indent dependency, fixes it.

### 5.7 ADVISORY A4 — the correction deleted its own receipts

`2a25050`'s fragment carried "`sha256sum -c` failed on `main` (138 OK, 1 FAILED) … verifies again at
138/138". `d86955d` softened both to "failed on `main`" and "the manifest verifies again". The
numbers were the receipt. Under `VERIFY-01` the durable record is weaker without them — and the
vaguer wording is materially what allowed B1 to survive into the head: "verifies again" reads as
timeless, whereas "138/138" is a falsifiable assertion someone would have re-run.

### 5.8 ADVISORY A5 — pre-existing: the corpus README does not list this package

`source_packages/README.md`'s **Packages** table lists three packages and omits
`NSO250MW_Commercial_Offers_2026-09-03.MANIFEST.sha256` entirely. A reader of the governing README
cannot discover that the commercial-offer package exists. This is a #1226 gap, **not introduced by
this candidate**, and I do not weigh it in the disposition — but this PR is the natural place to
close it, and it compounds A1: the package is neither indexed in the README nor correctly pinned to
its private location.

### 5.9 ADVISORY A6 — handling note for the coordinator (F6 §10.1 precedent)

Under the F6 precedent the coordinator copies this record into public `docs/`. **I have therefore
deliberately not transcribed any price figure, table row or offer text beyond the fragments the
candidate has already published** (which are the subject of B2 and are quoted only as evidence of
that finding). If B2 is resolved by *removing* the published term text, this record should be
redacted in the same pass, or it will re-publish what the fix removes. Please do not treat this file
as safe to copy verbatim until B2 is decided.

---

## 6. Checks NOT run — declared (`VERIFY-01`)

- **Test suite / lint / type checks — not run.** No Python, config or contract is touched; the diff
  is three text files. `AGENTS.md`'s financial-regression requirement is not engaged.
- **`NSO250MW_checklist_2026-08-21.MANIFEST.sha256` (72 entries) — not verified.** That package is
  manifest-only by design; its files are outside the repository, so it cannot verify here and a
  failure would be meaningless.
- **Byte-level PDF forensics (embedded metadata, producer timestamps, incremental-update objects) —
  not run.** I compared extracted text, which is what the candidate's claims are about. A
  producer-timestamp comparison would strengthen the "silent revision" characterisation but was not
  needed to confirm it: the text differences are decisive on their own.
- **Independent OCR corroboration of the four extractions — not run.** `R26` requires it where
  extraction is sparse or image-only; all four extracts are dense, complete text (16–19 KB each,
  stderr empty), and the two pairs are near-identical, so extraction adequacy is self-evidenced.
- **Legal adequacy of clause 6 reasoning — not assessed.** Out of role; see §5.2 item 2 and §8.

---

## 7. MUTATION ATTESTATION

I made **no** mutation of any kind to `/home/user/dutchbay-epc-model` or `/home/user/dutchbay_rag`.

- **No file** in either repository was created, modified or deleted.
- **No index, ref, branch, tag, worktree, stash or remote** was changed. No `git add`, `commit`,
  `checkout`, `stash`, `reset`, `rebase`, `merge`, `push`, `worktree add`.
- **No issue or PR** was created, edited, commented on, labelled, closed, approved or merged. Every
  GitHub call was a read (`pull_request_read` with methods `get` and `get_check_runs`).
- All scratch artifacts — the three `git archive` extractions and the four MarkItDown extracts —
  were written **outside both repositories**, under the session scratchpad. `git archive` reads the
  object database and touches neither working tree nor index.
- MarkItDown was run with `PYTHONDONTWRITEBYTECODE=1` so that reading the corpus could not create
  the very `__pycache__` artifact this review is about.
- `scripts/compile_changelog.py` was run only with `--check` and `--dry-run`, both documented
  non-mutating; repository cleanliness was re-verified immediately afterwards.
- **This review record, at the single permitted scratchpad path, is the only file I wrote.**

**Before review:**

```
$ git -C /home/user/dutchbay-epc-model status --porcelain
(empty)
```

**After review:**

```
$ git -C /home/user/dutchbay-epc-model status --porcelain --untracked-files=all
(empty)
$ git -C /home/user/dutchbay-epc-model rev-parse HEAD HEAD^{tree}
d86955da55e1af33f1f0772367cc887ae304d3fa
63e5a92e581a1ec21937f71d530b5ce300fc6b76
$ git -C /home/user/dutchbay_rag status --porcelain --untracked-files=all
(empty)
$ git -C /home/user/dutchbay_rag rev-parse HEAD
133833a67549000850e74d9a72ff9d962891f405
```

**Both repositories were clean when I finished, at the same commits and tree I bound to.**

---

## 8. Authority boundary

This record is a **documentation / evidence-record review** under `RECRUIT-01`. It is `REJECT` for
the exact commit `d86955da55e1af33f1f0772367cc887ae304d3fa` / tree
`63e5a92e581a1ec21937f71d530b5ce300fc6b76` / base `4082ac57283fb8c3fea5af2c649e863212dd9fd9` and
nothing else. Acceptance or rejection transfers to no other implementation, tree or base; any
further delta — including the one-line fix for B1 — **requires a fresh SHA-bound review**, and the
base fast-forward carve-out does not apply, because that carve-out covers only a base advance and
never a change to the candidate's own tree.

This disposition confers **no merge authority** and blocks none by itself — `MERGE-01` makes the
required-check set the merge boundary, and a review that is genuinely required belongs in that set
rather than as an unwritten extra gate. It confers no achieved grade, no report-grade, and no
release, deployment, audit, lender or Board authority. It lifts no `HOLD`.

It carries **no authority whatever over the confidentiality question in B2**. Whether Envision's
offer terms may be published on a public repository is a project-owner decision on recorded
authority, following the precedent this corpus already sets for the 27 August reversal. My finding
is confined to what is within a documentation reviewer's competence: the committed record currently
describes itself falsely, and the widening was neither disclosed nor justified.

### Handover point — this record is work product (`RECRUIT-01` / `PERSIST-01`, F6 §10.1)

`RECRUIT-01`: *"Review records and dispositions are WORK PRODUCT: write them to `docs/` the moment
they land — a review chain that lives only in a session's context is lost, and the pass must be
redone."* As a strictly read-only reviewer with no writer lease I **cannot** write into the
repository; my lease permits this one file outside it. **The coordinator (sole writer) must transfer
this record into `docs/`** — subject to the redaction caveat in A6, which should be settled first.
Flagging rather than acting is the correct behaviour under the lease, but it is a real outstanding
step.

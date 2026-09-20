# Framework compliance review — today's work

**Date:** 20 September 2026
**Scope:** dutchbay-epc-model PRs #1272, #1273 (merged) and #1274, #1276, #1278, #1280, #1282
(open drafts); DutchBay_RAG Kalpitiya ingestion and comparison write-up.
**Method:** read against the canonical ruleset, the PR diffs and the git history directly —
not against any thread's summary of them.

> **Status at filing.** The review below was carried out against `main` at `b3bd141`, when #1274,
> #1276, #1278, #1280 and #1282 were open drafts. By the time this record was committed, all five
> had merged (`main` at `c19d8e8`), and #1284 had landed the changelog-fragment heading guard that
> section *Finding A* records as an open defect found during #1272. The findings are preserved as
> they were made; only this note is added. Read the per-PR table at the end as the state on
> 20 September, not as current merge status.

---

## Verdict

**Nothing already merged breaks a rule.** Both #1272 and #1273 merged onto a current main with
every required check green, complete receipts, their own changelog fragments, and no KPI moved.
There is nothing to unwind.

**Four of the five drafts can proceed:** #1276, #1278, #1280, #1282. **#1274 cannot merge as it
stands** — it is one commit behind main and must be refreshed first.

The two real problems found are **not in today's diffs**. One is a contradiction inside the
governance documents themselves; the other is that the retrieval-repo work was never pushed and
is not recoverable from here.

---

## Where the four frameworks are actually defined

All four are defined in one place: **`go_with_the_flow_rules_v3_0_clean.csv`** at the root of
`dutchbay-epc-model`. It carries 74 rules, all `active`, and it is the canonical source —
`tests/lint/test_gwtf_canonical_source.py` pins it by name and fails if the bootstrap paths point
anywhere else.

| Name | Where | Canonical expansion |
|---|---|---|
| **GWTF** | the CSV itself | **Go-with-the-Flow** — the 74-rule ruleset. `GOV-01` binds AI-assisted work to it |
| **CASPER** | row `FRAMEWORK-01` | **Clear API Surfaces with Predictable Error Responses** |
| **CESSPIT** | row `FRAMEWORK-02` | **Config Explicit, Schema Strict, Pre-flight Integrity Tests** |
| **CCCDIR** | row `FRAMEWORK-03` | **Contracts Centralized, Compliance Documented, Import Relationships explicit** |

CASPER and CESSPIT carry documented secondary meanings in the same rows (Contract-Assured
Scenario Pipeline; Config-Enforced Schema Safety Pipeline Integration Triad), both marked active
and complementary. `docs/H01_WIND_REVIEW.md:71` quotes these same definitions and is consistent
with the CSV.

**Nothing had to be inferred from the acronyms.** But see Finding A — three other documents in
the repo give conflicting expansions.

---

## Per framework

### GWTF — Go-with-the-Flow ruleset (74 rules)

**What it requires (the rules today's work actually engages):**

- `R23` / `R25` / `GOV-02` — branch from current origin/main, PR, green required CI, never commit
  to main; merge only when the branch is current.
- `MERGE-01` — merge as soon as required CI is green; do not hold a green PR for a per-PR
  go-ahead. Green means *every* required check on the *exact* head, no conflict, not behind.
- `VERIFY-01` — a claimed check without a receipt is not a check. Every PR records command +
  result per check; a check not run is declared as `not run — <reason>`, never left silent. A new
  guard ships with the negative control showing it fires.
- `DELIVERY-01` — dolphins, not whales: one small, complete, independently revertable change per PR.
- `DOC-02` — anything that can move IRR/DSCR/NPV updates the changelog and bumps VERSION.
- `TEST-01` — finance-material code answers to an oracle that did not originate in the same change.
- `R24` — docstring-first, Google style with Args/Returns/Raises; external docs minimised.
- `R26` / `DATA-01` — PDFs go through the governed MarkItDown toolchain; ingestion captures every
  data point with source locations, nothing dropped.
- `PERSIST-01` — checkpoint durable state early and often to survive interruptions.

**Followed:**

- Every one of the seven PRs is branch-based onto main, dolphin-sized, with its own changelog
  fragment under `changelog.d/`. History is clean and linear: `5ab8f68 → 4a0778d (#1273) →
  b3bd141 (#1272)`. No direct commits to main.
- `VERIFY-01` is followed unusually well. All seven carry a receipts table with real commands and
  real output, and — the part that usually slips — explicit `not run — <reason>` rows. #1274
  declares that the full suite could not run locally and names CI as the substitute; #1272 and
  #1273 declare that lint/format/type checks were skipped because no Python changed. The gate
  enforces this rather than merely inviting it: `EXEMPT_AUTHORS` in
  `scripts/ci/check_pr_receipts.py` is `{dependabot, github-actions, copilot, renovate}` and
  **does not include `claude[bot]`**, so every pull request reviewed here had to satisfy it. The
  checker also rejects a Result cell of `none`, `n/a`, `tbd`, `-` or the template's own worked
  example, so a row cannot be closed with a word that says nothing.

  *Corrected 2026-09-20, after filing.* An earlier draft of this review stated the opposite — that
  `claude[bot]` was exempt and the receipts were voluntary. That was wrong. It was disproved by
  this record's own pull request (#1285), where the gate failed a `claude[bot]`-authored PR for a
  Result cell reading `none`. The error is recorded rather than quietly overwritten, because a
  compliance review asserting a gate is weaker than it is would licence exactly the silence
  `VERIFY-01` exists to prevent.
- `VERIFY-01` clause 5 (new guard ships with its negative control) is met where it applies. #1274
  records the script failing with the library uninstalled (`FAIL harfbuzz_subset is not None`,
  exit 1) and a separate check that check 4 is not vacuous. #1276 ships rejection tests per knob.
- `MERGE-01` was honoured on both merged PRs: all 20 checks green on the merged head, including
  `Verification receipts (VERIFY-01)`, `Coverage Gate (Python 3.12)` and `Security Scan`. Both
  branches were current at merge — #1272 was rebased onto #1273's result at 08:40:19 and merged
  at 08:47:43.
- `TEST-01`'s independent-oracle clause is met explicitly. #1276 names the committed scenario set
  and its frozen summaries — which predate the change — as its oracle rather than relying on the
  tests it introduces. #1282 goes further and converts a docstring parity *claim* into an executed
  test across the whole curve store.
- `R24` — #1274 found and fixed its own docstring gap mid-PR (commit `1e83ef3`) and recorded that
  the `test_docstring_coverage` ratchet covers only `api/`, `analytics/` and `finance/`, so
  `scripts/` was silent where the rule was not. #1280 *reduces* external documentation, 241 lines
  to 101, replacing copied figures with pointers.
- `R26` / `DATA-01` in the retrieval work — MarkItDown **0.1.7**, exactly the pinned version
  (`requirements.txt:165`), corroborated by a second extractor with 45/45 rows agreeing, and a
  parser that refuses to emit unless both agree. Caveats, uncertain values and document defects
  are all recorded rather than dropped.

**Not followed:**

1. **#1274 is one commit behind main** (base `4a0778d`, main `b3bd141`). Under `R25` step 7 and
   `MERGE-01` it is not mergeable until refreshed. #1276, #1278, #1280 and #1282 were all moved
   onto `b3bd141` and are current.
2. **`PERSIST-01` and `R25` step 6 failed in the retrieval repo** — see Finding B. This is the
   one genuine rule breach in today's work.
3. **A disclosed deviation, not a breach:** #1273 hand-edited the `jupyter_server` pin rather
   than regenerating via `make lock`, which the lock header prescribes. The PR states this
   plainly, gives the reasoning (a full relock mixes unrelated pin movement into a security fix),
   cites the precedent (#1256), and evidences it (2.21.0's requirements are byte-identical to
   2.20.0 — same 43 specifiers). Declared rather than silent, which is what `VERIFY-01` asks for.

---

### CASPER — Clear API Surfaces with Predictable Error Responses

**What it requires:** clean documented interfaces with consistent error types; optional
dependencies fail gracefully **at call time, not import time**, with actionable messages; analytics
exports carry CASPER metadata.

**Followed:** #1274's new guard is CASPER-shaped — it names which of its four checks failed rather
than collapsing to a generic "PDF rendering broken", writes nothing to disk, and restores both the
patched `Font.subset` and the logger level in a `finally`. #1278 and #1280 both reaffirm the
call-time import guards in `arco_assessment.py` and the `[wind]` extra, so the packages import
cleanly without the heavy geoscience dependencies.

**Not followed:** nothing found.

One deliberate and correctly-documented exception is worth knowing about: `DBPL-01` overrides the
CASPER degradation default for DBPL PDFs — there `require_dbpl_stack()` must fail loud, because
the PDF *is* the deliverable. #1274 operates in exactly that territory and is consistent with it.

---

### CESSPIT — Config Explicit, Schema Strict, Pre-flight Integrity Tests

**What it requires:** all scenario parameters in YAML/JSON, never hardcoded; strict validation
before execution; **no silent defaults or fallbacks for critical parameters**; error messages that
name the exact config path and expected structure; no `strict=False` bypass in production.

**Followed — this is the framework today's work advances most.** #1276 is a direct CESSPIT
implementation. It closes four silent-default defects at config consumption:

| Knob | Was | Now |
|---|---|---|
| `p50_haircut_pct` | `-10.0` accepted, raised bankable P50 464.4 → 521.2 GWh — a conservatism knob running backwards | rejected, band `[0, 100)` |
| `correlation` | `5.0` accepted, silently clamped to 1.0 inside `systematic_sigma_pct`, then the raw `5.0` written into the summary's own provenance block | rejected, band `[0, 1]`; reported value is now by construction the one the maths used |
| air-density pair | one of two declared silently skipped the IEC 61400-12-1 correction, moving net P50 +4.33% with no error and no log line | half-declared pair is a config error; neither-declared stays legal and now logs |
| `life_years` | `0` became 1 inside `combined_sigma_pct` | rejected, must be ≥ 1 |

Each error message names the full config path and why the band matters. `bool` is rejected
explicitly because it is an `int` subclass. The kernel clamps are retained as defence in depth so
no other caller changes behaviour. The one remaining silent default — the no-EYA haircut — is
logged rather than hidden, which is the CESSPIT-correct treatment.

**Independently verified:** I re-ran #1276's "every committed scenario regenerates unchanged"
claim myself across all 58 committed scenario and config files. **Zero** would be rejected by the
new guards. The KPI-neutral claim holds.

**Not followed:** nothing found.

---

### CCCDIR — Contracts Centralized, Compliance Documented, Import Relationships explicit

**What it requires:** result types centralised in `contracts_v14`; analytics imports only from
`contracts_v14` and the `evaluate_with_overrides()` gateway; import boundaries documented;
compliance written down.

**Followed:** no PR today introduces a new `finance/ → analytics/` import edge or imports
evaluation internals — #1276 and #1282 touch module interiors and docstrings only. The
"compliance documented" half is served well: #1278 corrects three superseded AEP headlines
(402.6 and 483.6 GWh) that had been sitting in live docstrings, replacing them with the committed
464.3 GWh and stating explicitly why the old figures were retired. #1282 documents which parts of
`bankable_aep.py` the lender path actually calls, so a reviewer looking for the live gross-AEP
maths no longer reads dead code. #1280 rewrites the wind README as pointers rather than copies,
with `tests/docs/test_module_reference_covers_wind.py` keeping the module map complete.

**Not followed:** nothing in the diffs. But CCCDIR's own "compliance documented" clause is what
Finding A breaches at the repository level.

---

## Finding A — the governance documents contradict each other on what three of the four mean

The canonical CSV is unambiguous. Three other tracked documents are not, and they disagree with it
and with each other:

| Source | CESSPIT | CASPER | CCCDIR |
|---|---|---|---|
| **`go_with_the_flow_rules_v3_0_clean.csv`** (canonical, test-pinned) | Config Explicit, Schema Strict, Pre-flight Integrity Tests | Clear API Surfaces with Predictable Error Responses | Contracts Centralized, Compliance Documented, Import Relationships explicit |
| `.github/SPRINT_WORKFLOW_CHECKLIST.md` | "Core-Easy-Simple" (as sub-item **C3 of CCCDIR**) | "Clean Architecture" / "Clean separation" (as **C2 of CCCDIR**) | treated as the parent framework |
| `docs/AUDIT_CASHFLOW_V14_FINAL.md` | Correct, Efficient, Structured, Snappy, Proactive, Immutable, Testable | Contract-first, Audit-safe, Service-oriented, Pure, Extensible, Resilient | Config-driven, Clear, Consistent, Defensive, Immutable, Reproducible |
| `docs/SPRINT_16_REORGANIZATION_COMPLETE.md` | "Comprehensive Error Handling" | "Contract-First Design" | "Clear, Complete, Consistent Documentation" |
| `Full Dolphin Rules` — **in the DutchBay_RAG repo root** | Config-Enforced Schema Safety Pipeline Integration Triad | **Capital Analytics, Sensitivity, Portfolio Evaluation Rigor** | Config-Centric Contract-Driven Integration Rules |

This matters because `SPRINT_WORKFLOW_CHECKLIST.md` is the document the sprint process tells a
developer to work through, and it both mis-expands the frameworks and inverts their relationship —
it files CASPER and CESSPIT as sub-items *of* CCCDIR, where the canonical ruleset has them as three
sibling rows, `FRAMEWORK-01/02/03`. Anyone auditing against the checklist is auditing against the
wrong definitions.

This is pre-existing, not introduced today. #1274 independently spotted the same contradiction and
raised it in its own PR body rather than papering over it. Worth a small PR of its own.

### The worst copy is the one in the other repo

`Full Dolphin Rules` — a 2.6 KB extensionless file at the root of **DutchBay_RAG**, carrying
`[2][3]` citation markers, so a pasted research or chat transcript rather than an authored
document — is the most dangerous of the four, because it is *half right*:

- Its CESSPIT and CCCDIR expansions are real. They are the documented **secondary** meanings from
  `FRAMEWORK-02` and `FRAMEWORK-03`, reproduced verbatim — which is exactly what makes the file
  read as authoritative.
- Its **CASPER expansion is invented**. "Capital Analytics, Sensitivity, Portfolio Evaluation
  Rigor" appears nowhere in the canonical CSV (zero matches for "Capital Analytics").
- It then restates the frameworks as things they are not: CCCDIR as "a type safety mandate —
  no dicts, frozen dataclasses, Pydantic, mypy strict" (that is `TYPE-01`/`R15`, not CCCDIR), and
  CASPER as tornado ranking and Monte Carlo tail risk (that is CASPER's MC-integration aspect,
  not the API-surface principle the rule is about).

`AGENTS.md:6-7` states the governing position plainly: the canonical source is the CSV, and even
AGENTS.md itself "is a concise Codex gateway, not a copy." `Full Dolphin Rules` is a copy, it
lives in the repo that does **not** hold the canonical source, and anyone working from it —
particularly on corpus and ingestion work, which is what that repo is for — would believe they
were compliant while auditing against a fabricated CASPER and a mischaracterised CCCDIR.

Recommend deleting it and replacing it with a one-line pointer to the CSV in the model repo.

**Related, smaller:** `DOC-02` states its enforcement as "CI checks verify VERSION and CHANGELOG
changes for PRs touching `analytics/` or `finance/`". No such check exists — only the PR template
mentions Financial impact. Three of today's PRs touch `analytics/wind/` and none bumps VERSION
(still 15.5.0). Each is genuinely KPI-neutral so nothing is owed, but the gate the rule names is
not there. #1276 changing what the model *accepts* is the one case where a reviewer might
reasonably want the Financial impact section filled rather than deleted.

---

## Finding B — the retrieval-repo work is not on any branch that survives

This is the one item that needs action today.

The Kalpitiya ingestion and comparison work is **not recoverable from here**:

- The `DutchBay_RAG` clone in this session is clean on `main`, with no local branch carrying it.
- `git ls-remote --heads origin` shows only `main` and five older branches (`claude/nso-*`,
  `claude/offer-resupply-2026-09-04`, `claude/ltl-ipo-report-ingress`). Nothing from today.
- No Kalpitiya corpus directory exists in the repo at all.

The work was committed to a branch in another session's container and never pushed. Those
containers are ephemeral, so on the evidence available here those commits are gone.

What this costs concretely: the evaluation write-up cites
`extracted/power_curve_en206_10.5_rho1.148.csv` and `registers/parse_power_curve_2026-09-20.py`.
Neither exists anywhere reachable. Those are precisely the `DATA-01` lossless extract and the
dual-extraction guard that make the ingestion reproducible, so **the evidence chain behind the
45-row power curve currently cannot be re-run or audited**, even though the method itself was
sound.

Rules engaged: `R25` step 6 ("push only the feature branch and open a PR") and `PERSIST-01`
("checkpoint durable state early and often to survive interruptions").

**Mitigation:** the two analytical write-ups did survive, as project files
(`Kalpitiya_60MW_Envision_Package_Ingress_Evaluation_2026-09-20.md` and
`Kalpitiya_vs_DutchBay_EIA_Feasibility_Comparison_2026-09-20.md`). The findings are intact. It is
the machine-readable artefacts and the parser that are lost, and re-deriving them means re-running
the ingestion against the source PDFs.

---

## What each thread can do

| PR | State | Verdict |
|---|---|---|
| #1272 | merged | Compliant. Nothing to unwind. |
| #1273 | merged | Compliant. The hand-edited pin is a declared deviation with evidence, not a breach. |
| #1274 | draft, **behind main** | Compliant in content. Refresh onto `b3bd141` before merging. |
| #1276 | draft, current | Compliant. KPI-neutrality independently re-verified across 58 configs. |
| #1278 | draft, current | Compliant. Docstrings only, no behaviour change. |
| #1280 | draft, current | Compliant. Reduces external docs, which is the direction `R24` wants. |
| #1282 | draft, current | Compliant, and the strongest `TEST-01` work of the set. |

Subject in every case to required CI being green on the exact head at the merge boundary, which is
what `MERGE-01` means by green.

Three follow-ups worth their own PRs, none blocking:

1. Delete `Full Dolphin Rules` from the DutchBay_RAG root and replace it with a pointer to the
   canonical CSV — the highest-value of the three, because it is actively misleading and sits in
   the repo where ingestion work happens.
2. Reconcile `.github/SPRINT_WORKFLOW_CHECKLIST.md` with the canonical ruleset (Finding A).
3. Re-run the Kalpitiya ingestion onto a branch that gets pushed (Finding B).

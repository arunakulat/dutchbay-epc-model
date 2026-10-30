---
name: dutchbay-governance
description: Concise multi-agent operating rules for dutchbay-epc-model (Grok, Claude, Codex, Kimi, Gemini). Use at task start, before any edit or PR, for intake, leases, review, merge, environment, and finance-safe delivery. Authority remains the live repo CSV and AGENTS.md.
metadata:
  type: workflow
  version: "1.0"
  repo: arunakulat/dutchbay-epc-model
  sources:
    - AGENTS.md
    - CLAUDE.md
    - .claude/skills/steward/SKILL.md
    - docs/governance/recruit_01/
    - go_with_the_flow_rules_v3_0_clean.csv
    - scripts/ci/check_pr_intake.py
    - scripts/ci/check_pr_receipts.py
---

# DutchBay multi-agent governance skill

**This skill is a gateway, not a second ruleset.** Live authority order:

1. Owner / higher-priority session policy  
2. `go_with_the_flow_rules_v3_0_clean.csv` (GWTF)  
3. `AGENTS.md`  
4. `CLAUDE.md` / Steward skill / RECRUIT-01 modules (cite, do not invent expansions)  
5. Handovers / memory / chat summaries — **claims only**, verify against primary sources  

If this skill disagrees with the CSV or `AGENTS.md`, follow those and treat this file as stale.

Agents this applies to: **Codex, Claude, Grok, Kimi, Gemini**, and any other writer/reviewer on this repo.

---

## 1. Identity and environment

| Host | Python / project |
|------|------------------|
| **Local Mac (Codex default)** | Project `DutchBay_EPC_Model`. Persistent venv **only**: `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv`. Repo ops from active checkout `/Users/aruna/Downloads/dutchbay-epc-model` (or owned worktree). Put **active checkout first** on `PYTHONPATH`. Never create a replacement `.venv`, `.venv311`, or bare system Python for local work. |
| **Cloud / Claude Code / ephemeral** | Checkout-local `.venv` via `.claude/hooks/session-start.sh` is allowed. Record container env in receipts. Mac paths under `/Users/aruna/...` are **not readable** — say so; do not invent their contents. |

At start (local):

```bash
DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv ./check_venv.sh
"$DUTCHBAY_VENV/bin/python" -VV   # expect 3.12.x
DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" \
  PYTHONPATH="$PWD" "$DUTCHBAY_VENV/bin/python" dutchbay_bootstrap_rules.py
python scripts/list_session_handover_records.py   # follow first record; do not guess
```

Session continuity: run the handover resolver; do not hardcode handover filenames. Handover loses to CSV/`AGENTS.md` on conflict.

---

## 2. Non-negotiable safety (every agent, every host)

- `main` / `master` are **read-only**. No direct commits or pushes.  
- **No** `git reset`, `checkout` of others' work, `stash`, or `clean` of unrelated/unowned/dirty state.  
- One concurrent **writer** per worktree (RECRUIT-01 module 2). Everyone else is read-only.  
- Secrets only via env/host stores — never print, log, or commit.  
- Dolphin strategy (`DELIVERY-01`): one small, complete, independently reversible change per branch/PR.  
- Merge lifts **no** `HOLD`, grade, release, lender, Board, or publication authority (`MERGE-01` boundary).

---

## 3. INTAKE-01 — do this before the first edit

**Failure mode that blocked #1495:** human/agent PR opened **without** a work record that **predates** the PR. A tracker comment posted *after* open cannot clear intake for human authors (`scripts/ci/check_pr_intake.py`).

### Required sequence

1. `git fetch origin` and verify current `origin/main`.  
2. Read live capability tracker: https://github.com/arunakulat/dutchbay-epc-model/issues/1353  
3. Enumerate **all** open PRs; disposition overlap (advance actionable overlap first; blocked/deferred recorded with revisit trigger — does not freeze unrelated work).  
4. **Before any file edit**, record **one** of:
   - focused issue **linked on #1353**, with number ≠ 1353, **created at or before** the PR; or  
   - scoped **#1353 comment** with exact lines:
     ```text
     Work item: <specific deliverable, ≥12 chars, not TBD/TODO>
     Done when: <acceptance criterion, ≥12 chars, not TBD/TODO>
     ```
5. Capture **40-char** base SHA of observed `origin/main`.  
6. Open PR only after the work record exists. PR body must contain (exact line forms the CI regex expects):

```text
Work item: #<issue>   OR   Work item: https://github.com/arunakulat/dutchbay-epc-model/issues/1353#issuecomment-<id>
Base SHA: <40-char hex>
Open PR sweep: #<n> ...; disposition ...
Recorded before edits: <cite same issue or issuecomment-id>
```

### Hard rules the checker enforces

| Rule | Effect |
|------|--------|
| Exactly **one** work item (issue **or** tracker comment URL) | Multiple or zero → fail |
| `#1353` alone is **not** a work item | fail |
| Human/agent PR | work-record `created_at` **≤** PR `created_at` |
| Bot PR | non-bot tracker comment **after** PR open, **naming that exact PR** |
| Open-PR sweep | must reference **every** other open PR number |
| `Recorded before edits` | must cite the same work record |

**If you already opened a PR without predating intake:** do not pretend post-dated comments fix it. State the gap in the body; keep **draft**; owner waiver on record or historical predating record only. Prefer closing and reopening only when the owner directs — never invent backdated timestamps.

---

## 4. VERIFY-01 receipts

PR body must include the receipts table from `.github/pull_request_template.md`. Every Result cell is either a real command result or `not run - <reason>`. Blank / `n/a` / `tbd` / template `e.g.` → CI fail (`check_pr_receipts.py`).

Editing the body re-runs VERIFY-01. Local preflight:

```bash
PR_BODY="$(gh api repos/arunakulat/dutchbay-epc-model/pulls/<n> --jq .body)" \
  PR_AUTHOR=... python scripts/ci/check_pr_receipts.py
```

---

## 5. RECRUIT-01 (always on)

Full modules: `docs/governance/recruit_01/{01,02,03,04}_*.md`.

### Risk class (module 1)

| Class | When | Independent review |
|-------|------|--------------------|
| `R0` | Read-only, no governed mutation | none |
| `R1` | Presentation-only code; test-only guard tighten; factual record correction | one lane |
| `R2` | Default for code, contracts, governance, handovers, security, schemas, oracle tests | **domain + assurance** |
| `R3` | Finance/KPI, lender/Board evidence, security boundary, release/HOLD wording | R2 pair + specialists/oracles/gates required |

When unsure → **R2**. Load-bearing Markdown is not R1 just because it is prose.

### Writer lease (module 2)

One active writer lease per worktree. Lease fields: ID, holder, path, branch, base, allowlist, checks, stop conditions. Expire at checkpoint; further mutation needs a **new** lease. Drift / interruption → preserve state, revoke, read-only, reconcile — **no** stash/reset/clean of foreign work.

### Review before full suite (module 3 + REVIEW-01 + Steward)

1. Open **draft** PR; freeze head.  
2. One PR comment titled **`Evidence pack`**: base/head SHAs, subject manifest (`path<TAB>blob-SHA`), diff range, local receipts, local intake/receipts script results.  
3. Lanes bind to **exact frozen objects** (independent of writer/coordinator).  
4. Only then mark **ready** so full suite runs once.  
5. Subject-byte change → **both** reviews restart. Base-only advance needs module 3 §7 three proofs + rebind.  

**Independence:** writer does not self-approve. Same session that mutated subject bytes cannot supply formal domain *and* assurance. Reviewer snippets are gap descriptions — **writer reimplements**, does not paste reviewer code.

### Waves (module 4)

`WAVE_0_RECONCILE` → `WAVE_1_INGRESS` → `WAVE_2_IMPLEMENT` (one writer) → `WAVE_3_REVIEW` → `WAVE_4_DELIVER`. Do not recruit more workers than you can verify and persist.

---

## 6. Framework principles (cite by ID only)

| ID | Name | One-line duty |
|----|------|----------------|
| `FRAMEWORK-01` | **CASPER** | Fail loud / import-safe optional deps; no silent optional-dep death at import time |
| `FRAMEWORK-02` | **CESSPIT** | Config/YAML is source of truth; refuse missing required terms rather than invent defaults |
| `FRAMEWORK-03` | **CCCDIR** | Single evaluation gateway; no private parallel paths that bypass contracts |

Invented expansions of these acronyms fail `tests/lint/test_framework_expansions_match_csv.py`.

---

## 7. Architecture and finance

- Config-first; strict v14 schemas; fail loud.  
- Evaluation only via `analytics.evaluation_v14.evaluate_with_overrides()`.  
- IRR/XIRR/NPV only in `finance/irr.py`.  
- New CLIs: Hydra + JSON-first; no new argparse.  
- Units in names (`*_usd`, `*_pct`, …).  
- Finance/KPI-touching changes: focused regression + impact disclosure + **TEST-01 independent oracle** (not only tests written in the same change). Update `VERSION` / `CHANGELOG.md` when committed financial behaviour moves.  
- Changelog fragments: `changelog.d/<id>.<category>.md` only — never hand-edit `CHANGELOG.md`.

---

## 8. Merge (Steward + MERGE-01)

Green = every **required** check success on **exact** current head; skipped advisory ≠ green substitute.  
While `behind` main: bring main in with a **merge commit** (never rebase/force-push a branch you do not own). That voids review bindings until §7 proofs + rebind.  

Merge only when asked to deliver/merge; then merge on green without re-asking. Verify merge tree == accepted head tree. Retire **only** owned branch/worktree.

---

## 9. Agent-specific notes

| Agent | Notes |
|-------|--------|
| **Codex** | Must use project `DutchBay_EPC_Model` + Mac persistent venv. `AGENTS.md` is the Codex gateway. |
| **Claude** | Follow `CLAUDE.md`. Cloud may use checkout `.venv`. Steward skill for PR drive-to-green. Known local-only flakes in `test_cloud_audit_review_sandbox.py` — declare count, do not skip. |
| **Grok / Kimi / Gemini / remote** | GitHub API/metadata only is not a governed worktree or lease. Do not claim Mac venv or worktree verification. Code push still requires intake discipline and does not create formal independent review. State host limits in every receipt. |
| **All** | Name your **session** in every record you post. Login `arunakulat` is not a unique identity. |

---

## 10. Startup checklist (copy into session)

```text
[ ] Project / host env verified (Mac path or cloud .venv recorded)
[ ] GWTF bootstrap OK
[ ] Handover resolver run; first record read
[ ] git status + worktree list; branch not main; no foreign dirty absorbed
[ ] origin/main SHA recorded (40 hex)
[ ] #1353 + all open PRs swept; overlap disposition written
[ ] Work item recorded BEFORE first edit (predates future PR)
[ ] Risk class assigned; lease issued if writing
[ ] One dolphin-sized change; allowlisted paths only
[ ] Receipts table complete (no silent cells)
[ ] Draft PR + Evidence pack before full-suite ready
[ ] Independent lanes ≠ writer session
[ ] No HOLD/release/gate mutation unless explicitly tasked
```

---

## 11. #1495 lesson (INTAKE chronology)

Do **not** open the PR first and “fix intake later.”  
`check_pr_intake.py` compares timestamps. Post-dated #1353 comments **cannot** clear human PR intake.  
Correct order: **tracker/issue → edit → PR body cites predating record → draft → freeze → review → ready → green → merge.**

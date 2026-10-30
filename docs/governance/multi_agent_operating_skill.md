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

# DutchBay multi-agent operating skill

**Primary multi-agent intake guide.** Load at every agent session start before edits or PRs.

**This skill is a gateway, not a second ruleset.** Live authority order:

1. Owner / higher-priority session policy
2. `go_with_the_flow_rules_v3_0_clean.csv` (GWTF)
3. `AGENTS.md`
4. This skill (`docs/governance/multi_agent_operating_skill.md` / `.claude/skills/dutchbay-governance/SKILL.md`)
5. Handovers / memory / chat summaries — **claims only**, verify against primary sources

If this skill disagrees with the CSV or `AGENTS.md`, follow those and treat this file as stale. Deduplicate agent memory banks and local skill sets against that order (`AGENT-01`).

Agents: **Codex, Claude, Grok, Kimi, Gemini**, and any other writer/reviewer on this repo.

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

---

## 2. Non-negotiable safety

- `main` / `master` are **read-only**. No direct commits or pushes.
- **No** `git reset`, foreign `checkout`, `stash`, or `clean` of unrelated/unowned/dirty state.
- One concurrent **writer** per worktree (RECRUIT-01 module 2). Everyone else is read-only.
- Secrets only via env/host stores.
- Dolphin strategy (`DELIVERY-01`): one small, complete, independently reversible change per branch/PR.
- Merge lifts **no** `HOLD`, grade, release, lender, Board, or publication authority.

---

## 3. INTAKE-01 — primary intake (before first edit)

### Predating rule (hard)

For a **human or agent-authored** PR, the work record must exist **at or before** the PR `created_at` timestamp. `scripts/ci/check_pr_intake.py` compares timestamps. A #1353 tracker comment posted **after** the PR opens **cannot** clear intake for human authors. That is the #1495 failure mode.

**Correct order:** tracker/issue → edit → PR body cites predating record → draft → freeze → review → ready → green → merge.

### Required sequence

1. Fetch and verify `origin/main` (record 40-char SHA).
2. Read live capability tracker #1353.
3. Enumerate **all** open PRs; disposition overlap.
4. **Before any file edit**, record one of:
   - focused issue linked on #1353 (number not 1353), created before the PR; or
   - scoped #1353 comment with:
     ```text
     Work item: <specific deliverable, >=12 chars, not TBD>
     Done when: <acceptance criterion, >=12 chars, not TBD>
     ```
5. Open PR only after the work record exists. Body must contain exact lines:

```text
Work item: #<issue>
   OR Work item: https://github.com/arunakulat/dutchbay-epc-model/issues/1353#issuecomment-<id>
Base SHA: <40-char hex>
Open PR sweep: #<n> ...; disposition ...
Recorded before edits: <cite same issue or issuecomment-id>
```

Bot PRs need a non-bot tracker comment **after** open naming that exact PR.

---

## 4. VERIFY-01 receipts

Every Result cell is a real command result or `not run - <reason>`. Blank / n/a / tbd fails CI.

---

## 5. RECRUIT-01 summary

- Risk: R0 read-only; R1 bounded low-risk (one lane); R2 default code/governance (domain+assurance); R3 finance/KPI/security boundary (R2 plus specialists).
- One writer lease per worktree; expire at checkpoint.
- REVIEW-01: draft → Evidence pack → lanes bind → ready (full suite once).
- Writer does not self-approve; same session that mutated subject bytes cannot formal domain and assurance.

---

## 6. Framework IDs only

`FRAMEWORK-01` CASPER; `FRAMEWORK-02` CESSPIT; `FRAMEWORK-03` CCCDIR. No invented expansions.

---

## 7. Agent-specific operational constraints

| Agent | Constraints |
|-------|-------------|
| **Codex** | Project `DutchBay_EPC_Model` only. Mac persistent venv required. `AGENTS.md` is the Codex gateway. |
| **Claude** | Follow `CLAUDE.md`. Cloud may use checkout `.venv`. Steward skill for PR drive-to-green. Declare known local-only sandbox flakes; do not skip tests. |
| **Grok / Kimi / Gemini / remote** | GitHub metadata is not a governed worktree or lease. Do not claim Mac venv or worktree verification. Code push still requires intake discipline and does not create formal independent review. State host limits in every receipt. |
| **All** | Name your **session** in every record. Login `arunakulat` is not a unique identity. |

---

## 8. Startup checklist

```text
[ ] Ingress this skill (AGENT-01) and dedupe memory against authority order
[ ] Project / host env verified
[ ] GWTF bootstrap OK; handover resolver run
[ ] git status + worktree list; branch not main
[ ] origin/main SHA recorded
[ ] #1353 + all open PRs swept
[ ] Work item recorded BEFORE first edit (predates future PR)
[ ] Risk class assigned; lease if writing
[ ] Receipts table complete
[ ] Draft PR + Evidence pack before full-suite ready
[ ] Independent lanes != writer session
[ ] No HOLD/release/gate mutation unless explicitly tasked
```

---
name: dutchbay-governance
description: Concise multi-agent operating rules for dutchbay-epc-model (Grok, Claude, Codex, Kimi, Gemini). Use at task start, before any edit or PR, for intake, leases, review, merge, environment, and finance-safe delivery. Authority remains the live repo CSV and AGENTS.md.
---

# DutchBay multi-agent operating skill

**Canonical copy:** `docs/governance/multi_agent_operating_skill.md`

Load that path (or this mirror) at session start. Authority order: owner policy; GWTF CSV; AGENTS.md; this skill; handovers/memory as claims only. Deduplicate memory and local skills against that order (`AGENT-01`).

## INTAKE-01 predating rule

Human/agent PRs require a work record **created at or before** the PR. Post-dated #1353 comments cannot clear intake (`check_pr_intake.py`). Order: tracker/issue → edit → PR citing predating record → draft → freeze → review → ready → green → merge.

## Agent constraints

- **Codex:** project `DutchBay_EPC_Model`; Mac persistent `.venv` only.
- **Claude:** `CLAUDE.md`; cloud may use checkout `.venv`; Steward for PRs.
- **Grok/Kimi/Gemini/remote:** no claimed Mac worktree/lease; state host limits in receipts.
- **All:** name the session in every record; one writer per worktree; no self-approve.

See full skill body under `docs/governance/multi_agent_operating_skill.md`.

# Session handover — 11 October 2026: capability and assurance roadmap

## Status and predecessor

This is a scoped successor to `docs/SESSION_HANDOVER_2026-10-07_MERGE_COORDINATION.md`. It adds the source-grounded planning record `docs/CAPABILITY_AND_ASSURANCE_ROADMAP_2026-10-11.md` and a changelog fragment. The 10-07 record's open items and the 10-06 wording it delegates to remain controlling. The 10-05 v15.6.1 record remains the startup record for a new session: read it and follow its bootstrap. This handover changes no model, KPI, governance rule, grade, release, issue state or `HOLD`.

The roadmap is a prioritised to-do document, not authority to implement every item. Its live GitHub observations are bounded to 11 October 2026 around 11:05 UTC and must be refreshed before PR action. The governing source hierarchy remains `AGENTS.md`, the canonical GWTF CSV, applicable `RECRUIT-01` modules, current contracts and evidence, then this planning record.

## Verified startup and live state

- Protected `main` and `origin/main` matched at `f3b674c873b85be629f33ae21a30a6cd74361726`, tree `fc6c581d1868b6a601c8d8955d8948b3e443b528`; the primary checkout was clean and full-history. `git rev-list --count origin/main` returned 1,554; `VERSION` was 15.6.1.
- The governed Python 3.12.14 environment passed `check_venv.sh` with 311 locked distributions; rules bootstrap loaded 74 active v3.0 rows. The handover resolver passed and listed the 10-07 record first; elapsed cloud time was about 47 seconds, a separate faster observation than the approximately 150-second governed run and prior 71-second warning recorded by #1342; the 60-second threshold has already been exceeded intermittently.
- Live open PRs: #1343 draft/green checks; #1344 blocked by the `sympy`/`mpmath` ceiling; #1345 and #1346 green checks pending observed review; #1326 behind and blocked by the `numba`/`llvmlite` ceiling. The roadmap records each head and action. No PR was reviewed, merged or closed in this documentation task.
- Published v15.6.1 remained non-draft and non-prerelease. Issue #1110 remained OPEN with the Board/lender circulation `HOLD`; the F-5 quarterly CFADS/intra-year DSCR bar also remained in force.
- The owner's Mac-only project association and confidential source packages were not verifiable from this cloud runner. No model, QSTS or resource assessment was run for the roadmap.

## Continuation

At the next thread, run the resolver and follow the selected newest record; do not hard-code this filename as a pointer. Read the roadmap for its reconciled priorities, then check the live PR, release, issue, evidence and review states again. A new writer lease and source-specific review are required for each implementation dolphin. The 26 September platform-plan decisions D3, D6 and D7 remain unmade in the latest decision record found; this roadmap does not answer them.

The roadmap should be delivered through its own protected PR with exact-object domain and assurance review under `RECRUIT-01` because it is load-bearing planning documentation. The final PR and merge record, if any, supersede this pre-delivery snapshot. Do not infer merge or acceptance from this file's presence on a branch.

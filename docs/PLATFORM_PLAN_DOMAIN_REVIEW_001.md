# #1296 post-merge review — task-domain record (R-DOM-1, wave 1)

> **Repository copy, 28 October 2026 (#1371).** The record below is the one preserved unedited on
> #1371 in [issuecomment-6459238264](https://github.com/arunakulat/dutchbay-epc-model/issues/1371#issuecomment-6459238264),
> from blob `bc3b4d9de306d4ac2001f0cd76bdd36910ef8a32` (commit `b8cc7d55`, never merged), with two
> changes: this note, and one token on the `reviewer_identity` line. The repository carries no
> model identifiers, so the model name there is withheld. Without this note and with that token
> restored from the #1371 copy, the file has SHA-256
> `7ccdaee3d08253783b30e6980f1e0ac28ffa7339df44799302848aef744d9303`. The coordinator's 22 October
> header below, including its digest and its "unedited" statement, describes that original.

Persisted by the coordinator on 2026-10-22 under `PERSIST-01` and `RECRUIT-01` module 3, for work
item #1371. Everything below the rule is the reviewer's final message, extracted programmatically
from its hand-back call and written unedited. Its UTF-8 bytes, without the single trailing
newline this file adds, have SHA-256 `4a38fb4a58db0f70361f9fa5c947b03942ff643f9ef6b6b231618920a3a2ea61`. The coordinator's reconciliation of this record
with the assurance record is in `docs/PLATFORM_PLAN_REVIEW_RECONCILIATION.md`.

---

```
reviewer_role: task-domain (R-DOM-1), post-merge
reviewer_identity: R-DOM-1, Claude Code subagent (model [identifier withheld in the repository copy]), isolated worktree /home/user/dutchbay-epc-model/.claude/worktrees/agent-a68a23131b1dde93d at 0255c1fd. It was dispatched inside Claude Code session session_01Xmv5MBtYeqKTJvsJXphk6F, the same session ID the implementation record names as #1296's writer and coordinator. The subagent started cold and had no access to the writer's context (see Independence disclosure).
candidate_commit: 5dd220eb4011188924dccd3aa26659c646c9f306. Resolved: cat-file -t = commit.
candidate_tree: 780ee2bf87f9d21edfdc217a111325cf3f62daa9. Verified with git rev-parse 5dd220eb^{tree}.
base_sha: b87ee32f8031a9b81b222c90020ed10af2c18131
merge_base_sha: b87ee32f8031a9b81b222c90020ed10af2c18131. Verified with git merge-base 5dd220eb b87ee32f.
subject_manifest_sha256: bb601ad3f4ecf77711596a57d6c383a410163fa84d68adff47f58834ea189fc8. Verified: 48 lines, two TAB fields each, sorted under the C locale. All 48 blobs equal git ls-tree 5dd220eb, with 0 mismatches. The manifest does not list itself.
delivery_attestation: git diff --name-status b87ee32f 5dd220eb gives 12 added or modified paths: the 11 manifest objects plus docs/PLATFORM_PLAN_SUBJECT_MANIFEST.tsv (blob 58b6b5d8). Against squash e35ea9f2, all 12 are IDENTICAL. Against main 0255c1fd, 10 are IDENTICAL. changelog.d/platform-plan-2026-09-26.added.md (9f8c84a8) is ABSENT from main: a527cda2 (#1312) deleted it after folding it into CHANGELOG.md verbatim (frag.strip() in CHANGELOG.md == True). tests/lint/test_nso_corpus_manifest_integrity.py DIFFERS on main (c9654ebc on the candidate, b7dabfee on main), edited by 673fc485 (#1313). That edit only repoints the NSO anchor's citation from changelog.d/nso-commercial-offer-resupply.fixed.md to CHANGELOG.md and changes one docstring phrase. The PLATFORM-PLAN-HANDLING-2026-09-26 registration is untouched, so the edit has no effect on the disposition. The squash tree 42beea1b equals the tree of merged PR head 12c499c8, NOT the candidate tree 780ee2bf: after the freeze the PR head merged main, bringing in #1231 (d3157e0d) and #1290 (0ff4f74c). No subject blob changed, but subject statements did (DOM-7). Of the 37 other manifest objects, all are identical in the squash. Seven differ on main: AGENTS.md, CLAUDE.md, the GWTF CSV, the PR template, pyproject.toml, scripts/compile_changelog.py and scripts/list_session_handover_records.py. That is drift in evidence and governance files, not in the subject.
corpus_and_rule_identities: Read at 0255c1fd: AGENTS.md blob 6bd82805d7a319d42928b6f97912397e33696b95; CLAUDE.md 90539bb4e8ad0d4add715bdec375e34b9d33316b; go_with_the_flow_rules_v3_0_clean.csv aa210333816b20d3c5a4653c89a6d11fba164bc8 (the candidate's blob is 5102d0cd; compared programmatically, the rows are identical except that INTAKE-01 exists only on main); recruit_01/01 4b5cdfbf7500d9b5abb32400b013bc2d291112df, 02 9c088a835171388da2da71885e119e8dc48db787, 03 b6616416d25859d9e356c3ca25e85fe2d0d8aefc, 04 b2f1963bc8a81fa45809024d3bfa1b8a2013fd2f (git diff --stat 5dd220eb 0255c1fd -- docs/governance/recruit_01/ is empty). Read at the candidate: findings_register.v2.json 5a86e676 and findings_current_state_overlay.v1.json 17dd4a15. The overlay records for every section-7 finding are identical at 0255c1fd.
review_scope: Domain correctness and fair statement of the four docs/SPRINT_21_BOOTSTRAP documents, the corpus area platform_strategy_2026 (plan, README, MANIFEST.sha256 handling note), the successor handover, the implementation record and the changelog fragment, all at 5dd220eb. Also: the guard-test registration as a domain object, the C1 debt-capacity claim, section 3 path:line claims and category calls, section 7 register states, corrections C2–C9, the plan's fidelity invariants, section 8 lanes, risk classes and KPI effects, section 5.7 multi-tenant claims, and whether the owner decisions D1, D2, D4 and D5 are recorded consistently. Out of scope: assurance-role negative controls of the guard, and authority language beyond what bears on the domain.
checks_executed_and_exact_results: C-01..C-24 in the narrative "Checks executed". Each check records its command and exact result.
independent_oracles_or_counterexamples: (1) A C1 oracle in exact rational arithmetic that imports nothing from the repository, run with python -I scripts/c1_oracle.py. It uses a closed-form annuity and a hand-written sculpt over non-flat CFADS [12,11,14,9,10,13,8,15,11,10,9,12,14,7,10], r = 8%, target 1.30. Results: PV(CFADS) = 95.48415137502165; PV(CFADS/1.30) = 73.44934721155512; the ratio is exactly 13/10. The plan's debt, sculpted, gives DSCR 1.00 in every period with a zero end balance. The C1 debt, sculpted, gives DSCR 1.30 in every period with a zero end balance. The plan's debt serviced at CFADS/1.30 leaves 69.898 unpaid (73.2% of the debt). Under a level annuity, capacity = min(CFADS)/1.30 × a(15, 8%) = 46.0895 (min DSCR 1.30). The C1 debt on an annuity gives min DSCR 0.8158, and the plan's debt on an annuity gives 0.6275. The flat case reproduces the writer's receipt: 85.59478687926372 / 65.84214375327979 = 1.3. (2) An engine counterexample (scripts/engine_probe.py on the candidate tree). It shows the canonical sizing path is not the closed form: on the same flat CFADS 10×15 the closed form gives 65.8421, while _solve_gearing_for_dscr plus apply_debt_layer (capex 100, one construction period, sculpted, target 1.30, 8%) gives gearing 0.46, debt 46.0, balloon 0.0, dscr_min 1.3. On the non-flat series the figures are 73.4493 and 55.25. (3) Audit-register counterexample P2-F2-05 against the claim "the code is already correct". (4) A plan-text counterexample against item 30: plan line 66 is matched by finance/equity_distribution_v14_hydra.py:68 and :541-553. (5) A replay of C7 with openpyxl 3.1.5. (6) Primary or secondary web verification for C2, C4 and C8.
predecessor_finding_matrix: PF-1 CLOSED; PF-2 CLOSED; PF-3 NOT_APPLICABLE; PF-4 CLOSED (handling statement and sampled receipts), with an analogous low-grade disagreement recorded as DOM-6; PF-5 CLOSED; PF-6 CLOSED; PF-7 RECURS as a process fact (#1296 was merged without its review chain), recorded as fact rather than a content finding. Detail in the narrative.
findings_and_residual_limitations: DOM-1 high BLOCKS_CURRENT_CANDIDATE (debt sizing is misattributed to the inert closed form, contradicting open finding P2-F2-05). DOM-2 high BLOCKS_CURRENT_CANDIDATE (section 7 and "Eleven items" omit open hold-blocking findings, including two critical ones, and the omission has propagated to roadmap P0.2). DOM-3 low BLOCKS_CURRENT_CANDIDATE (C1 misquotes the plan by dropping "based on", and its capacity definition lacks the sculpting qualifier). DOM-4 medium BLOCKS_CURRENT_CANDIDATE (item 30 omits the existing operating-cash 6-month reserve sweep). DOM-5 low BLOCKS_CURRENT_CANDIDATE (B3 is classed R2 but is finance behaviour, R3). DOM-6 low BLOCKS_CURRENT_CANDIDATE (internal inconsistencies in the executive summary). DOM-7 medium BLOCKS_CURRENT_CANDIDATE (the undispositioned base movement at merge made statements in the handover and analysis false on main, including the handover "trap"). DOM-8 low ACCEPTED_RESIDUAL_WITHIN_SCOPE (C4 overstates "the fixed 30% is ATAD"). DOM-9 low ACCEPTED_RESIDUAL_WITHIN_SCOPE (imprecise line citations). Post-merge, every BLOCKS finding becomes a corrective issue. Detail in the narrative.
hold_and_authority_effect: None. The #1110 Board and lender HOLD is unaffected. This record confers no grade, release, audit, lender, Board, publication, issue-closure or HOLD authority, and it mutates nothing. Because of DOM-1 and DOM-2, the analysis should not be used as a finding map, as docs/CAPABILITY_AND_ASSURANCE_ROADMAP_2026-10-11.md P0.2 and tracker #1353 P0.2 use it, until a corrective change lands. The corrective issue and its linkage to #1353 and #1371 are for the coordinator; this reviewer posts nothing.
disposition: REJECT
mutation_attestation: In the reviewer's worktree, git status --short printed nothing (empty output) and git rev-parse HEAD = 0255c1fd1bb7ec6ddc9a06cb90e8a3df1267a318 (unchanged). Nothing was checked out, committed, stashed, reset or pushed, and no PR, issue or comment was posted. GitHub was read only, with gh api GET calls for PR #1296 metadata and body, compare 5dd220eb...12c499c8, and commit 12c499c8. All scratch files are under /tmp/claude-0/-home-user-dutchbay-epc-model/02df32a2-87ee-5cd7-b1b9-548b823e5157/scratchpad/rdom1b/. pytest ran with PYTHONDONTWRITEBYTECODE=1, -p no:cacheprovider and --basetemp under that scratch directory.
```

## Ingress receipt

**Read (path, commit):**
1. AGENTS.md @0255c1fd: read in full. CLAUDE.md @0255c1fd: read in full, and identical to /home/user/dutchbay-epc-model/CLAUDE.md. INTAKE-01 is new since the candidate and governs work ordering, not this read-only review.
2. go_with_the_flow_rules_v3_0_clean.csv @0255c1fd, parsed with the csv module:
   - Read in full: FRAMEWORK-01, FRAMEWORK-02 and FRAMEWORK-03 (unabridged description and enforcement), plus TEST-01, DOC-02, DOC-03, DATA-01, DELIVERY-01, FIN-01, RECRUIT-01 and INTAKE-01.
   - Compared with the candidate CSV row by row: no row changed, and INTAKE-01 was added.
3. RECRUIT-01 modules @0255c1fd:
   - Read in full: 01 and 03.
   - Read at section level: 04 (ingress, NO_EVIDENCE, receipt).
   - Read headings only: 02.
4. Subject @5dd220eb (git archive extracted to scratch/tree), all read in full:
   - all four docs/SPRINT_21_BOOTSTRAP documents;
   - PLATFORM_DEVELOPMENT_PLAN_2026-09-26.txt, its README and MANIFEST.sha256 (the handling note);
   - SESSION_HANDOVER_2026-09-26_PLATFORM_PLAN.md and PLATFORM_PLAN_IMPLEMENTATION_RECORD.md;
   - the changelog fragment;
   - the candidate's diff to tests/lint/test_nso_corpus_manifest_integrity.py.
5. Evidence @5dd220eb, by targeted line ranges or grep:
   - finance/debt_v14.py: 181-214, 849-920, 1251-1445, 1593-1640, 1984-2097, plus greps.
   - finance/equity_distribution_v14_hydra.py: 68, 351, 476-560; finance/cashflow_v14_tax.py at the cited lines; finance/bess_revenue.py at the cited lines plus grep; finance/tech_types.py 25-44; finance/cashflow_v14_fx.py 43-60; finance/cashflow_v14_contracts.py 1-20.
   - analytics/fx/fx_builder.py 44-53, 395-401, 592; wind_resource/bankable_aep.py at the cited lines plus grep; solar_resource/pv_producer.py by keyword counts; analytics/mc/samplers.py, analytics/three_statement.py, analytics/aep_reconciliation.py:3 and analytics/portfolio/poi_curtailment.py:33.
   - app/api/main.py 100-135 plus grep; app/api/jobs_router.py grep; app/jobs/models.py 76-86; app/api/auth.py 400-415; app/web/routes.py grep.
   - fly.toml, docker-compose.yml, pyproject.toml:23 and its extras.
   - scenarios/dutchbay_lendercase_2025Q4.yaml 455-512, 374-380 plus grep; scenario-level debt_sizing grep over scenarios/*.yaml.
   - docs/FEASIBILITY_REPORT_CONTRACT.md, docs/CURRENCY_NUMERAIRE_DECISION.md, docs/WEB_SERVICE_ROADMAP.md and docs/ARCHITECTURE.md by grep.
   - Both JSON registers, queried programmatically (all 111 records).
   - tests/finance/test_debt_coverage.py 329-330 and 400-520.
6. Main-only context: CHANGELOG.md (programmatic check); docs/CAPABILITY_AND_ASSURANCE_ROADMAP_2026-10-11.md lines 15, 34, 50-51, 87, 93-100; docs/SESSION_HANDOVER_2026-10-05_RELEASE_15_6_1.md lines 5-12; the overlay at 0255c1fd.
7. GitHub, read only: PR #1296 metadata and body; compare 5dd220eb...12c499c8; commit 12c499c8 tree.
8. Web:
   - The FCA "end of LIBOR" page was fetched (primary).
   - EUR-Lex was tried twice (CELEX:32016L1164 and the ELI URL); both returned empty content.
   - Web searches were run for CBSL OPR, the OBBBA 45Y/48E rules, ATAD Article 4 and Sri Lanka IRA section 18.

**Not read:**
- The owner's original chat message is unavailable, so fidelity to what was sent cannot be checked, only internal invariants.
- Files under /Users/aruna/... and the private DutchBay_RAG repository.
- The bodies of issues #1353 and #1371.
- The full guard test (about 1,400 lines; only the diffs).
- RECRUIT-01 module 2 body.
- The CSV rows not listed above (cited ARCH, REFACTOR, MRM, R-rules by ID only).
- docs/H08_DELIVERY_HANDOVER.md, .github/pull_request_template.md, scripts/ci/check_pr_receipts.py, scripts/compile_changelog.py and scripts/list_session_handover_records.py. These are in the manifest but are not domain evidence.
- Primary texts not reached: gov.uk/HMRC CA23220, ag-grid.com, the tigerdata/timescale licence, the OECD Action 4 PDF, the IRA No. 24 of 2017 primary text and amending Acts, and cbsl.gov.lk.
- The handover resolver was not run; it is not needed for a read-only domain review, and the repository is not shallow (rev-parse --is-shallow-repository = false).

## Independence disclosure

This reviewer is a separate subagent instance with a cold context. The Claude-Session ID in its environment matches the writer and coordinator session ID recorded in PLATFORM_PLAN_IMPLEMENTATION_RECORD.md section 2. Section 3 of that record anticipates exactly this arrangement ("distinct subagent instances, started cold"). Whether it satisfies module 3 section 1 ("distinct from the writer, coordinator") is a question for the assurance reviewer and the owner. This record does not resolve it.

## Checks executed (exact commands and results)

**Subject and delivery**

- **C-01** `git rev-parse HEAD`, then `git cat-file -t 5dd220eb...`, `git rev-parse 5dd220eb^{tree}`, `git merge-base 5dd220eb b87ee32f`, and `git rev-parse e35ea9f2 0255c1fd`.
  - Result: `0255c1fd...`, `commit`, `780ee2bf...`, `b87ee32f...`, and both SHAs resolve.
  - `git rev-parse e35ea9f2^` gives `0ff4f74c...`, not b87ee32f.
- **C-02** `git show 5dd220eb:docs/PLATFORM_PLAN_SUBJECT_MANIFEST.tsv > manifest.tsv; sha256sum; wc -l; LC_ALL=C sort -c`, then a comparison of each entry with `git ls-tree -r 5dd220eb`.
  - Result: `bb601ad3…fc8`, 48 lines, sorted, 0 mismatches.
- **C-03** `git diff --name-status b87ee32f 5dd220eb`.
  - Result: 11 A and 1 M (the test file).
- **C-04** Programmatic comparison of `git ls-tree -r` for 5dd220eb, e35ea9f2 and 0255c1fd.
  - Result: as in delivery_attestation.
  - `git diff 5dd220eb 0255c1fd -- tests/lint/test_nso_corpus_manifest_integrity.py` shows the two-hunk NSO edit.
  - `git log --oneline 5dd220eb..0255c1fd -- <test> <fragment>` lists 673fc485 (#1313), a527cda2 (#1312) and e35ea9f2.
  - The fragment-in-CHANGELOG check returned True.
- **C-05** `gh api repos/arunakulat/dutchbay-epc-model/pulls/1296`.
  - Result: merged 2026-09-29T01:42:19Z, merge_commit e35ea9f2, head 12c499c8, base 0ff4f74c.
  - `gh api .../compare/5dd220eb...12c499c8` shows 3 commits ahead: d3157e0d (#1231), 0ff4f74c (#1290), and the merge 12c499c8 (23 files: period_grid_v14.py, subannual_rows_v14.py, the met_mast_617725_2025 area, and others).
  - `gh api .../commits/12c499c8 --jq .commit.tree.sha` returns 42beea1b..., equal to `git rev-parse e35ea9f2^{tree}`.
  - `git ls-tree e35ea9f2 -- finance/period_grid_v14.py finance/subannual_rows_v14.py docs/source_materials/met_mast_617725_2025/README.md` shows all three present.

**Plan fidelity**

- **C-06** `python -I scripts/plan_fidelity.py <tree>/docs/source_materials/platform_strategy_2026/PLATFORM_DEVELOPMENT_PLAN_2026-09-26.txt`:

  | Invariant | Result |
  |---|---|
  | Size | 6378 bytes, 81 newline-terminated lines |
  | SHA-256 | a1be78037cc4bc662541b8e9e6f1b167bb2451c2fe88f68d411fb6b6245bf444 |
  | Terminal newline | exactly one |
  | CR / tab / trailing-space lines | 0 / 0 / 0 |
  | U+2013 en dash | 5 |
  | U+00D7 multiplication sign | 6 |
  | U+2014 em dash | 0 |
  | Other non-ASCII characters | none |
  | Start | "To transform the `dutchbay-epc-model` fr…" |
  | End | "…ewable energy project finance platform.\n" |
  | Inline formula | `$P = \eta \cdot \rho \cdot g \cdot Q \cdot H$` present at line 36 |

  `cd <tree>/docs/source_materials/platform_strategy_2026 && sha256sum -c MANIFEST.sha256` gives "PLATFORM_DEVELOPMENT_PLAN_2026-09-26.txt: OK", "README.md: OK", exit=0.

  Every invariant in the handling note holds, and the README's "81 lines, 6,378 bytes" holds. The original message is unavailable, so fidelity to what the owner sent is unverifiable.

**Section 2 and section 3**

- **C-07** `python -I scripts/sizes.py <scratch>` reads the candidate ls-tree and file bytes.
  - Python line counts: analytics 73979, finance 12303, app 13135, api 841, wind_resource 7033, solar_resource 2700, sum 109991.
  - tests: 392. Top-level scenario YAML: 37. Extras: 14.
  - All section-2 measures reproduce.
- **C-08** `python -I scripts/recount.py <tree>/docs/SPRINT_21_BOOTSTRAP/SPRINT_21_COMPREHENSIVE_ANALYSIS.md`.
  - Result: 38 rows, numbered 1-38, Counter Exists 14, Partial 11, Gap 11, DoesNotApply 2.
    - Exists: 1, 6, 9, 11, 19, 23, 26, 27, 28, 29, 32, 33, 34, 35.
    - Partial: 5, 7, 12, 13, 14, 18, 20, 21, 22, 30, 36.
    - Gap: 2, 3, 4, 8, 10, 15, 16, 17, 24, 31, 37.
    - DoesNotApply: 25, 38.
  - Incorrect markers: 7, 8, 12, 24, 28, 37, 38.
  - The claimed counts reproduce. Spot-checked calls 25 and 30 are contestable (DOM-1 and DOM-4).
- **C-09** `python -I scripts/show_lines.py <tree> 1 <specs>` printed every cited path:line with context. Results are in "path:line verdicts" below.

**Section 7 and the registers**

- **C-10** `python -I scripts/sec7.py <tree> overlay_main.json` and `python -I scripts/sec7b.py <tree> <16 ids>`. Every one of the 16 section-7 findings matches the table:

  | Finding | Severity | Overlay state |
  |---|---|---|
  | P3-COV-03 | critical | open_current_state_not_examined |
  | P2-F4-01 | high | open_current_state_not_examined |
  | P2-F5-01 | high | implementation_delivered_review_pending |
  | P2-F5-02 | high | external_evidence_blocked |
  | P3-COV-05 | high | open_current_state_not_examined |
  | P3-COV-06 | high | open_current_state_not_examined |
  | P3-MCFX-01 | high | open_current_state_not_examined |
  | P5-WIND-003 | high | open_current_state_not_examined |
  | P4-COMPLEX-01 | high | deferred_current_state_not_examined |
  | P2-MC-SENS-02 | high | implementation_delivered_review_pending |
  | P2-F2-02 | medium | open_current_state_not_examined |
  | P2-F3-01 | medium | open_current_state_not_examined |
  | P2-F5-03 | medium | open_current_state_not_examined |
  | P3-COV-08 | medium | open_current_state_not_examined |
  | P2-F4-04 | low | open_current_state_not_examined |
  | P2-F3-05 | low | open_current_state_not_examined |

  - Every one has hold_effect=blocks_board_lender_release.
  - The overlay record is identical at 0255c1fd for all 16.
- **C-11** `python -I scripts/allopen.py <tree> '<keyword regex>'` lists findings outside section 7 that are not baseline-closed.
  - All 111 overlay records carry blocks_board_lender_release.
  - States: open 65, requires_correction 20, deferred 16, delivered_review_pending 5, baseline_closed 4, external_evidence_blocked 1.
  - The omitted findings bearing on assessed items are listed under DOM-2.
- **C-12** `python -I scripts/finding_detail.py <tree> P2-F2-05,P2-F2-07,P3-COV-04,P2-F2-03` and `… P2-F2-01,P2-F4-05,P3-G1,P3-COV-01,P3-G7,P2-MC-SENS-01,P2-F4-02` print titles, corrected claims and canon impact (quoted in DOM-1 and DOM-2).

**Debt sizing**

- **C-13** C1 oracle, `python -I scripts/c1_oracle.py`. Results are in the structured block. The script also printed a hypothetical "engine-rule plateau" line, D = 96.15 with a 100% balloon. The engine probe did NOT reproduce that, so no claim is made that the engine oversizes.
- **C-14** Engine probe:

  ```
  cd <tree> && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<tree> python scripts/engine_probe.py
  ```

  - flat10: helper 65.8421, engine gearing 0.46, debt 46.0, balloon_remaining 0.0, dscr_min 1.3.
  - nonflat: helper 73.4493, engine 0.5525, debt 55.25, balloon 0.0.
- **C-15** `grep -n` on candidate debt_v14.py: `:1374 bind_downside = _truthy_flag(...)`, `:1402` the NOTE "only discounts the dual-DSCR *capacity* detail (lender-pack metadata)", `:1410 detail = size_debt_with_dual_dscr(`, `:1786 config, dual_dscr_detail = _maybe_autosolve_dscr(config, rows)`, `:1962 "dual_dscr": dual_dscr_detail`.
- **C-16** Scenario sizing modes.
  - `ls scenarios/*.yaml | wc -l` gives 37. Files with `debt_sizing: (dual_dscr|auto_dscr|dscr_sculpt)`: 19.
  - `grep -L debt_sizing` gives 18 files, including dutchbay_basecase_2025Q4.yaml (`debt_ratio: 0.7` at :90) and dutchbay_equitycase_2025Q4.yaml (`debt_ratio: 0.4`).
  - The lender case at :457-499 sets debt_sizing dual_dscr and no bind_downside.
- **C-17** `grep -n reserve_balance` and `min_reserve_months` in finance/equity_distribution_v14_hydra.py.
  - `:68 min_reserve_months default=6`; `:541-553` reserve top-up from cf_after_debt and release.
  - There is no draw path (reserve_balance is only set at :485, :547, :552 and :653).
  - `pipeline_v14_enhanced.py:998` imports it, so it is on the production path.

**Other code claims**

- **C-18** grep of the auth gating:
  - main.py :118-132 gates pipeline_router and /sensitivity with get_current_subject.
  - public_router endpoints take `Depends(get_current_subject)` (:506-581), except /token (:255).
  - jobs_router has per-route `Depends(get_current_subject)` (:177, :215, :271, :281) and owner checks returning 404.
  - Public unversioned routes are /health (:143), /health/readiness (:172) and /static; the web router uses cookie authentication.
- **C-19** `grep -n` of the evidence docs:
  - FRC :54 "authorize a Python or native-language rewrite", :60-61 unsupported/supported/assured with no silent inheritance, :86 section 3.1.
  - CURRENCY_NUMERAIRE_DECISION :43-47 aliases, then one file per atomic commit.
  - WEB_SERVICE_ROADMAP :4 "small set of known clients".
  - ARCHITECTURE :34 "~0.05s".
  - fly.toml :61-75 web and worker processes, auto_start.
  - All hold.

**Tests**

- **C-20** On the main worktree:

  ```
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<worktree> .venv/bin/python -m pytest -p no:cacheprovider -q --basetemp=<scratch>/pt_main tests/lint/test_nso_corpus_manifest_integrity.py tests/lint/test_framework_expansions_match_csv.py
  ```

  Result: `65 passed in 6.12s`. This is supplementary and is run on main, not the candidate. The candidate tree cannot run git-based guards outside a repository.
- **C-21** On the candidate tree:

  ```
  cd <tree> && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<tree> python -m pytest -p no:cacheprovider -q --basetemp=<scratch>/pt_cand tests/finance/test_debt_dual_dscr.py
  ```

  Result: `16 passed in 1.85s`. These are pre-existing tests; supplementary.

**Correction C7, external facts and consistency**

- **C-22** `python -I scripts/c7_openpyxl.py <scratch>/xl` gives "openpyxl 3.1.5", "formula view: =A1*A2" and "cached value view: None". C7's receipt reproduces.
- **C-23** External verification:
  - WebFetch of fca.org.uk/news/press-releases/end-libor: "All 35 LIBOR settings have now permanently ceased"; "30 September 2024, the remaining synthetic LIBOR settings were published for the last time".
  - WebFetch of EUR-Lex (both URLs): empty content.
  - WebSearch, CBSL: the OPR was set at 8.00% at the 26 November meeting and took effect 27 November 2024; SDFR and SLFR are now standing-facility rates at ±50 bp (adaderana, newsfirst, dailymirror, ft.lk).
  - WebSearch, OBBBA: wind and solar 45Y/48E terminate for facilities placed in service after 31 December 2027 unless construction begins within 12 months of 4 July 2025. Some sources give July 4 and others July 3 (Sidley, H&K, projectfinance.law).
  - WebSearch, ATAD Article 4: 30% EBITDA, an optional EUR 3m threshold, and an optional exclusion for long-term public infrastructure where the operator, borrowing costs, assets and income are all in the EU (KPMG, Deloitte summaries).
  - WebSearch, IRA section 18: amended by Act 10/2021 and Act 45/2022. One secondary guide (Chambers) states a limit of 4× issued share capital plus reserves, with carry-forward of the disallowed excess. The primary text was not read.
- **C-24** Decision-quote consistency, `grep -l -F` over the subject documents. Results are under DOM-6.

## Path:line verdicts (section 3 and 5.7; at least ten required, 33 checked)

**HOLDS:**
- `pyproject.toml:23` `"pandas>=2.0,<3.0"`.
- `app/web/routes.py:107`: Jinja2Templates.
- `poi_curtailment.py:33`: estimate_poi_curtailment.
- `cashflow_v14_fx.py:43`: `_fx_curve`, explicit or parametric.
- `cashflow_v14_contracts.py:8`: FxHedge, CIP forward, docstring "the stream debt sizing and DSCR run on".
- `fx_builder.py:400`: lkr_eur. `:592`: hedging_coverage_pct. `:52` for item 18: tranche "cny" → CNY.
- `bankable_aep.py:66`: density_velocity_factor (IEC). `:219`: model_wake_loss (Bastankhah-Porte-Agel default).
- `aep_reconciliation.py:3`: annual capacity × capacity factor × 8760.
- `bess_revenue.py:68`: no dispatch simulation. `:121`: `_DEFAULT_MDSC_FLOOR_SOH = 0.70`. `:132`: SUPPORTED_SOH_MODELS. `:741`: augmentation capex. The DoD is linear through EFC = cycles × DoD, and there is no C-rate term.
- `samplers.py:19` LHS and `:105` Sobol.
- `three_statement.py:113` TieOutStatus and `:157` build_three_statement.
- `cashflow_v14_tax.py`: `:174` interest_deductibility bool; `:243` and `:290` loss_carryforward_years required and `>= 0`; `:359` and `:396` straight-line and split straight-line; `:460` build_tax_holiday_map; `:488` `> 0` enables carry-forward; `:495` _apply_loss_vintages.
- `tech_types.py:25-44`: enum-only hydro and run_of_river, gated by allow_unvalidated_flat_cf.
- `debt_v14.py:867` _sculpted_schedule with fee-inside-sculpt (#737); `:1251` _solve_gearing_for_dscr; `:1593` _build_funding with fund_at_close.
- `lendercase.yaml:502` `dsra_months: 6`, with no fund_at_close.
- `app/api/main.py:112-131`, `app/jobs/models.py:81-83` and `app/api/auth.py:409`.
- Item 1's jobs_router routes, item 5's fly.toml, Dockerfile and docker-compose, the existence of all cited modules, and the absence of period_grid_v14.py and subannual_rows_v14.py at the candidate.

**HOLDS with imprecision (DOM-9):**
- `fx_builder.py:52` cited for item 7 as a "CNY curve slot": `:52` is the tranche-currency map, and the CNY curve read is at `:395-397`.
- `debt_v14.py:921` for the "CFADS timeline": `:921` is apply_debt_layer, and `_build_cfads_timeline` is at `:694`.
- Section 5.7's "only /health and /v1/token are public": /health/readiness and /static are also public. Neither is a compute route, so the compute claim holds.

**FAILS:**
- `debt_v14.py:1323` cited for a "dual P50/P99 downside case": it is `_resolve_downside_ratio`, the P90 bankable-downside resolver, reached only when `bind_downside` is true. That is opt-in and absent from the lender case (DOM-1).
- `debt_v14.py:1984` "sizes … Keep the code": true of the function, false as a description of how the repository sizes debt (DOM-1).
- Research notes 2.4 "Straight-line and split straight-line depreciation only": `enhanced_capital_allowance_multiple` (tax :135-143, cashflow_v14.py:306; lender case :377 = 1.5, applies:false) is a wired enhanced allowance. Folded into DOM-2 through P2-F4-05.

## Corrections C2–C9

| Correction | Verdict | Basis | Overstatement |
|---|---|---|---|
| C2 | Holds | LIBOR verified at primary (FCA). CBSL OPR of 27 Nov 2024 verified at multi-outlet secondary. | None |
| C3 | Holds | UK WDA is a reducing-balance pooled allowance (reviewer knowledge; gov.uk not fetched). There is no EU-wide schedule of that name. | None |
| C4 | Holds in substance | The BEPS 10-30% corridor with an optional group ratio, and the ATAD Art 4 30%, EUR 3m and infrastructure options, verified at secondary. The thin-cap versus earnings-stripping distinction is correct. Section 18 is properly hedged and consistent with secondary sources. | "The fixed 30% is the EU ATAD Article 4" implies uniqueness (DOM-8) |
| C5 | Holds | A distribution has no chronology; P50/P90 expresses uncertainty, not resolution. | None |
| C6 | Holds | Joint probability ≤ 10%; percentile direction; FIN-01 None versus 0. | None |
| C7 | Holds | Replayed (C-22). | None |
| C8 | Holds | OBBBA wind and solar termination verified at secondary. Transferability (s.6418) goes unmentioned, which is an omission and not an error. | None |
| C9 | Holds | Against bess_revenue.py:5-9: CEB dispatches and pays an availability-based Capacity Charge. | None |

**Arithmetic in section 5.1 holds:** 25 × 8760 = 219,000 values, and × 8 bytes = 1.752 MB. 10,000 × 25 × 365 = 91.25 million solves.

## Section 8 recommendation

**KPI effects against register canon_impact:**

| Dolphin | Finding | Effect claimed in section 8 | Register canon_impact | Verdict |
|---|---|---|---|---|
| B1 | P2-F4-01 | Moves CFADS, LLCR, PLCR | confirmed, higher CFADS/LLCR/PLCR (+USD 17.32m CFADS) | Consistent |
| B2 | P2-F3-01 | None on canon | none, none_on_canon | Consistent |
| B3 | P3-COV-08 | None while off | potential, lower distributions if added | Consistent |
| B4 | P3-COV-05 | Only when configured from evidence | confirmed, zero DSRA at close | Consistent for the remediation |
| B5 | P2-F4-04 | Only when configured | none | Consistent |
| B6 | P3-COV-03 | To be established | confirmed residual, headline KPIs unchanged | Defensible as a statement about the fix |

- **Risk classes:** B1, B2, B4, B5 and B6 are R3, which is correct. B3 is wrong (DOM-5).
- **Lane A:** stale since the merge (DOM-7).

**Section 5.7 multi-tenant:** all three anchors hold (C-18). Job reads enforce ownership (`_owned_record_or_404`). The recommendations are reasonable.

## Findings (ledger)

### DOM-1: Debt sizing misattributed to the inert closed form, contradicting open audit finding P2-F2-05

**Severity:** high. **Ledger state:** BLOCKS_CURRENT_CANDIDATE.

**Statements affected:**
- Analysis section 1 step 5: "the repository's own debt-sizing function".
- C1: the receipt labelled "repository sizing"; "The code is already correct (`finance/debt_v14.py:1984`). The plan also omits the dual-case sizing the code performs (P50 and a downside case, the binding one governs)".
- Item 28: "Exists … Keep the code".
- Item 27: "dual P50/P99 downside case (`:1323`)".
- Item 25: "Gearing is solved against the real amortisation schedule … Premise does not apply".
- Executive summary key finding 2 ("dual P50/downside DSCR sizing" exceeds the plan) and key finding 3 ("checked numerically against the repository's own function").
- Research notes 2.4 row 1.

**Evidence:**
1. plan_debt `:1786` → `_maybe_autosolve_dscr` resizes `debt_ratio` through `_solve_gearing_for_dscr` (`:1251`), a scan over apply_debt_layer. `size_debt_with_dual_dscr` is called only at `:1410`, to fill the `dual_dscr` metadata key (`:1962`). The code's own note at `:1402-1408` calls it "lender-pack metadata".
2. Register P2-F2-05 (medium, open, overlay open_current_state_not_examined, blocks_board_lender_release): "Dual-DSCR closed-form lender-pack block is inert and self-contradicting: min_dscr_p50 is a tautology, the P99 constraint can never bind, downside_impact_pct is reported negative, and debt_sized is 33.6% above the real solved debt". Its canon_impact reads "Verified that plan_debt's resize uses solved_gearing only". The analysis says it cross-checked every finance item against this register, yet calls this code correct and says to keep it.
3. `bind_downside` (`:1374`) is opt-in and unset in the lender case, so no downside case governs canonical gearing. `:1323` is a P90 resolver, not a P99 one.
4. DSCR-solved sizing is opt-in (docstring "Opt-in DSCR-based debt sizing"). 18 of 37 top-level scenarios use static gearing, including dutchbay_basecase_2025Q4 at `debt_ratio: 0.7`, literally the plan's "70% Debt / 30% Equity". Item 25's "Premise does not apply" therefore holds only for the lender case and the other 18 DSCR-mode scenarios.
5. Engine counterexample (C-14): on identical CFADS, the engine's sized debt (46.0) differs from the closed form's (65.84).

**Not affected:** C1's correction of the plan's literal formula is right (oracle 1).

**Consequence:** a later session following roadmap P0.2 or Lane B would treat `:1984` as the sizing engine and an accepted mechanism.

**Corrective:** cite `_solve_gearing_for_dscr` and `_maybe_autosolve_dscr` as the sizing path; state that it is opt-in and which scenarios use it; re-grade items 25, 27 and 28; cite P2-F2-05, P2-F2-07, P2-F2-03 and P3-COV-04; relabel the C1 receipt as "closed-form capacity helper".

### DOM-2: Section 7 and the "Eleven items" count omit open hold-blocking findings on assessed items

**Severity:** high. **Ledger state:** BLOCKS_CURRENT_CANDIDATE.

**Statements affected:** analysis section 3 summary "Eleven items touch at least one open audit finding (section 7)", executive summary key finding 4, and the changelog. The changelog text is now in CHANGELOG.md on main.

**Omitted findings, by item.** All are blocks_board_lender_release and none is baseline-closed:

| Item | Omitted findings |
|---|---|
| 6 | P3-G7 (medium, curtailment placeholder) |
| 8 | P2-F4-02 (medium, two tax-rate ladders with a silent 0.0 fallback) |
| 11 | P3-G1 (CRITICAL, zero on-site measurement); P3-G2 (high); P3-G3, P3-G4 (medium); P3-G6 (low, open-reference turbine curve); P4-DC-1 (medium, deferred); P3-MCFX-05 (medium, Weibull knob) |
| 21 | P2-F4-05 (medium, enhanced capital allowance wired but off, no statute) |
| 25 / 27 / 28 | P3-COV-01 (CRITICAL, DSCR threshold needs transaction-specific challenge); P3-COV-04 (high, low solved gearing is CFADS-constrained); P2-F2-05 (medium); P2-F2-07 (low); P2-F2-03 (low) |
| 26 | P2-F2-01 (high, DSCR/LLCR/PLCR measured on CFADS USD 6.03M smaller than the published CFADS) |
| 33 | P2-MC-SENS-01 (high, delivered, review pending); P5-SA-001 (medium); P5-SA-002 (medium, deferred) |
| 34 (counted) | Also omits P3-MCFX-03 (high), P3-MCFX-07 (high, 100,000-trial run not evidenced), P5-MC-002 (medium, Sobol claim) |
| 32 (counted) | Also omits P2-F3-02 (low) |

**Count:** at least 19 of 38 items touch an open finding, not 11.

**Propagation, demonstrated:** docs/CAPABILITY_AND_ASSURANCE_ROADMAP_2026-10-11.md P0.2 cites this "Sprint 21 audit map". It lists only P3-COV-03, P2-F4-01, P2-F3-01, P3-COV-05 and P3-COV-08, and adds "The debt engine already sculpts against DSCR; a replacement sizing engine is not indicated". Critical P3-COV-01 and high P2-F2-01 and P3-COV-04 are absent from the debt-and-tax adjudication lane.

**Corrective:** a complete item-to-finding map generated from the register, or an explicit "non-exhaustive" qualifier with the omitted IDs listed.

### DOM-3: C1 misquotes the plan, and its capacity definition lacks a qualifier

**Severity:** low. **Ledger state:** BLOCKS_CURRENT_CANDIDATE.

**Misquote:** plan line 58 reads "Calculate maximum debt capacity *based on* the NPV of CFADS discounted at the debt interest rate", directly after line 57, "sculpt principal repayments to hit a target DSCR (e.g., 1.30x) in every period". The analysis writes "The plan sizes maximum debt as 'the NPV of CFADS …'". The executive summary writes "the plan sizes maximum debt as the NPV of CFADS", and the changelog writes "the plan's debt-capacity formula sizes at 1.00x … oversizes debt by the target DSCR factor". Read with "based on" and line 57, the plan is ambiguous rather than definitely wrong. Only the literal reading oversizes by exactly the DSCR factor.

**Missing qualifier:** "Debt capacity is … CFADS divided by the target DSCR, discounted …" holds for sculpted repayment only. Under level annuity repayment, capacity is min(CFADS)/DSCR × a(N, r). The oracle gives 46.09 against 73.45, a factor of 1.59 on non-flat CFADS.

**Corrective:** quote the plan exactly, call it underspecified, and qualify the definition.

### DOM-4: Item 30 omits the operating-cash 6-month reserve sweep that already exists

**Severity:** medium. **Ledger state:** BLOCKS_CURRENT_CANDIDATE.

**Plan text:** line 66 reads "DSRA … Automatically sweep cash to fill a 6-month debt service reserve".

**Code:** the production waterfall (finance/equity_distribution_v14_hydra.py `:68` sets min_reserve_months default 6; `:541-553` tops up from cash after debt service and releases excess) does exactly that. It is on the production path (pipeline_v14_enhanced.py `:998`).

**What item 30 says instead:** it describes only fund-at-close and grades the item Partial. Its recommendation offers "cash-funded" as a structure still to configure, which risks B4 duplicating an existing mechanism.

**The real gaps:** the reserve is never drawn when CFADS falls short (there is no draw path; related to P2-F3-01), it is not funded at close in canon, and there is no letter-of-credit option. The register's P3-COV-05 detail ("zero DSRA at close") is consistent with that framing.

**Corrective:** restate the state and gaps for item 30. Consider re-grading it to Exists with gaps; the recount then becomes 15/10/11/2, or 16/10/11/1 once DOM-1 re-grades item 25.

### DOM-5: B3 under-classified as R2

**Severity:** low. **Ledger state:** BLOCKS_CURRENT_CANDIDATE.

B3 adds a major-maintenance reserve and multi-tier lock-up to the equity waterfall. Its default is off, but it is still new finance behaviour, and once configured it changes distributions and equity IRR.

The section 8 table classes it R2. That contradicts module 1 section 3 (R3 covers "Finance/KPI behavior"), the analysis's own section 6 ("Finance dolphins are R3_CONSEQUENTIAL"), and B2, which is also "None on canon" yet classed R3. A later session would recruit too light a review chain.

### DOM-6: Internal inconsistencies in the executive summary

**Severity:** low. **Ledger state:** BLOCKS_CURRENT_CANDIDATE, because statements are false.

| Statement | Executive summary location | Conflicts with |
|---|---|---|
| "The project owner decided D1, D2 and D4" | Line 5 | Its own line 71 ("D1, D2, D4 and D5"), the README, the analysis, the handover and the changelog |
| "a multi-tenant product that has not been decided" | Key finding 5 | D2 as recorded: "multi-tenant is the planned extension" |
| "Lenders test coverage quarterly or semi-annually" | Key finding 6 | Analysis section 5.1, which relays #1225's "at least quarterly"; semi-annual is not "at least quarterly". The #1225 phrasing is itself questionable PF practice, where semi-annual testing is common. |

The decision quotes D1 "yes", D4 "keep on public branch" and D5 "follow repo rules, harness, frameworks" are otherwise identical across the analysis, executive summary, handover, implementation record and handling note. D2's quote is identical but line-wrapped in the handover.

### DOM-7: Base movement at merge was not dispositioned, so subject statements were false on main from e35ea9f2

**Severity:** medium. **Ledger state:** BLOCKS_CURRENT_CANDIDATE, graded as the module 3 section 7 carry-forward would grade it pre-merge.

The squash tree (42beea1b, equal to PR head 12c499c8) includes #1231 (finance/period_grid_v14.py, subannual_rows_v14.py) and #1290 (the met-mast corpus). Statements that became false on main:

- The handover "Traps": "`finance/period_grid_v14.py` is **not** on `main` … re-proposed with A2 in draft #1231. Text that treats Sprint 20 A1 as landed is stale". This now tells a session to distrust correct text.
- Analysis item 12, section 5.1 and Lane A ("draft #1231", "complete review cycle 3 and merge").
- Item 11 "#1290 is in flight" and Lane C "Measured wind data (#1290)".
- Research notes 2.4 "Sub-annual modules absent from main". This row is dated to b87ee32, but it was relied on at merge.

**Mitigation:** the 2026-10-05 handover supersedes the predecessor's "live release/cleanup snapshot", and the roadmap states that #1231 merged. The 09-26 handover's trap is not expressly withdrawn.

**Corrective:** a PERSIST-01 correction that withdraws the trap and updates the Lane A and #1290 status.

### DOM-8: C4 overstates "The fixed 30% is the EU ATAD Article 4"

**Severity:** low. **Ledger state:** ACCEPTED_RESIDUAL_WITHIN_SCOPE.

A 30% fixed ratio is also the top of the BEPS corridor itself and is used in other regimes (for example UK CIR and US s.163(j) on ATI). The substantive corrections stand: the thin-cap versus earnings-stripping conflation, the corridor, and the infrastructure exclusion.

Accepted because no reliance in the subject turns on the uniqueness. Recommended for the same corrective edit. HOLD effect: none.

### DOM-9: Citation imprecision

**Severity:** low. **Ledger state:** ACCEPTED_RESIDUAL_WITHIN_SCOPE.

The imprecise citations are `fx_builder.py:52` for item 7, `debt_v14.py:921` for the CFADS timeline, and the public-route list in section 5.7. In each case the substance holds within a few lines or within the scoped claim. Recommended for the same corrective edit. HOLD effect: none.

## Predecessor finding matrix (detail)

- **PF-1 — CLOSED.** The area manifest verifies (C-06, exit 0). There are no nested manifests and no gitignored or impossible entries. Every tracked file in the area other than MANIFEST.sha256 is recorded. The subject manifest covers all 11 changed objects (C-02). The guard passes on main (C-20).
- **PF-2 — CLOSED.** I read all 81 plan lines. They contain no confidentiality marking, prices, counterparty names or personal data, which is consistent with publication clause 3.
- **PF-3 — NOT_APPLICABLE.** No redaction occurred, and the subject contains no review record.
- **PF-4 — CLOSED.**
  - The handling statement exists once, in the MANIFEST header, and the READMEs cite the identifier.
  - The fragment's brief restatement agrees with the note.
  - Sampled receipts reproduce: the C1 numbers, the area sha256sum, the section-2 measures and the openpyxl replay.
  - An analogous disagreement over a different fact (the decision set) is DOM-6.
- **PF-5 — CLOSED.** The subject contains no CASPER, CESSPIT or CCCDIR expansions (grep), and test_framework_expansions_match_csv passes on main.
- **PF-6 — CLOSED.** Every subject document states "not independently reviewed" or "review pending". No acceptance is asserted.
- **PF-7 — RECURS, recorded as a process fact and not a content finding.**
  - #1296 merged 2026-09-29 as squash e35ea9f2 with no RECRUIT-01 review. The first dispatch on 2026-09-26 returned NO_EVIDENCE.
  - The merge also carried an undispositioned base movement (12c499c8). Its content consequence is DOM-7.
  - The subject's own handover said "Do not merge on green CI alone".

## Limitations

- The owner's chat message and the evidence held on the owner's Mac were not available. Decisions D1, D2, D4 and D5 are treated as claims, and only their consistent recording was checked.
- External facts were verified at primary level only for C2-LIBOR. Everything else is secondary or reviewer knowledge; EUR-Lex returned empty content.
- The guard tests could not run against the candidate tree outside git and were run on main only.
- No full suite or financial regression was run, which is appropriate because the subject changes no finance code.
- The engine probe uses a synthetic configuration, not the lender case. The magnitude comparison for the lender case comes from the register (P2-F2-05: 91.9M closed form against a 68.8M solved facility).

## Scratch artefacts (not persisted to the repository)

Scripts are in /tmp/claude-0/-home-user-dutchbay-epc-model/02df32a2-87ee-5cd7-b1b9-548b823e5157/scratchpad/rdom1b/scripts/: c1_oracle.py, engine_probe.py, show_lines.py, registers.py, sec7.py, sec7b.py, allopen.py, finding_detail.py, recount.py, sizes.py, plan_fidelity.py and c7_openpyxl.py. The extracted candidate tree is in scratchpad/rdom1b/tree/, and the PR body is in scratchpad/rdom1b/pr1296_body.md.

# #1296 post-merge review — assurance record (R-ASR-1)

Persisted on 28 October 2026 under `PERSIST-01` and `RECRUIT-01` module 3, for work item #1371, as
`docs/PLATFORM_PLAN_IMPLEMENTATION_RECORD.md` section 3.3 asks. Everything inside the fence below is
the reviewer's complete record, copied byte for byte from the file the reviewer wrote
(`pr1296-assurance.txt`, 285 lines, 23,258 bytes). Those lines, each with its line feed, have
SHA-256 `fddbff768f550875dcdd656df342cfde2ada9b093076893e851d851c50143ee0`. The reviewer's summary
is on #1371
([issuecomment-6460171871](https://github.com/arunakulat/dutchbay-epc-model/issues/1371#issuecomment-6460171871)).
The reconciliation of this record with the domain record is in
`docs/PLATFORM_PLAN_REVIEW_RECONCILIATION.md`.

---

```text
RECRUIT-01 ASSURANCE REVIEW RECORD — R-ASR-1 — #1296 platform-plan candidate (work item #1371)
=====================================================================================================

reviewer_role:            R-ASR-1, independent assurance reviewer, read-only
                          (profile: docs/PLATFORM_PLAN_IMPLEMENTATION_RECORD.md section 3.2 at the candidate)
reviewer_identity:        Claude Code cloud session session_0159RRMb3ibRLm7H1vJ5x3L1, project thread
                          "Blind assurance review of #1296"; recruited 2026-10-28T03:33Z by the project
                          coordinator at the owner's request. Distinct from the #1296 writer
                          (session_01Xmv5MBtYeqKTJvsJXphk6F), from the R-DOM-1 lane, and from the earlier
                          R-ASR-1 lane that stood down on 2026-10-28.
date:                     2026-10-28
candidate_commit:         5dd220eb4011188924dccd3aa26659c646c9f306
candidate_tree:           780ee2bf87f9d21edfdc217a111325cf3f62daa9   (verified: git cat-file -p)
base_sha:                 b87ee32f8031a9b81b222c90020ed10af2c18131
merge_base_sha:           b87ee32f8031a9b81b222c90020ed10af2c18131   (verified: git merge-base)
subject_manifest:         docs/PLATFORM_PLAN_SUBJECT_MANIFEST.tsv at the candidate, 48 entries
subject_manifest_sha256:  bb601ad3f4ecf77711596a57d6c383a410163fa84d68adff47f58834ea189fc8   (verified: sha256sum)
delivery_examined:        squash e35ea9f26c8094be4d18a4cf5475d35f25932d4f (parent 0ff4f74c7b18...),
                          PR head 12c499c8eaa599f19fe873a9db2a344482171a4e, current main
                          0cc5a0da09b5da41ea56c9cc154772a00ccd253c
corpus_and_rule_identities:
                          go_with_the_flow_rules_v3_0_clean.csv blob 5102d0cd (candidate): 74 rules, v3.0,
                          all active (dutchbay_bootstrap_rules.py at the candidate). Rows read in full:
                          DOC-03, SPRINT_BOOTSTRAP_PROC_R1, FRAMEWORK-01/02/03, DELIVERY-01, GOV-02,
                          DATA-01, PERSIST-01, VERIFY-01, MERGE-01, RECRUIT-01. RECRUIT-01 modules 1-4 at
                          blobs 4b5cdfbf, 9c088a83, b6616416, b2f1963b. AGENTS.md 98ca2509, CLAUDE.md
                          57400775.

disposition:              REJECT (one veto blocks)
  - frozen subject, judged at its own base b87ee32f:  no finding in BLOCKS_CURRENT_CANDIDATE
  - as delivered on main (e35ea9f2 and since):        ASR-1 BLOCKS_CURRENT_CANDIDATE
  - delivered-bytes attestation: all 12 changed paths in e35ea9f2 are byte-identical to the candidate,
    and the squash tree equals the PR-head tree. The acceptance carry-forward from base b87ee32f to
    delivery base 0ff4f74c LAPSES under module 3 section 7 (see ASR-1).

hold_and_authority_effect:
  None. This record confers no grade, release, audit, lender, Board, publication, issue-closure or
  HOLD authority and lifts nothing. The #1110 HOLD is untouched. A revert of #1296 is not proposed:
  nothing found is content that must not stand on main; ASR-1 is corrected by amending the record.

mutation_attestation:
  No mutation of the repository, any branch, ref on GitHub, PR or issue other than the single #1371
  evidence comment the coordinator's brief asked for (the record's persistence channel). Local to the
  container only: one fetch ref refs/review/pr1296 (= refs/pull/1296/head) in /home/user/dutchbay-epc-model
  and a full-history fetch of main and tags; all negative controls ran in a separate scratch clone
  under the session scratchpad, reset to the candidate after each control (git status empty, verified).
  The shared checkout stayed clean at 0cc5a0da (git status --porcelain empty).

-----------------------------------------------------------------------------------------------------
INDEPENDENCE AND EXPOSURE DISCLOSURE
-----------------------------------------------------------------------------------------------------
Not read, at any point before or after disposing: any #1371 comment (the issue was read only with
issue_read method=get); /mnt/project-files/review-records/2026-10-22/pr1296-domain.txt;
pr1296-assurance-lane-contamination.txt; docs/PLATFORM_PLAN_DOMAIN_REVIEW_001.md; issues #1477-#1483;
any #1296 PR comment or review. Object b8cc7d55 is not present in this container. From the PR branch
I read only `git log 5dd220eb..12c499c8` (three merge-from-main commits) and the two trees, to prove
squash-tree equality.

DISCLOSED EXPOSURE. Before any review work, the session's automatic team-memory recall injected two
notes that state the R-DOM-1 headline: disposition REJECT, DOM-1..DOM-7 BLOCKS_CURRENT_CANDIDATE,
DOM-8/DOM-9 accepted residuals, its comment id and record digest, and that it cites a reconciliation
file that does not exist. The owner's message attached to my brief also says seven DOM findings are
blocking. No finding text, subject, path or reasoning of any DOM finding reached me. I did not use the
headline; every finding below comes from an object check whose command is recorded here. The reader
should still weigh that this lane knew the domain lane rejected.

-----------------------------------------------------------------------------------------------------
INGRESS RECEIPT (module 4 section 3)
-----------------------------------------------------------------------------------------------------
Read in full at the candidate: AGENTS.md; CLAUDE.md (system context); the four RECRUIT-01 modules;
docs/PLATFORM_PLAN_IMPLEMENTATION_RECORD.md; docs/PLATFORM_PLAN_SUBJECT_MANIFEST.tsv;
docs/source_materials/platform_strategy_2026/{MANIFEST.sha256, README.md,
PLATFORM_DEVELOPMENT_PLAN_2026-09-26.txt}; docs/SPRINT_21_BOOTSTRAP/README.md;
docs/SESSION_HANDOVER_2026-09-26_PLATFORM_PLAN.md; changelog.d/platform-plan-2026-09-26.added.md;
the guard diff b87ee32f..5dd220eb and the guard functions it relies on (lines 455-500, 680-762);
SPRINT_21_RESEARCH_NOTES.md sections 1-2; #1371 body; #1296 PR body.
Read by targeted search, not end to end: SPRINT_21_COMPREHENSIVE_ANALYSIS.md and
SPRINT_21_EXECUTIVE_SUMMARY.md (publication, fidelity, authority, HOLD, #1231/Lane A, restricted-term
and framework-acronym searches); the GWTF CSV rows not listed above (rule IDs enumerated only).
Not read: the audit registers and the evidence code the analysis cites (domain-lane ingress; I checked
only whether those objects are pinned and whether the base movement touched them); later handover
records on main; evidence on the owner's Mac; the owner's 26 September session transcript, so every
quoted owner reply ("keep on public branch", "yes", D2, D5) and the received-text fidelity claims are
unverifiable here and are treated as the writer's claims.
Environment: cloud container, /home/user/dutchbay-epc-model/.venv, Python 3.12.3; full history and
tags fetched (git fetch --unshallow --tags origin main).

-----------------------------------------------------------------------------------------------------
review_scope
-----------------------------------------------------------------------------------------------------
Contract boundaries, failure modes, verification quality, disclosure control, authority language and
unintended scope of the frozen subject; the R-ASR-1 minimum method; and the delivered state on main.
Not in scope: the correctness of the evaluation's finance, resource and audit-state claims (R-DOM-1).

-----------------------------------------------------------------------------------------------------
checks_executed_and_exact_results
-----------------------------------------------------------------------------------------------------
Subject identity
 S1  Manifest entries vs candidate tree (git rev-parse 5dd220eb:<path> per entry) -> entries=48 mismatches=0
 S2  Changed paths b87ee32f..5dd220eb -> 12; 11 in the manifest; the 12th is the manifest itself
 S3  The 36 unchanged context entries vs base b87ee32f -> 0 differ
 S4  Delivery e35ea9f2: changed-path set equals the candidate's; all 12 blobs identical
 S5  Tree e35ea9f2 == tree 12c499c8 == 42beea1bbc6025eb366238d286d5235dec8865e5
 S6  The 36 context entries at e35ea9f2 -> 0 differ
 S7  Current main 0cc5a0da: 10 of 12 identical; changelog fragment absent (folded by #1312 a527cda2,
     fragment text found verbatim in CHANGELOG.md, 0 lines missing); the guard differs by one #1313
     hunk pair (673fc485, NSO referrer -> CHANGELOG.md, 2+/2-), not in the platform registration.
     #1371 body's "Changed on main since" row verified true.

Guard registration, independent negative controls (scratch clone at 5dd220eb, guard file run alone)
 N0  Baseline                                                     -> 34 passed
 N1  Remove the PLATFORM-PLAN-HANDLING-2026-09-26 HANDLING_ANCHORS entry
                                     -> 1 failed, 32 passed: test_every_handling_note_in_the_tree_is_registered
 N2  Area README stops citing the anchor, its manifest hash refreshed so only the citation defect remains
                                     -> 1 failed, 33 passed: test_handling_notes_are_stated_once[PLATFORM-...]
 N3  Append one byte to the plan file, manifest unchanged
                                     -> 1 failed, 33 passed: test_recorded_entries_are_present_and_hash_as_recorded[platform_strategy_2026/MANIFEST.sha256]
 N4  New tracked file in the area, not recorded
                                     -> 1 failed, 33 passed: test_every_tracked_corpus_file_is_recorded[platform_strategy_2026]
 N5  Definition line's em dash replaced by a hyphen
                                     -> 1 failed, 33 passed: test_handling_notes_are_stated_once[PLATFORM-...]
 N6  HOSTILE: section 3 (PUBLICATION) of the handling note restated verbatim in the changelog fragment
     and the handover                                             -> 34 passed (not detected)
 N7  HOSTILE: a second, contradictory definition of the anchor in a new nested manifest
                                     -> 4 failed, 30 passed (classification, recorded-file, parent-pin, registration)
 N8  HOSTILE: Sprint 21 README keeps citing the anchor but adds "The plan text is withheld; only its
     hash is recorded (manifest only)"                            -> 34 passed (not detected)
 The registration is effective for everything the guard claims to check (N1-N5, N7). N6 and N8 show
 that "stated once" is enforced as "defined once and cited", not "not restated and not contradicted";
 the test name predates #1296. See ASR-2.

Area manifest and plan-file fidelity invariants
 M1  sha256sum -c --strict MANIFEST.sha256 (area dir, candidate) -> PLATFORM_DEVELOPMENT_PLAN_2026-09-26.txt: OK, README.md: OK, exit 0
 M2  Plan file: 6,378 bytes; 81 LF; 0 CR; one terminal newline, not two; no BOM; starts "To transform",
     ends "project finance platform.\n"; non-ASCII = 5 x U+2013 and 6 x U+00D7, nothing else; the inline
     formula is present on line 36. Every invariant in handling-note section 2 and the area README holds.
     Whether these are the bytes the session received cannot be checked from the objects.

Receipts sample re-run at the candidate (writer ran most at earlier commits; see ASR-4)
 R1  pytest the four focused lint/docs files                      -> 111 passed (writer: 111 at 7458252)
 R2  ruff check / ruff format --check / black --check / isort --check-only / mypy --follow-imports=silent
     on the guard -> All checks passed! / 1 file already formatted / 1 file would be left unchanged. /
     exit 0 / Success: no issues found in 1 source file
 R3  compile_changelog.validate_body(name, non-blank lines) -> returned; compile_changelog.py --dry-run -> exit 0
 R4  requires_grid_study(b87ee32f..HEAD paths) -> 12 paths; Grid Study required: False (writer: 10 paths)
 R5  research notes 2.2 C1 command -> 65.84214375327976 85.5947868792637 1.3 (identical); independent
     closed-form annuity sum(10/1.08^t, t=1..15) = 85.5947868792637, /1.3 = 65.84214375327976
 R6  pytest tests/lint tests/docs -q -n auto -> 3 failed, 653 passed; the three are
     test_cloud_audit_review_sandbox.py (bounded_watchdogs_kill_descendant_after_leader_exits,
     create_transport_watchdog_reaps_on_interrupt_and_eperm, codespace_creation_watchdog_bounds_a_hung_ssh_probe),
     the known container-local family; pre-existing and local, not caused by the subject.
 R7  Handover resolver at the candidate -> exit 0; first SESSION_HANDOVER_2026-09-26_PLATFORM_PLAN.md, then
     H08 (matches the writer). At current main it is no longer first (newest: SESSION_HANDOVER_2026-10-22_...).
 R8  dutchbay_bootstrap_rules.py at the candidate -> 74 rules, v3.0, active=74 (matches research notes 1)

Disclosure, authority and style
 D1  Plan text read in full: no confidentiality marking, counterparty name, price, contract term or
     personal data. Handling-note section 3's description holds.
 D2  Subject docs name the NSO and Kalpitiya projects only as project names (analysis lines 50-51); no
     restricted term found by search; the guard's verbatim-quotation tests pass (N0).
 D3  Authority/HOLD language searched in every changed document: each disclaims authority; none claims
     acceptance, grade, release or a lifted HOLD. The changelog's "Not independently reviewed: the
     RECRUIT-01 domain and assurance review is pending" is accurate and survives in CHANGELOG.md.
 D4  Non-ASCII in the new Markdown: em dash, middle dot, eta, rho, multiplication sign; no emoji (DOC-03).
 D5  No CASPER/CESSPIT/CCCDIR expansion in any subject doc; test_framework_expansions_match_csv.py passes (R1).

Base movement (module 3 section 7)
 B1  Cited repository paths extracted from the subject docs: 61 backtick paths; 18 existing evidence
     objects cited at path or path:line level are not in the subject manifest (analytics/aep_reconciliation.py,
     analytics/contracts_v14.py, analytics/executive_workbook.py, analytics/mc/engine.py,
     analytics/portfolio/generation_aggregator.py, analytics/reproducible_workbook.py,
     analytics/sensitivity/global_sa.py, analytics/sensitivity/optimizer.py, app/api/jobs_router.py,
     app/jobs/redis_store.py, app/reports/report_model.py, app/reports/templates/report.html.j2,
     docker-compose.yml, docs/SESSION_HANDOVER_2026-09-07.md, dutchbay_bootstrap_rules.py,
     finance/equity_distribution_v14_hydra.py, finance/irr.py, run_scenario_analytics_v14.py), plus
     finance/period_grid_v14.py, absent at the base.
 B2  b87ee32f..0ff4f74c (the delivery base): 23 files, +4503. It adds finance/period_grid_v14.py and
     finance/subannual_rows_v14.py: #1231, d3157e0d, merged 2026-09-27T05:06Z, two days before the
     squash at 2026-09-29T01:42Z. Present at 0ff4f74c (git cat-file -e), absent at b87ee32f.

-----------------------------------------------------------------------------------------------------
findings_and_residual_limitations
-----------------------------------------------------------------------------------------------------
ASR-1  BLOCKS_CURRENT_CANDIDATE (as delivered). Needs a corrective issue.
  The handover record on main states a false fact as a trap for later sessions. Its "Traps found this
  session" item (docs/SESSION_HANDOVER_2026-09-26_PLATFORM_PLAN.md lines 52-54) says
  `finance/period_grid_v14.py` "is **not** on `main`" and is "re-proposed with A2 in draft #1231", and
  that "Text that treats Sprint 20 A1 as landed is stale". #1231 merged before the squash (B2), so the
  sentence was false the moment #1296 landed. It is still false: the record is byte-identical on main
  and period_grid_v14.py is on main. AGENTS.md ("a durable record that is confidently wrong is worse
  than a thin one") and PERSIST-01 make this a correction that cannot wait. The same base movement
  makes dated statements in the executive summary (line 49, 57) and the analysis (lines 243, 374) read
  "draft #1231"; those are dated evaluation text and are not blocking, but the corrective change should
  date or annotate them.
  Cause: the base moved b87ee32f -> 0ff4f74c and no module 3 section 7 proofs were recorded. Proof 2
  (normative-reference isolation) fails, because a subject object makes a claim about an object the
  base movement created. The subject manifest gave no warning, because it does not pin the cited
  evidence objects (ASR-3). The disposition LAPSES at the delivery base whatever the frozen subject's
  merit.
  Gate: an amendment to the handover (and dating of the analysis and summary references) reviewed under
  RECRUIT-01 as R2, since it edits a PERSIST-01 record.

ASR-2  Non-blocking. Proposed TRACKED_IN_NAMED_ISSUE; no issue named yet, so the #1371 coordinator owns
  it until one exists. HOLD effect: none.
  Predecessor finding PF-4 recurs in latent form. The handling note says it "is the ONLY statement of
  how this object is handled" and that the two READMEs "cite the identifier above rather than restating
  it". In fact the publication decision and its authority are also written in the Sprint 21 README
  (line 15, "publication (D4: keep public)"), the executive summary (line 79), the analysis (line 437),
  the handover (lines 32-33) and the changelog fragment (lines 20-21). The executive summary (lines
  90-91) says outright that D1, D2, D4 and D5 were recorded "here, in the analysis, in the handover
  record and, for D4, in the handling note". Fidelity is restated in the changelog fragment (line 4)
  and the area README (lines 25-27), which also says the note is "deliberately not repeated here". All
  copies agree today; I checked each. N6 and N8 show the guard would not catch a copy that drifted or
  contradicted the note. That guard behaviour predates #1296, but #1296 relied on it while claiming more.
  Gate: either reduce the copies to citations of PLATFORM-PLAN-HANDLING-2026-09-26, or soften the
  "ONLY statement" sentence, and record whether the guard should detect restatement.

ASR-3  Non-blocking. ACCEPTED_RESIDUAL_WITHIN_SCOPE for this documentation-only item, because the
  candidate commit and tree pin every object. HOLD effect: none.
  The subject manifest pins 36 unchanged context objects but leaves out the 18 cited evidence objects in
  B1. That partial pinning reads as complete, and it is why ASR-1 passed the S6 check silently. Any
  later carry-forward under module 3 section 7 must treat cited evidence objects as files the reviewer
  judged.

ASR-4  Non-blocking. ACCEPTED_RESIDUAL_WITHIN_SCOPE: superseded for this review by R1-R8, which reproduce
  the sampled results at the candidate. HOLD effect: none.
  The writer's receipts are not bound to the frozen candidate. The implementation record names the
  #1296 PR body as its receipts, but no row there names 5dd220eb. Rows name 46a21a5 or 7458252 or no
  commit at all. The Grid Study row counts 10 paths, while the candidate has 12. The PR Notes still say
  "Publication decision (D4) belongs before merge" and that the handling note records "how to switch to
  the manifest-only route". The note at the candidate records D4 as decided and describes no switch.
  The implementation record also says the lint and docs suites "passed except five sandbox tests",
  where the cited row is "3 failed, 653 passed". This is the VERIFY-01 LIMIT case: the receipts gate
  cannot see stale rows.

ASR-5  Non-blocking for the frozen subject. Proposed TRACKED_IN_NAMED_ISSUE (owner's governance call);
  no issue named yet. HOLD effect: none.
  Contract boundary: the review gate that #1296 depended on was unwritten, and the canonical ruleset
  tells agents not to honour unwritten gates. The handover (open item 2) and the PR Notes say "Do not
  merge on green CI alone". MERGE-01 at the candidate says the opposite for a green PR: do not hold it
  for a per-PR go-ahead, and a mandatory independent review "belongs in the REQUIRED-CHECK set ... never
  an unwritten extra gate that a green pull request is silently held against". RECRUIT-01 does not
  change MERGE-01 ("Existing ... MERGE-01 gates remain unchanged"). So the merge on green without the
  review chain, on 2026-09-29, follows from the ruleset as written. PF-7 recurred at delivery. Until R2
  review is a required check, or MERGE-01 names an exception, the same thing can happen to any R2
  documentation PR.

Observations (no ledger state needed; offered only for the writer of any corrective change)
 O1  The DELIVERY-01 deviation (one PR spanning corpus, guard, planning record and handover) and the
     SPRINT_BOOTSTRAP_PROC_R1 deviations (branch name, line target, undefined five passes) are declared
     honestly with reasons.
 O2  The implementation record (3.3) puts reviewers "in an isolated git worktree" and also forbids any
     "worktree mutation". Creating that worktree falls to the coordinator; the record could say so.
 O3  The handover's Status line describes a pre-merge snapshot and defers to "review records bound to
     its head", none of which exist. A reader of main gets no signal that review never happened, except
     from the CHANGELOG line in D3.

Residual limitations of this review
 L1  Owner quotes and received-text fidelity are unverifiable from the objects (ingress).
 L2  The finance, resource and audit-register claims were not judged here (R-DOM-1 scope).
 L3  The analysis and executive summary were searched, not read end to end.
 L4  Exposure to the R-DOM-1 headline, disclosed above.

-----------------------------------------------------------------------------------------------------
predecessor_finding_matrix (implementation record section 4)
-----------------------------------------------------------------------------------------------------
 PF-1 stale pin / incomplete manifest / impossible entry | applicable | M1, N3, N4, N7; area has no nested
      manifest; no gitignored entry; every tracked file recorded                          | CLOSED
 PF-2 "manifest only" contradicted by quoted content     | applicable | full publication with recorded
      authority (L1); plan read in full (D1); restricted-term search (D2)                 | CLOSED
 PF-3 review record re-publishing removed material       | no review record in the subject              | NOT_APPLICABLE
 PF-4 one fact in several places; false receipts table   | applicable | ASR-2 (copies), ASR-4 (receipts)| RECURS (non-blocking)
 PF-5 invented framework expansions                      | applicable | D5, R1                          | CLOSED
 PF-6 acceptance asserted without a record               | applicable | D3: no acceptance asserted     | CLOSED
 PF-7 load-bearing work merged on green without review   | applicable to delivery | merged 2026-09-29 on green
      without the review chain; ASR-5                                                     | RECURS (at delivery)

-----------------------------------------------------------------------------------------------------
independent_oracles_or_counterexamples
-----------------------------------------------------------------------------------------------------
 N1-N8 (five positive controls that must fire and do; two hostile counterexamples that are not
 detected; one hostile counterexample that is detected), M2 byte-level invariant proof, R5 closed-form
 annuity, B1-B2 base-movement replay against #1231.

END OF RECORD
```

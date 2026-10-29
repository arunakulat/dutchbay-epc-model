# #1296 post-merge review — reconciliation record

| Field | Value |
|---|---|
| Work item | #1371 (post-merge `RECRUIT-01` review of #1296), tracker #1353 |
| Subject | Frozen candidate `5dd220eb4011188924dccd3aa26659c646c9f306`, tree `780ee2bf87f9d21edfdc217a111325cf3f62daa9`, base `b87ee32f8031a9b81b222c90020ed10af2c18131`; subject manifest `docs/PLATFORM_PLAN_SUBJECT_MANIFEST.tsv`, SHA-256 `bb601ad3f4ecf77711596a57d6c383a410163fa84d68adff47f58834ea189fc8` |
| Delivery | Squash `e35ea9f26c8094be4d18a4cf5475d35f25932d4f`, 29 September 2026 |
| Written | 28 October 2026, by the writer of #1484, which also carries the corrections. This record is a writer's reconciliation, not a review |
| Authority | None. It confers no grade, release, audit, lender, Board, publication, issue-closure or `HOLD` authority, and it changes no reviewer's disposition or ledger state. The #1110 `HOLD` is untouched |

The implementation record (section 3.3) and the domain record both name this file. Until now it
did not exist. It covers what #1371 asks of it: the `NO_EVIDENCE` attempt, the uncoordinated
merge and the findings ledger. It also records the independence of each lane and how the two
records were persisted.

## 1. History

| Date (UTC) | Event | Source |
|---|---|---|
| 26 September 2026 | The first review dispatch was stopped by an account usage limit before either reviewer returned. Under module 4 section 6 that attempt is `NO_EVIDENCE` | #1371 body; domain record, PF-7 |
| 27 September 2026, 05:06 | #1231 merged as `d3157e0d`, adding `finance/period_grid_v14.py` and `finance/subannual_rows_v14.py` to `main` | `git log` |
| 29 September 2026, 01:00 and 01:42 | #1290 merged as `0ff4f74c`. #1296's head then took in `main`, and it merged as squash `e35ea9f2` on green CI without its review pair. The base moved from `b87ee32f` to `0ff4f74c`, and no module 3 section 7 proofs were recorded | `git log`; assurance record, B2 |
| 6 October 2026 | The merge coordinator's handover lists #1296 as "Not coordinated by this session" | `docs/SESSION_HANDOVER_2026-10-06_MERGE_COORDINATION.md` line 37 |
| 21 October 2026 | The owner directed "yes, open the tracker and run the reviews", and #1371 was opened | #1371 body |
| 22 October 2026 | R-DOM-1 (wave 1) returned REJECT. Its record was committed as `b8cc7d55` on a branch that never merged | Domain record |
| 28 October 2026 | The domain record was preserved on #1371. Corrective issues #1477 to #1483 were opened | #1371 issuecomment-6459238264 |
| 28 October 2026 | The first R-ASR-1 lane stood down before reviewing (section 3) | Stand-down note, held in the project's review-records folder |
| 28 October 2026 | A second R-ASR-1 lane returned REJECT | #1371 issuecomment-6460171871 |

The merge without review is predecessor finding PF-7. Both records find that it recurred. The
assurance record traces it to a contract boundary (ASR-5): the "Do not merge on green CI alone"
gate was unwritten, and `MERGE-01` tells agents not to honour unwritten gates.

## 2. Records

| Record | Repository copy | Digest of the record | Disposition |
|---|---|---|---|
| R-DOM-1, task-domain, wave 1 | `docs/PLATFORM_PLAN_DOMAIN_REVIEW_001.md` | File as preserved: `7ccdaee3d08253783b30e6980f1e0ac28ffa7339df44799302848aef744d9303`. Reviewer's message inside it: `4a38fb4a58db0f70361f9fa5c947b03942ff643f9ef6b6b231618920a3a2ea61` | REJECT |
| R-ASR-1, assurance | `docs/PLATFORM_PLAN_ASSURANCE_REVIEW_001.md` | Fenced record: `fddbff768f550875dcdd656df342cfde2ada9b093076893e851d851c50143ee0` | REJECT |

Both records are bound to the frozen subject manifest above. Both attest that the delivered
bytes in `e35ea9f2` equal the candidate's for all 12 changed paths. Both name the two later
changes on `main`: #1312 folded the changelog fragment into `CHANGELOG.md`, and #1313 changed one
hunk pair in the guard.

How each copy differs from what the reviewer handed back:

- **Domain record.** It keeps the coordinator's 22 October header and adds a dated note under the
  title. One token, the model identifier on the `reviewer_identity` line, is withheld because the
  repository carries no model identifiers. The note gives the digest of the unedited file. The
  unedited copy is on #1371 in issuecomment-6459238264, and that comment will not be edited.
- **Assurance record.** A header precedes it, and the record sits unchanged inside a `text`
  fence. The fenced lines, each with its line feed, hash to the digest above.

## 3. Independence

#1371 requires that the two reviews run one after the other, and that neither sees the other's
disposition. They ran in that order. Each record discloses the limits on its independence, and
they are restated here so a reader does not have to find them:

- **R-DOM-1.** It ran as a subagent inside Claude Code session
  `session_01Xmv5MBtYeqKTJvsJXphk6F`. That is the same session ID the implementation record names
  as #1296's writer and coordinator. The record says the subagent started cold without the
  writer's context, and it ran in its own worktree.
- **First R-ASR-1 lane.** It stood down before any check ran. A call to read #1371's comments
  returned the whole domain record, because that record is #1371's first comment, and the lane
  read it. It gave no disposition and posted nothing on #1371. Its note is held outside the
  repository. Its advice to any later lane was to read #1371 only with the issue `get` method.
- **R-ASR-1.** The lane ran in session `session_0159RRMb3ibRLm7H1vJ5x3L1`. Before it began, two
  things showed it the domain record's headline: its project memory recall, and the owner's
  message in its brief. The headline gave the disposition, the finding IDs and the record's
  digest. It saw no finding's text, subject or reasoning. It did not read #1371's comments, the
  domain record or #1477 to #1483. The record says every finding comes from a check it records,
  and it asks the reader to weigh the exposure.

Neither reviewer is the writer of #1296 or of #1484, although R-DOM-1 shared the #1296 writer's
session ID. The writer of #1484 read both records after they were
delivered. #1484's own review pair must be lanes other than these.

## 4. Findings ledger

Ledger states are the reviewers' own, from module 3 section 5. Issue numbers are the corrective
or tracking issues.

| Finding | Severity | Ledger state | Issue | Where it is addressed |
|---|---|---|---|---|
| DOM-1: debt sizing attributed to the inert closed-form helper | high | `BLOCKS_CURRENT_CANDIDATE` | #1477 | #1484: analysis section 13 |
| DOM-2: audit-overlap map incomplete | high | `BLOCKS_CURRENT_CANDIDATE` | #1478 | #1484: analysis section 7.1; roadmap P0.2 |
| DOM-3: C1 misquotes the plan and lacks a qualifier | low | `BLOCKS_CURRENT_CANDIDATE` | #1479 | #1484: analysis C1 |
| DOM-4: item 30 omits the existing reserve sweep | medium | `BLOCKS_CURRENT_CANDIDATE` | #1480 | #1484: analysis item 30, B4 |
| DOM-5: B3 classed `R2` | low | `BLOCKS_CURRENT_CANDIDATE` | #1481 | #1484: B3 classed `R3` |
| DOM-6: executive summary inconsistencies | low | `BLOCKS_CURRENT_CANDIDATE` | #1482 | #1484: executive summary |
| DOM-7: statements false on `main` from the merge | medium | `BLOCKS_CURRENT_CANDIDATE` | #1483 | #1484: handover trap withdrawn; analysis, summary and research notes dated |
| DOM-8: C4 implies the 30% ratio is unique to ATAD | low | `ACCEPTED_RESIDUAL_WITHIN_SCOPE` | #1371 | #1484: C4 reworded |
| DOM-9: imprecise citations | low | `ACCEPTED_RESIDUAL_WITHIN_SCOPE` | #1371 | #1484: items 7 and 26, section 5.7 |
| ASR-1: the handover's period-grid trap is false on `main` | — | `BLOCKS_CURRENT_CANDIDATE` (as delivered) | #1483 | #1484: as DOM-7 |
| ASR-2: the handling note claims to be the only statement, but five files restate it | — | `TRACKED_IN_NAMED_ISSUE` (proposed) | #1485 | Not in #1484 |
| ASR-3: the subject manifest leaves out 18 cited evidence objects | — | `ACCEPTED_RESIDUAL_WITHIN_SCOPE` | #1371 | Not in #1484 |
| ASR-4: the writer's receipts are not bound to the candidate | — | `ACCEPTED_RESIDUAL_WITHIN_SCOPE` | #1371 | Superseded by the assurance record's own re-runs |
| ASR-5: the review gate was unwritten, and `MERGE-01` forbids unwritten gates | — | `TRACKED_IN_NAMED_ISSUE` (proposed) | #1486 | Owner's governance call |

The assurance record gives no severity grades. Its blocking finding is ASR-1.

**Where the records overlap.**

- **ASR-1 and DOM-7** describe the same false sentence, found by different checks. The domain
  lane re-read the statement against `main`. The assurance lane replayed the base movement. One
  correction under #1483 answers both. ASR-1 also asks for the "draft #1231" references in the
  analysis and the executive summary to be dated; #1484 does that.
- **PF-4.** The domain record closed PF-4 for the handling statement and the sampled receipts,
  and recorded a separate disagreement about the decision set as DOM-6. The assurance record
  finds PF-4 recurring in two other places: copies of the handling statement (ASR-2) and stale
  receipts (ASR-4). The records looked at different objects, so they do not conflict.
- **PF-7.** Both records find that it recurred. Only the assurance record turns it into a
  finding (ASR-5).

**Observations.** The assurance record's observations O1 to O3 take no ledger state. #1484's
update note on the handover's open item 2 gives a reader of `main` the signal that O3 found
missing: that #1296 merged without review.

## 5. Deviations from the #1371 plan

- #1371 planned one documentation-only pull request for the records, and said that item would not
  edit the reviewed documents. Instead, the records travel in #1484 with the corrections for
  #1477 to #1483, at the coordinator's direction and after the owner asked for issues and then a
  pull request. #1484's reviewers judge both parts.
- The domain record's repository copy withholds one token (section 2).
- #1371's "Done when" asks for every blocking finding to link a corrective issue. Each does:
  DOM-1 to DOM-7 link #1477 to #1483, and ASR-1 links #1483. #1371 stays open until the owner
  decides it is done.

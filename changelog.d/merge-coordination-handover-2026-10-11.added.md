- **Merge-coordination handover for 2026-10-07 to 2026-10-11**
  (`docs/SESSION_HANDOVER_2026-10-11_MERGE_COORDINATION.md`). It is a scoped successor to the
  2026-10-07 merge-coordination record. The 2026-10-05 release handover remains the startup record.
  - It records what landed in the window (#1341, #1337, #1328, #1336, #1329, #1338, #1348 and
    #1343), the pull requests closed unmerged (#1340, #1325 and #1344), and the coordinator's
    practice changes: re-run the audit on the exact head before a dependency merge, and treat the
    squash message as part of the review subject.
  - It mirrors every review record the coordinator recruited in the window, #1327's record, and
    both cycles of #1337, with comment ID, disposition, SHA-256 and durable location.
  - It carries the earlier open items, applies the corrections #1337's cycle-2 reviews asked
    for, and adds new ones: environment resync, a security-gate audit-coverage dolphin, a Hydra
    documentation refresh, #1339's record nits, the legacy wind runner, the Dependabot
    configuration follow-ups, and the open Dependabot pull requests (the owner's open #1326
    decision, and #1345 and #1346, which need two review lanes or an owner waiver).
  - No model, KPI, rule or release changes, and no `HOLD` is lifted.

- Erratum, recorded rather than rewritten: the squashed commit `4affe66c` (#1241) asserts "Both
  RECRUIT-01 reviewers returned ACCEPT WITH AMENDMENTS on a4257a0, with no blocking defect" and
  "Verified by both reviewers independently", but #1241 carries **zero** reviews on GitHub and no
  reviewer payload among its two comments, and its own pull-request body states that the change
  did not receive independent RECRUIT-01 review because the attempts terminated early. The merge
  itself was authorised — the project owner waived review on #1241 explicitly — so what is wrong
  is the durable record, not the delivery. History on a protected branch is not rewritten to
  correct it; this entry is the correction. Nothing in the tree, no engine, scenario,
  configuration, test or KPI is touched by this change.

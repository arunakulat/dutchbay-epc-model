- Added the #1429 project-input defaults inventory of 28 October 2026 under
  `docs/analysis/issue_1429_inputs_2026-10-28/`: a README, a 241-row migration register in
  49 groups, and a source manifest that pins every inspected file at base `c283565a`. It
  is a dated snapshot and a proposal register, not a migration. No production, scenario or
  KPI byte changes. Groups D01 (gearing), D06 (DSCR target) and D07 (downside factor) are
  the scope of draft #1733. Group N01 (the default project discount rate) was resolved
  after the snapshot by #1524, which removed the constant, so N05's fallback now reaches
  the declared project discount rate; the other groups remain open proposals. The
  README's line numbers are from that base, and its local evidence ledgers live on the
  owner's Mac.

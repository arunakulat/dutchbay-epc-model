- **The Sprint 21 evaluation of the owner's platform plan is corrected after its domain review.**
  #1296 merged `docs/SPRINT_21_BOOTSTRAP/` without its review pair; the post-merge domain review
  (#1371) returned REJECT with seven blocking findings, each now an issue (#1477 to #1483). Four
  statements in the #1296 entry of `CHANGELOG.md` are corrected here. The
  repository sizes debt by solving gearing on the real schedule, in an opt-in mode that 19 of 37
  top-level scenarios use; `size_debt_with_dual_dscr`, against which the debt-capacity check was
  run, only fills lender-pack metadata. The plan bases debt capacity "on the NPV of CFADS"
  without saying how, so only its literal reading sizes at 1.00x coverage and oversizes a
  sculpted facility by the target DSCR factor. At least 19 of the 38 plan items touch open
  hold-blocking audit findings, not 11; the analysis's audit map is now marked non-exhaustive and
  lists the rest in its section 7.1. The corrected counts are 16 items implemented, 10 partly, 11
  gaps and 1 premise that does not apply. The analysis also now records the existing 6-month
  reserve sweep in the equity waterfall, classes dolphin B3 as `R3`, makes the executive summary
  agree with the recorded decisions, and withdraws the 26 September handover's trap about
  `finance/period_grid_v14.py`, which has been on `main` since #1296 itself merged. The roadmap's
  P0.2 citation of the audit map is qualified. Documentation only: no runtime, financial formula,
  scenario, model input or KPI change. The post-merge assurance review of #1296 also returned
  REJECT; its one blocking finding is the same handover trap. Both review records and a
  reconciliation record are now under `docs/PLATFORM_PLAN_*`.

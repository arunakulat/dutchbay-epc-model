- Stop `.github/SPRINT_WORKFLOW_CHECKLIST.md` defining CASPER, CESSPIT and CCCDIR in terms the
  canonical ruleset does not contain. Its "CCCDIR Framework Checklist" filed the three as a
  five-part `C1`-`C5` structure with CASPER at `C2` and CESSPIT at `C3`, inverting the sibling
  relationship: `go_with_the_flow_rules_v3_0_clean.csv` carries them as three peer rows,
  `FRAMEWORK-01`, `FRAMEWORK-02` and `FRAMEWORK-03`, in category "Framework Principles". The
  expansions were wrong too -- CASPER as "Clean Architecture" against the CSV's "Clear API
  Surfaces with Predictable Error Responses", CESSPIT as "Core-Easy-Simple" against "Config
  Explicit, Schema Strict, Pre-flight Integrity Tests" -- and `C4` "LIBsct" and `C5` "CDIR" appear
  nowhere in the ruleset at all. An audit run off this file checks properties that do not exist and
  reports a clean result against them, which is what happened during the PR #1274 review. The
  section now summarises the three `FRAMEWORK-0x` rows by rule id and says to read the CSV for the
  full statement; the PR-template, pre-merge and scorecard blocks that echoed `C1`-`C5` follow it.
- Stop the same file contradicting `FRAMEWORK-02` on fallbacks. Its `ARCH-01` block asked for
  "Fallback logic defined if config sections missing" and its `VAL-01` block for "Fallback behavior
  documented for `strict=False`", where the CSV's CESSPIT row requires no silent defaults or
  fallbacks for FX, tax or debt terms and no `strict=False` bypass in production code. Both lines
  now state the rule the CSV actually carries.
- Declare the file derived. It now names `go_with_the_flow_rules_v3_0_clean.csv` as canonical and
  says the CSV wins where the two disagree, matching how `AGENTS.md` describes itself as "a concise
  Codex gateway, not a replacement copy". Note for a follow-up: `FRAMEWORK-01`'s enforcement cell
  in the CSV cites `analytics/gis/netcdf_utils.py` as its guard example, and no such file exists in
  the tree, so this checklist cites `analytics/sensitivity/global_sa.py::_require_salib` instead.
  Documentation only -- no code, config or KPI is touched.

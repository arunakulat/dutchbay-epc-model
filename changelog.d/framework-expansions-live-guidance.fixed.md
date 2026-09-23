- Re-file the framework-compliance sections of five live-guidance files onto the rules the
  canonical ruleset actually defines. `go_with_the_flow_rules_v3_0_clean.csv` carries CASPER,
  CESSPIT and CCCDIR as three peer rows -- `FRAMEWORK-01`, `FRAMEWORK-02`, `FRAMEWORK-03` -- and
  every one of these files restated them differently. `analytics/contracts/README.md` and
  `finance/FINANCE_REORGANIZATION.md` carried the same invented triple verbatim: CESSPIT as
  "Comprehensive Error Handling", CASPER as "Contract-First Design", CCCDIR as "Clear, Complete,
  Consistent Documentation". `docs/policy/discount_rate_policy.md` gave CCCDIR as "Configuration in
  Config DIRectory"; `docs/FX_FLAG_TRACKING_GUIDELINES.md` gave CESSPIT as "Evidence-based tracking
  (not config-based)", which inverts a rule whose whole content is that config is explicit; and
  `docs/DEBT_NAMING_CONVENTIONS_v14.md` gave CCCDIR as "Comprehensive documentation standards".
- The contracts README is the sharpest case, because it is the package README for `contracts_v14`,
  the module `FRAMEWORK-03` governs, so it sits exactly where a reader verifying CCCDIR compliance
  looks. Its bullets were accurate; they were filed under the wrong rules. They are re-filed rather
  than rewritten: Pydantic validation and error messages under `FRAMEWORK-01`, schema strictness
  and frozen models under `FRAMEWORK-02`, and the single canonical definition plus the import
  guards under `FRAMEWORK-03`. `finance/FINANCE_REORGANIZATION.md` gets the same treatment.
- Correct one claim about the import guards while re-filing it. An earlier draft of this change
  said a LibCST test bans every import from `analytics.evaluation_v14` except
  `evaluate_with_overrides()`. It does not: `tests/lint/test_contracts_gateway_imports.py` fails a
  module-level import of a PRIVATE, underscore-prefixed name from that module, and the module
  boundary itself is guarded separately by `tests/lint/test_no_direct_finance_pipeline_imports.py`.
  The README now names both guards and says what each one checks.
- Thirteen further tracked files carry divergent expansions inside dated audits, retrospectives and
  sprint completion records -- `docs/AUDIT_CASHFLOW_V14_FINAL.md`,
  `docs/SPRINT_16_REORGANIZATION_COMPLETE.md`, `docs/archive/` and `legacy/sprint_snapshots/` among
  them. Those are receipts of what was believed on a date and are deliberately left as written;
  correcting them would falsify the record. Documentation only -- no code, config or KPI is touched.

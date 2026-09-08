# F2/F3 DSCR unification recovery record

Status: implementation checkpoint for fresh independent review; no acceptance or merge claimed.

## Identity, authority and recovery

Coordinator/sole writer: task `01a07e1b-a139-79e0-94fc-4a8d48c37b72`, worktree
`/Users/aruna/.codex/worktrees/c971/dutchbay-epc-model`, branch
`codex/f2f3-dscr-recovery`, base `61c5956d0ec23d03b1ac472abf735d6172ef4dbd`.
Risk: `R3_CONSEQUENTIAL`; separate domain and assurance review required.
Authoring/review task setting: GPT-6 Astra Extra High (`gpt-6-astra`, `xhigh`).

Owner direction:

"Do not wait for approval. work autonomously. Take your best, considered and safe decision. Use the Recruit-01 and verify-01 rules to reconsider and confirm your decisions. Start all new worktrees ingressing the rulesets - GWTF, CESSPIT, CASPER and CCCDIR. Follow these rules rigorously. Copy this instruction to all new tasks, worktrees, PR's"

The source worktree `agent-a3dabbfe309764689` remains untouched at
`8935103594760af103ec3032948dbf136aa040b9` with twelve local commits and its original dirty
implementation record. Historical owner revocation was read from `LOCAL_OWNER_ACKS.json`.
No matching active source writer process was found. A full-history bundle verifies;
1,486 tracked-file hashes were identical before and after preservation. Dirty bytes,
patches, full commit history and manifests reside under
`/Users/aruna/Downloads/DutchBay_Oldest_First_Programme_2026-09-07/f2f3/original`.
The original dirty record's anticipated thirteenth commit never existed at recovery;
its green-test and held-base statements remain historical receipts, not acceptance.

Full canonical GWTF (74 active rules), framework definitions, four RECRUIT modules,
AGENTS, September 7 handover/bootstrap, complete F6/F2F3 charter including sections
10–14, F6 implementation and both complete review/rebind records were ingressed.
F6 PR #1223 is merged as `e90cfc2`; A1 revert #1232 is merged as `4082ac5` and is
an ancestor of this base. `finance/period_grid_v14.py` and A2 code are absent.
The programme profile expressly authorizes reconstruction on current main with fresh
review, superseding the charter's temporary contested-A1 base hold.

## Behavior and compatibility

`plan_debt.dscr_series` now spans every debt period, including undefined `None`
sentinels. New `dscr_periods` records the period ratio, operating year, row index and
per-year folded `covenant_dscr`. Labels follow the published row-period map.
Mapped rows after debt tenor retain their operating-year labels with undefined DSCR;
only genuinely unmapped construction, bridge and padding periods have no year.

Headline `min_dscr` retains `min(operating-period minimum, dscr_by_year minimum)`.
The gearing solve and fee/tax basis remain unchanged. `ScenarioResult.dscr_series`
retains its compact finite-float contract. `raw_dscr_series` remains a plain-list
value alias; its warning accessor and retention limits are in `DEPRECATIONS.md`.
The facade keeps the labelled series opaque; no report route is added.

Covenant breach counts/dates use the operating-year label and folded coverage.
The CEB capacity-charge case changes from REVIEW to FAIL (three breaches including
year one); the solar/nightpeak case has two breaches beginning in year one.
These are intentional covenant-reporting changes, even though headline KPIs match.
Missing, malformed, duplicate or invalid published labels fail loudly. An explicitly
invalid input-row year cannot be replaced with an ordinal. The existing timeline
builder's explicit ordinal for an omitted input-row year is preserved.

Version 15.5.0 and CHANGELOG disclose the public contract and covenant change under
DOC-02. This is a model-version update, not a release/tag or canon rebaseline.
Version/hash pins in the pure D3C identity leaf and synthetic-grid source snapshot
must change with VERSION; their guards remain intact. D3B test fixture version values
and their exact assertions move together. Derived D3B success and synthetic manifest
checksum pins also change; their existing independent-oracle and corruption guards
remain intact. Grid math and frozen payload hashes do not
change. The GitHub Grid Study will be required by the touched source surface.

## Fresh evidence and limitations

Evidence directory: programme `f2f3`. `scenario_comparison.json` compares separate
real base and candidate worktrees in the one governed Python 3.12.13 environment,
with each active checkout first on PYTHONPATH. All 37 current scenario files were
attempted: 29 evaluated, eight failed identically. Every KPI key/value matched at
full repr precision across all 29 (37–40 KPI keys depending on scenario). Every old
debt-result value except the intentionally positional `dscr_series` matched, and
old key order remains the prefix with only `dscr_periods` appended. Compact
ScenarioResult series and headline minima match exactly.

Both CEB fold-dominated headlines are preserved: `0.9069456485322224` and
`0.8724193845452927`. No canon constant changes. The pre-existing canon and driver
responsiveness tests are included in the focused 412-pass run.

Checks at the implementation checkpoint:

- Recovered-byte control: 395 focused tests passed.
- Strict-label revision: 412 focused tests passed in 24.86 seconds.
- `mypy analytics finance`: no issues in 185 source files.
- Seven in-memory hostile mutations in the real c971 worktree: all killed;
  unmutated controls passed 279 tests before and after. Source hashes stayed fixed.
  Mutants restore offset years, include the bridge, discard the fold, recompact,
  ignore folded covenant coverage, diverge the alias, and invent invalid years.
- Pre-commit on the initial changed paths passed. Final checkpoint hooks must rerun.
- Full suite before identity-pin synchronization: 30 failed, 7,364 passed,
  18 skipped, 333 errors. D3C identity and synthetic-grid VERSION pins caused
  reproduced failures after the version bump; pin synchronization answers them.
  SSH readiness failed on a sandbox-denied loopback bind and passed outside the sandbox (1 passed). This failed full run is retained as failed.
- Version-pin follow-up: 1,585 contract/grid tests passed; three failures identified
  the two derived checksum pins. Those pins are synchronized with source identities.
- Full post-fix suite, final independent dispositions, final-head CI and merge
  verification are pending at writing. No historical run substitutes for them.

The native test stack created a 51-byte `:memory:.ses` transient session file.
It was hash-recorded and preserved in the evidence directory before named removal.
Coordinator continuity revocation was honored; dirty hashes and failed-run facts
were checkpointed, then a fresh bounded identity-dependency lease was issued.

## Predecessor findings and dispositions

| Finding | Current disposition and evidence |
|---|---|
| F6 assurance: helper-only no-bridge test | Public `plan_debt([])` tests retained and extended at construction counts 0 and 3; independent reviewers must replay. |
| F6 assurance: ordering only claimed | Exact published key-order assertion retained and extended; all-scenario comparison verifies prefix identity. |
| F6 domain: first operating boundary not derivable | Historical claim rejected; boundary derives from the public map. |
| F6 domain: facade reason covers two keys | Corrected in the already-touched facade; no period-indexed series is routed. |
| F6 domain: route first operating index later | Deferred to a separately chartered D3C series-routing change, owned by the contract coordinator; current opaque disposition is consistent with no series route and lifts no HOLD. |
| F2/F3 fold hazard | Both CEB headlines exact-equal; discard-fold mutant killed by 14 tests. |
| Archive false-positive controls | All current evaluation, contract and mutation work uses real Git worktrees; controls pass before/after. |
| Old-shape tests weakened during migration | Exact ordering/set assertions retained; headline test now asserts both terms; independent assurance must inspect complete diff. |
| Invalid labels silently normalized | Fixed with explicit error and public-boundary hostile tests. |
| Source record claimed DOC-02 exemption | Superseded: covenant behavior is consequential; version and impact documentation updated. |
| Raw alias consumers | Retained for compatibility; separate finance-maintenance migration required before removal, with no present HOLD effect. |

F1, A1, A2, fee/tax changes, canon rebaseline, broad audit and shared-ledger writes
are excluded. F5-02 and #1110 evidence/professional/release/Board/lender HOLDs remain.
Engineering tests, review and merge confer no additional authority.

## Unevaluable current files

- `bad_missing_tax.yaml`: PipelineValidationError — Pipeline execution failed: Config '<inline>' is missing or has invalid required fields: corporate_tax_rate (paths: tax.corporate_tax_rate_pct, tax.corporate_tax_rate, project.corporate_tax_rate_pct, project.corporate_tax_rate, parameters.corporate_tax_rate_pct, parameters.corporate_tax_rate, corporate_tax_rate_pct, corporate_tax_rate)
- `contracts_edgecase_base_v14.yaml`: PipelineValidationError — Pipeline execution failed: Config '<inline>' is missing or has invalid required fields: capacity_factor (paths: project.capacity_factor_pct, project.capacity_factor, parameters.capacity_factor_pct, parameters.capacity_factor, capacity_factor_pct, capacity_factor); opex_usd_per_year (paths: opex.usd_per_year, opex.usd_annual, opex.annual_opex_usd, costs.opex_usd_per_year, parameters.opex_usd_per_year, opex_usd_per_year); tariff_lkr_per_kwh (paths: tariff.lkr_per_kwh, tariff.lkr_kwh, tariff.tariff_lkr_per_kwh, revenue.tariff_lkr_per_kwh, parameters.tariff_lkr_per_kwh, parameters.tariff_lkr, tariff_lkr_per_kwh, tariff_lkr, tariff)
- `dscr_sensitivity_example.yaml`: PipelineValidationError — Pipeline execution failed: Config '<inline>' is missing or has invalid required fields: Missing `fx` section. Expected mapping with keys: `start_lkr_per_usd`, `annual_depr`.; capacity_factor (paths: project.capacity_factor_pct, project.capacity_factor, parameters.capacity_factor_pct, parameters.capacity_factor, capacity_factor_pct, capacity_factor); corporate_tax_rate (paths: tax.corporate_tax_rate_pct, tax.corporate_tax_rate, project.corporate_tax_rate_pct, project.corporate_tax_rate, parameters.corporate_tax_rate_pct, parameters.corporate_tax_rate, corporate_tax_rate_pct, corporate_tax_rate); epc_usd_total (paths: capex.usd_total, capex.epc_usd, capex.capex_total_usd, capex.total_capex_usd, capex.total_capex, finance.capex_total_usd, finance.capex_usd, costs.capex_total_usd, costs.capex_usd, costs.total_capex_usd, costs.total_capex); fx_start_lkr_per_usd (paths: fx.start_lkr_per_usd); opex_usd_per_year (paths: opex.usd_per_year, opex.usd_annual, opex.annual_opex_usd, costs.opex_usd_per_year, parameters.opex_usd_per_year, opex_usd_per_year); tariff_lkr_per_kwh (paths: tariff.lkr_per_kwh, tariff.lkr_kwh, tariff.tariff_lkr_per_kwh, revenue.tariff_lkr_per_kwh, parameters.tariff_lkr_per_kwh, parameters.tariff_lkr, tariff_lkr_per_kwh, tariff_lkr, tariff)
- `dutchbay_mc_enhanced_2025Q4.yaml`: PipelineValidationError — Pipeline execution failed: Config '<inline>' is missing or has invalid required fields: Missing `fx` section. Expected mapping with keys: `start_lkr_per_usd`, `annual_depr`.; capacity_factor (paths: project.capacity_factor_pct, project.capacity_factor, parameters.capacity_factor_pct, parameters.capacity_factor, capacity_factor_pct, capacity_factor); corporate_tax_rate (paths: tax.corporate_tax_rate_pct, tax.corporate_tax_rate, project.corporate_tax_rate_pct, project.corporate_tax_rate, parameters.corporate_tax_rate_pct, parameters.corporate_tax_rate, corporate_tax_rate_pct, corporate_tax_rate); epc_usd_total (paths: capex.usd_total, capex.epc_usd, capex.capex_total_usd, capex.total_capex_usd, capex.total_capex, finance.capex_total_usd, finance.capex_usd, costs.capex_total_usd, costs.capex_usd, costs.total_capex_usd, costs.total_capex); fx_start_lkr_per_usd (paths: fx.start_lkr_per_usd); opex_usd_per_year (paths: opex.usd_per_year, opex.usd_annual, opex.annual_opex_usd, costs.opex_usd_per_year, parameters.opex_usd_per_year, opex_usd_per_year); tariff_lkr_per_kwh (paths: tariff.lkr_per_kwh, tariff.lkr_kwh, tariff.tariff_lkr_per_kwh, revenue.tariff_lkr_per_kwh, parameters.tariff_lkr_per_kwh, parameters.tariff_lkr, tariff_lkr_per_kwh, tariff_lkr, tariff)
- `dutchbay_sprint17_enhanced.yaml`: PipelineValidationError — Pipeline execution failed: Config '<inline>' is missing or has invalid required fields: Missing `fx` section. Expected mapping with keys: `start_lkr_per_usd`, `annual_depr`.; capacity_factor (paths: project.capacity_factor_pct, project.capacity_factor, parameters.capacity_factor_pct, parameters.capacity_factor, capacity_factor_pct, capacity_factor); capacity_mw (paths: project.capacity_mw, project.capacity, parameters.capacity_mw, parameters.capacity); corporate_tax_rate (paths: tax.corporate_tax_rate_pct, tax.corporate_tax_rate, project.corporate_tax_rate_pct, project.corporate_tax_rate, parameters.corporate_tax_rate_pct, parameters.corporate_tax_rate, corporate_tax_rate_pct, corporate_tax_rate); fx_start_lkr_per_usd (paths: fx.start_lkr_per_usd); opex_usd_per_year (paths: opex.usd_per_year, opex.usd_annual, opex.annual_opex_usd, costs.opex_usd_per_year, parameters.opex_usd_per_year, opex_usd_per_year); project_life_years (paths: project.project_life_years, project.life_years, parameters.project_life_years, Financing_Terms.tenor_years); tariff_lkr_per_kwh (paths: tariff.lkr_per_kwh, tariff.lkr_kwh, tariff.tariff_lkr_per_kwh, revenue.tariff_lkr_per_kwh, parameters.tariff_lkr_per_kwh, parameters.tariff_lkr, tariff_lkr_per_kwh, tariff_lkr, tariff)
- `example_fx_structured_blocks.yaml`: ComposerError — expected a single document in the stream
  in "<CHECKOUT>/scenarios/example_fx_structured_blocks.yaml", line 14, column 1
but found another document
  in "<CHECKOUT>/scenarios/example_fx_structured_blocks.yaml", line 114, column 1
- `kolonnawa_epc_100mw.yaml`: PipelineValidationError — Pipeline execution failed: Config '<inline>' is missing or has invalid required fields: Missing `fx` section. Expected mapping with keys: `start_lkr_per_usd`, `annual_depr`.; capacity_factor (paths: project.capacity_factor_pct, project.capacity_factor, parameters.capacity_factor_pct, parameters.capacity_factor, capacity_factor_pct, capacity_factor); capacity_mw (paths: project.capacity_mw, project.capacity, parameters.capacity_mw, parameters.capacity); corporate_tax_rate (paths: tax.corporate_tax_rate_pct, tax.corporate_tax_rate, project.corporate_tax_rate_pct, project.corporate_tax_rate, parameters.corporate_tax_rate_pct, parameters.corporate_tax_rate, corporate_tax_rate_pct, corporate_tax_rate); epc_usd_total (paths: capex.usd_total, capex.epc_usd, capex.capex_total_usd, capex.total_capex_usd, capex.total_capex, finance.capex_total_usd, finance.capex_usd, costs.capex_total_usd, costs.capex_usd, costs.total_capex_usd, costs.total_capex); fx_start_lkr_per_usd (paths: fx.start_lkr_per_usd); opex_usd_per_year (paths: opex.usd_per_year, opex.usd_annual, opex.annual_opex_usd, costs.opex_usd_per_year, parameters.opex_usd_per_year, opex_usd_per_year); project_life_years (paths: project.project_life_years, project.life_years, parameters.project_life_years, Financing_Terms.tenor_years); tariff_lkr_per_kwh (paths: tariff.lkr_per_kwh, tariff.lkr_kwh, tariff.tariff_lkr_per_kwh, revenue.tariff_lkr_per_kwh, parameters.tariff_lkr_per_kwh, parameters.tariff_lkr, tariff_lkr_per_kwh, tariff_lkr, tariff)
- `sensitivity_parameters_examples.yaml`: PipelineValidationError — Pipeline execution failed: Config '<inline>' is missing or has invalid required fields: Missing `fx` section. Expected mapping with keys: `start_lkr_per_usd`, `annual_depr`.; capacity_factor (paths: project.capacity_factor_pct, project.capacity_factor, parameters.capacity_factor_pct, parameters.capacity_factor, capacity_factor_pct, capacity_factor); capacity_mw (paths: project.capacity_mw, project.capacity, parameters.capacity_mw, parameters.capacity); corporate_tax_rate (paths: tax.corporate_tax_rate_pct, tax.corporate_tax_rate, project.corporate_tax_rate_pct, project.corporate_tax_rate, parameters.corporate_tax_rate_pct, parameters.corporate_tax_rate, corporate_tax_rate_pct, corporate_tax_rate); epc_usd_total (paths: capex.usd_total, capex.epc_usd, capex.capex_total_usd, capex.total_capex_usd, capex.total_capex, finance.capex_total_usd, finance.capex_usd, costs.capex_total_usd, costs.capex_usd, costs.total_capex_usd, costs.total_capex); fx_start_lkr_per_usd (paths: fx.start_lkr_per_usd); opex_usd_per_year (paths: opex.usd_per_year, opex.usd_annual, opex.annual_opex_usd, costs.opex_usd_per_year, parameters.opex_usd_per_year, opex_usd_per_year); project_life_years (paths: project.project_life_years, project.life_years, parameters.project_life_years, Financing_Terms.tenor_years); tariff_lkr_per_kwh (paths: tariff.lkr_per_kwh, tariff.lkr_kwh, tariff.tariff_lkr_per_kwh, revenue.tariff_lkr_per_kwh, parameters.tariff_lkr_per_kwh, parameters.tariff_lkr, tariff_lkr_per_kwh, tariff_lkr, tariff)

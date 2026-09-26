# Sprint 21 bootstrap — research notes

These notes record the evidence behind
[`SPRINT_21_COMPREHENSIVE_ANALYSIS.md`](SPRINT_21_COMPREHENSIVE_ANALYSIS.md): the commands run
against the repository, the external sources consulted, and the level at which each external
claim was verified. They follow `VERIFY-01`: every check carries its command and result, and a
check that could not be completed is declared.

## 1. Session environment

| Item | Value |
|---|---|
| Date | 26 September 2026 |
| Host | Claude Code cloud container (not the owner's workstation) |
| Python | `.venv/bin/python -VV` reports Python 3.12.3, the checkout-local fallback that `CLAUDE.md` permits on an ephemeral container |
| Repository base | `main` at `b87ee32`; full history and tags fetched with `git fetch --unshallow --tags origin main` |
| Ruleset | `dutchbay_bootstrap_rules.py`: 74 rules, version v3.0, all active |
| Handover resolver | `scripts/list_session_handover_records.py`: newest record `docs/H08_DELIVERY_HANDOVER.md` |

## 2. Repository receipts

### 2.1 Size and scope

```text
$ for d in analytics finance app api wind_resource solar_resource; do
    printf '%s ' "$d"; git ls-files "$d" | grep '\.py$' | xargs cat | wc -l; done
analytics 73979
finance 12303
app 13135
api 841
wind_resource 7033
solar_resource 2700
$ # sum of the six: 109991
$ git ls-files tests | grep -c -E '(^|/)test_[^/]*\.py$'
392
$ git ls-files 'scenarios/*.yaml' | grep -v -E '/(test|overrides|_scrtch)/' | wc -l
37
```

### 2.2 Debt-capacity check (correction C1)

```text
$ PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" .venv/bin/python - <<'PY'
from finance.debt_v14 import size_debt_with_dual_dscr, _npv
cfads = [10.0] * 15
repo = size_debt_with_dual_dscr(cfads, cfads, dscr_target_p50=1.30, dscr_target_p99=1.30,
                                capex=1e6, debt_ratio_max=1.0, debt_rate=0.08)
print(repo["debt_sized"], _npv(cfads, 0.08), _npv(cfads, 0.08) / repo["debt_sized"])
PY
65.84214375327976 85.5947868792637 1.3
```

The capex and gearing cap were set so that neither binds, isolating the formula. `_npv` is the
debt module's own period-1-to-N discounting helper, so both figures share one discounting
convention.

### 2.3 Audit register and overlay

States quoted in section 7 of the analysis were read from
`docs/audit/2026-08-controlled-successor/registers/findings_register.v2.json` (as of
2026-08-16, audited commit `7e99f34`) and `findings_current_state_overlay.v1.json` (current-main
snapshot `63b67eb`). Every finding cited carries `hold_effect: blocks_board_lender_release`.
The overlay records P2-F5-01 and P2-MC-SENS-02 as `implementation_delivered_review_pending`,
P2-F5-02 as `external_evidence_blocked`, P4-COMPLEX-01 as `deferred_current_state_not_examined`,
and every other cited finding as `open_current_state_not_examined`.

### 2.4 Code facts relied on

| Fact | Where it was read |
|---|---|
| Debt sizing on NPV of CFADS divided by target DSCR | `finance/debt_v14.py:1984` |
| Gearing solved against the real schedule | `finance/debt_v14.py:1251` |
| DSRA funded at close only when `dsra.fund_at_close` is set; lender case does not set it | `finance/debt_v14.py:1593`; `scenarios/dutchbay_lendercase_2025Q4.yaml:502` |
| Straight-line and split straight-line depreciation only | `finance/cashflow_v14_tax.py:359`, `:396` |
| `loss_carryforward_years` required, `>= 0`, `0` disables carry-forward | `finance/cashflow_v14_tax.py:243`, `:290`, `:488` |
| Binary interest deductibility | `finance/cashflow_v14_tax.py:174` |
| Forward hedge contract | `finance/cashflow_v14_contracts.py:8` |
| No BESS dispatch simulation | `finance/bess_revenue.py:68` |
| Hydro is enum-only and gated | `finance/tech_types.py:25-44` |
| Solar producer is fixed tilt | `solar_resource/pv_producer.py`, module docstring |
| Three statements rendered in the lender report | `app/reports/report_model.py`, `app/reports/templates/report.html.j2` |
| Sub-annual modules absent from `main` | `ls finance/period_grid_v14.py finance/subannual_rows_v14.py` reports both missing; reverted by #1232, re-proposed in draft #1231 |

### 2.5 Formula workbooks carry no computed values (correction C7)

Run in a scratch directory outside the repository; the file was deleted afterwards.

```text
$ .venv/bin/python - <<'PY'
import openpyxl
wb = openpyxl.Workbook(); ws = wb.active
ws["A1"], ws["A2"], ws["A3"] = 2, 3, "=A1*A2"
wb.save("f.xlsx")
print("openpyxl", openpyxl.__version__)
print("formula view:", openpyxl.load_workbook("f.xlsx")["Sheet"]["A3"].value)
print("cached value view:", openpyxl.load_workbook("f.xlsx", data_only=True)["Sheet"]["A3"].value)
PY
openpyxl 3.1.5
formula view: =A1*A2
cached value view: None
```

## 3. External sources

The session's network policy blocked direct retrieval of `eur-lex.europa.eu`, `www.fca.org.uk`,
`www.ag-grid.com` and `www.gov.uk`. The claims below were therefore checked against search-engine
summaries of the named pages, cross-checked where several independent sources agree. The
"Level" column says which. None of these claims is used by code in this change; any dolphin that
relies on one must first verify it at the primary source and ingest PDFs through the governed
MarkItDown workflow (`R26`).

| Claim | Source | Level |
|---|---|---|
| All 35 LIBOR settings have permanently ceased; the last synthetic US dollar settings were published on 30 September 2024 | FCA, "The end of LIBOR", <https://www.fca.org.uk/news/press-releases/end-libor>; Bank of England, <https://www.bankofengland.co.uk/news/2024/october/the-end-of-libor> | Summary of primary, two regulators agree |
| CBSL introduced a single Overnight Policy Rate effective 27 November 2024; SDFR and SLFR ceased to be policy rates | CBSL, Monetary Policy Review No. 6 of 2024, <https://www.cbsl.gov.lk/en/news/monetary-policy-review-no-6-of-2024>; <https://www.cbsl.gov.lk/en/rates-and-indicators/policy-rates> | Summary of primary |
| BEPS Action 4 recommends a fixed-ratio rule in a 10%-30% of EBITDA corridor, with an optional group-ratio rule | OECD (2016), Action 4 2016 Update, <https://www.oecd.org/content/dam/oecd/en/publications/reports/2016/12/limiting-base-erosion-involving-interest-deductions-and-other-financial-payments-action-4-2016-update_g1g745d0/9789264268333-en.pdf> | Summary of primary; PDF not converted |
| ATAD Article 4: 30% of EBITDA; optional EUR 3 million safe harbour; optional exclusion of loans funding long-term public infrastructure projects where operator, borrowing costs, assets and income are in the EU; optional standalone-entity exclusion | European Commission report COM(2020) 383, <https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:52020DC0383> | Summary of primary |
| The writing-down allowance is a United Kingdom capital-allowances mechanism on a reducing-balance pool basis | LITRG, <https://www.litrg.org.uk/working/self-employment/calculating-self-employed-profits/business-expenses-capital-and-capital-allowances>; Saffery, <https://www.saffery.com/insights/articles/capital-allowances-a-practical-guide-for-uk-businesses/>; HMRC manual CA23220 (blocked) | Secondary, two sources agree |
| The One Big Beautiful Bill Act (4 July 2025) ends sections 45Y and 48E for wind and solar placed in service after 31 December 2027 unless construction began by 4 July 2026 | Sidley Austin, <https://www.sidley.com/en/insights/newsupdates/2025/07/the-one-big-beautiful-bill-act-navigating-the-new-energy-landscape>; Kirkland & Ellis, <https://www.kirkland.com/publications/kirkland-alert/2025/08/one-big-beautiful-bill-act-brings-big-changes-to-green-energy-tax-credits>; Latham & Watkins on narrowed beginning-of-construction guidance, <https://www.lw.com/en/insights/treasury-guidance-narrows-beginning-of-construction-rules-for-wind-and-solar-projects> | Secondary, three sources agree |
| Sri Lanka Inland Revenue Act No. 24 of 2017, section 18, limits deductible financial cost by a debt-to-capital-and-reserves ratio, with carry-forward of the excess | The Sunday Times (Sri Lanka), 15 February 2026, <https://www.sundaytimes.lk/260215/business-times/reforming-interest-deductibility-in-sri-lankas-tax-policy-631197.html>; Oxford Business Group, 2018; primary text <https://www.ird.gov.lk/en/publications/Acts_Income%20Tax_2017/IR_Act_No_24_2017_E.pdf> and amending Acts (not ingested) | Secondary only. The ratio in force after amendment and the carry-forward term are **not verified**. Must be ingested before dolphin B5 |
| AG Grid Excel export is an Enterprise feature; the Community edition needs no licence | AG Grid, "Community vs. Enterprise", <https://www.ag-grid.com/react-data-grid/community-vs-enterprise/> | Summary of vendor page |
| TimescaleDB is dual-licensed: an Apache 2.0 core, and Community features under the Timescale License, free to self-host but restricted for database-as-a-service | Tiger Data, "Compare TimescaleDB editions", <https://www.tigerdata.com/docs/about/latest/timescaledb-editions>; licence text <https://github.com/timescale/timescaledb/blob/main/tsl/LICENSE-TIMESCALE> | Summary of primary |

## 4. Claims not verified in this session

- The current section 18 ratio and carry-forward period in Sri Lanka (secondary sources disagree
  on whether the manufacturing and non-manufacturing ratios were unified; primary text not read).
- Any United Kingdom rate change after April 2026; the allowance's current rates were not needed
  and are not stated in the analysis.
- Whether a chosen hosting provider supports the TimescaleDB extension.
- Whether LKR hedging instruments are available at project tenor; this is a market-evidence
  question for the F5-02 intake.
- The documented 0.05 s full-run timing in `docs/ARCHITECTURE.md`; cited, not re-measured.

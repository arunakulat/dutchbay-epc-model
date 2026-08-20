# Independent Refuter — DFI Covenant and Security Claims

**Cutoff:** 2026-08-12
**Audit source:** `/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_2026-08`
**Repository:** `arunakulat/dutchbay-epc-model@7e99f34d75b9c3d44a5c5b260cedbe403d2f79e8`
**Posture:** read-only source, code, and numerical refuter pass; no threshold or transaction assumption was changed

## Result

The canonical project has weak coverage, a large structural scheduled-maturity balance, incomplete early DSRA funding, and no modeled structural FX mitigation. These remain serious credit issues. The audit nevertheless overstated their provenance and, in places, the current implementation state.

No official evidence establishes a universal IFC/ADB 1.35–1.50 minimum band that applies equally to DSCR, LLCR, and PLCR. The archive instead contains context-specific examples spanning 1.25–1.50, a generic IFC solar guide describing DSCR of at least 1.3 or 1.5 for merchant solar, and separate high-level definitions of DSCR, LLCR, and PLCR. DutchBay thresholds require transaction-specific definitions and credit judgment.

The canonical balloon treatment is `cash_sweep`, not an unmodeled refinance or pure terminal bullet. The sweep is materially incomplete. The six-month DSRA target is not funded at close. The model charges guarantee and political-risk-insurance fees without modeling the corresponding instruments' benefit. Several apparent “enforcement” configuration flags have no production consumer, but the model already computes a failing covenant snapshot and can headline the case as not bankable.

## Finding dispositions

| Claim | Disposition | Refuter conclusion |
|---|---|---|
| P3-COV-01 — 1.30 DSCR target and DFI band | `partially_confirmed` | The 1.30 target is thin and merits challenge; the universal IFC/ADB 1.35–1.50 policy attribution is unsupported. |
| P3-COV-02 — LLCR/PLCR below a common DFI band | `partially_confirmed` | LLCR 1.2677 and PLCR 1.3069 are reproduced, but one common policy threshold for all ratios is unsupported. |
| P3-COV-03 — balloon and lack of resolution | `partially_confirmed` | The 48.8929% structural scheduled-maturity balance is real, but `cash_sweep` is implemented. It recovers only part of the balance and leaves a material residual. The 10% ceiling is internal policy, not DFI policy. |
| P3-COV-04 — low gearing | `confirmed` | Approximately 41% gearing is CFADS-constrained by the implemented sculpt; it is not evidence of conservative economics by itself. |
| P3-COV-05 — DSRA and receivables guarantee | `partially_confirmed` | Six-month target, zero close funding, incomplete first-year reserve, dead receivables-guarantee field, and fee-only guarantee semantics are confirmed. The 9–12-month DSRA claim is not supported. |
| P3-COV-06 — no structural FX mitigation | `partially_confirmed` | No hedge, indexed tariff, currency reserve, or modeled guarantee cash support was found. Final mitigant requirements remain transaction-specific. |
| P3-COV-07 — covenant enforcement disabled | `partially_confirmed` | Three fail/enforce flags are unwired no-ops, but the snapshot returns `FAIL` and the report can state “Not bankable — covenant breach.” |
| P3-COV-08 — maintenance reserve and lock-up tiers | `confirmed` for implementation absence | The model lacks those mechanisms; whether they are mandatory is a transaction-policy decision. |

## Canonical reproduction at the audited commit

| Item | Reproduced value / state |
|---|---:|
| Structural balance at scheduled maturity | USD 38,907,533.974 |
| Share of principal after IDC | 48.892896% |
| Configured treatment | `cash_sweep` |
| Cash swept after maturity | USD 22,021,308.209 |
| Residual at project end | USD 16,886,225.765 |
| Internal `max_balloon_pct` | 10%; breach true |
| DSRA target | 6 months |
| `fund_at_close` | `false`; close balance USD 0 |
| Operating year 1 target / funding | USD 8,099,467.954 / USD 4,767,959.778 (58.9%) |
| Operating year 2 balance | USD 7,420,953.958 |
| Guarantee fee plus PRI fee | 75 bp + 100 bp = 1.75% of opening debt annually |
| Total fee burden | USD 17,296,565.055 |
| Covenant snapshot | `FAIL`; three years below the 1.30 threshold |

The preserved files are `reproductions/canonical_covenant_reproduction.json`, `reproductions/canonical_covenant_fee_and_reserve_reproduction.json`, and `reproductions/covenant_config_consumer_trace.json`.

## Configuration-consumer findings

| Configuration field | Production behavior at `7e99f34` |
|---|---|
| `fail_on_covenant_breach` | No production Python consumer. |
| `fail_on_large_balloon` | No production Python consumer. |
| `enforce_hard_covenants` | No production Python consumer. |
| `receivables_guarantee_months` | Accepted by validation but has no runtime consumer. |
| `use_revenue_guarantee` | Controls a separate 75 bp WACC load; it does not create a payment-support cash flow. |
| Guarantee and PRI fee rates | Charged through the debt fee schedule irrespective of a modeled benefit. |

Simply turning the three fail/enforce flags to `true` would therefore be a false remediation. Enforcement requires code, tests, explicit failure semantics, and report reconciliation.

## Primary-source boundary

- IFC's 2015 solar developer guide describes a DSRA as often six months of debt service and gives broad solar DSCR examples of 1.3 and 1.5 for merchant cases. It is guidance, not IFC credit policy for DutchBay (`PSR-0016`, `PSR-0017`).
- ADB's Burgos wind review records a six-month offshore DSRA alongside an EDC parent guarantee. It is transaction precedent, not a universal policy (`PSR-0018`).
- ADB and World Bank examples in `PSR-0006` through `PSR-0008` use different structures and thresholds. They support lender challenge, not a universal rule.
- The 2025 Sri Lanka PAD's legacy 12-month structure and proposed six-to-nine-month IDA-backed SBLC are PPA payment security, not DSRA (`PSR-0013`, `PSR-0014`).
- GitHub issue #920 records that no DutchBay lender term sheet had been produced at its checkpoint. It is an internal evidence-status record, not proof that no off-repository communication exists (`PSR-0012`).

## Corrected circulation wording

> The canonical model produces minimum DSCR 1.2857, LLCR 1.2677, and PLCR 1.3069. These ratios and the project's risk profile warrant lender challenge, but the audit has not established a universal IFC/ADB threshold applicable equally to all three ratios. The debt schedule carries a 48.8929% structural balance at scheduled maturity; the configured cash sweep recovers about USD 22.02 million and leaves about USD 16.89 million at project end. The scenario targets a six-month DSRA but funds zero at close and only 58.9% of the first operating-year target. Thresholds, reserve sizing, permitted residual debt, security, and enforcement must be confirmed against financing documents.

## Open dependencies

1. Obtain facility, common-terms, intercreditor, account-bank, tax, reserve, hedge, guarantee, and lender-model definitions.
2. Do not re-baseline DSCR, LLCR, PLCR, DSRA, or balloon limits from generic precedent alone.
3. Implement flag enforcement and guarantee/payment-support semantics through separate tested dolphins.
4. Preserve the large residual debt as a transaction blocker until genuine refinancing or full amortization is evidenced.

# NSO 250MW BESS tax layer and RFP timeline — domain review record

**Record status:** blocking review checkpoint under `RECRUIT-01` and `PERSIST-01`
**Review role:** renewable/hybrid project feasibility and project-finance domain specialist
**Reviewer posture:** strictly read-only. No file, Git, GitHub, issue or release-state mutation.
**Important boundary:** this is a specialist AI review. It is not statutory assurance, an external
audit opinion, lender acceptance, a verified human professional engagement, or package release
authority.

## 1. Candidate bound

| | |
|---|---|
| candidate commit | `b4c2d25dc97b25b5e3d379238522a43c4ccaa16a` |
| candidate tree | `c3f923865f819cc0463f9f87c26f413295811a6e` |
| base | `ba4b51898f53afa6bb35f1e1464efb43c1c73951` |

Verified by the reviewer with `git rev-parse HEAD` / `HEAD^{tree}` / `origin/main`. Working tree
clean before and after. Base scenarios extracted read-only to `/tmp` via `git archive`.

## 2. Disposition on `b4c2d25`: **VETO**

### Blocking counterexample

The change switched on an enhanced capital allowance whose stated eligibility test the model's own
capex fails in every one of the eight scenarios, while the header asserted the opposite —
"its depreciable base sits inside the band".

Computed from the scenarios themselves via `finance.debt_v14._extract_capex_base_usd` and
`finance.import_levies.capex_uplift_lines_usd`, against a USD 250,000–3,000,000 band:

| scenario | capex_usd | levy uplift | depreciable base | per-site plant | band |
|---|---:|---:|---:|---:|---|
| `unit_bidimplied` | 3,465,103 | 59,773 | 3,524,876 | 3,172,388 | BREACH (1.06×) |
| `unit_upside` | 5,899,824 | 101,772 | 6,001,596 | 5,401,436 | BREACH (1.80×) |
| `unit_base` | 5,940,027 | 102,465 | 6,042,492 | 5,438,243 | BREACH (1.81×) |
| `unit_stress` | 6,310,122 | 326,549 | 6,636,671 | 5,973,004 | BREACH (1.99×) |
| `portfolio_bidimplied` | 83,162,464 | 1,434,553 | 84,597,017 | — | BREACH (25×) |
| `portfolio_upside` | 141,595,785 | 2,442,527 | 144,038,312 | — | BREACH (42×) |
| `portfolio_base` | 142,560,645 | 2,459,171 | 145,019,816 | — | BREACH (43×) |
| `portfolio_stress` | 151,442,925 | 7,837,171 | 159,280,096 | — | BREACH (45×) |

Every variant is over on all three defensible readings of "total investment in a new undertaking":
pre-levy capex per site, levy-inclusive depreciable base per site, and the plant-only base the
header itself named. Read per portfolio the base is 48× the ceiling.

**The allowance was the dominant driver of the headline result.** Isolating each driver
(`raw_config` mutated in memory, nothing written), on `portfolio_bidimplied`:

| state | project IRR | equity IRR |
|---|---:|---:|
| base commit | 8.02% | 5.60% |
| candidate `b4c2d25` | 10.72% | 8.17% |
| candidate minus the allowance | 9.00% | 6.72% |
| base plus the allowance only | 9.51% | 6.82% |

Of the advertised +2.70pp project-IRR gain, **+1.72pp (64%) was the allowance alone**.

Aggravating: `project.boi_approved: false` sits in the same file while the header conditions the
allowance on BOI approval, and `grep -rn "boi_approved" --include=*.py` returns zero hits, so the
contradiction fails silent. The supporting law is not in the held corpus. And
`grep -rln "nso250" tests/` returned no files — nothing in CI would have caught it.

### What the reviewer verified as sound

- **SSCL mechanism — CONFIRMED CORRECT.** `IndirectTaxes.duty_rate` returns `0.0` when
  `bonded_scheme` is true and `cid + pal + sscl` otherwise. Setting the flag false and zeroing
  CID/PAL individually does leave SSCL live: `duty_rate` 0.025 post against 0.0 pre.
  **No VAT side effect** — `capex_vat_rate` keys only off `vat_capex_relieved`, true on both sides.
- **RFP timeline — SOURCE CONFIRMED VERBATIM** at RFP Volume I lines 468–478.
  `finance/debt_v14.py:512` reads `Financing_Terms.construction_years` defaulting to 2;
  `finance/equity_distribution_v14_hydra.py:733` consumes it. The key is genuinely read, not inert.
- **Allowance mechanism, eligibility aside — CORRECT.** `finance/cashflow_v14.py:304-308` applies
  the multiple to the whole base before the plant/civil split, so 2.0 does express
  "100% enhanced in addition to 100% normal".
- **All eight KPI deltas reproduced exactly.** `min_dscr_period` 1.3000 throughout. Unit and
  portfolio agree to the basis point.
- **Negative equity IRR on the three OEM-priced variants is a finding, not a defect** — the
  negatives pre-date the change and the change improves them slightly.
- **`stress` is still a genuine stress case** — `duty_rate` 0.075 against 0.025 on base.

### Latent couplings recorded

- `vat_on_duties: true` means the VAT base is `import_base + duties`. Duties are now non-zero, so
  if `vat_capex_relieved` were ever flipped false, SSCL would silently cascade into the VAT base.
  Dormant today; live the moment the VAT recovery position is revisited.
- Zeroing PAL applies to the whole 69% import share, whereas RFP Clarifications cl. 48 excludes
  transmission-line materials and external interconnection works. Disclosed in the header, so a
  disclosed optimism rather than a concealed one.
- cl. 47's "approval takes 6–8 weeks and can only be applied for after Financial Close" now sits
  against a 17-week FC-to-COD window in the same commit.

### Amendments required

1. Set `enhanced_allowance_applies: false` on all eight, or source the eligibility. Restate every
   KPI figure accordingly — `bidimplied` becomes 9.00% / 6.72%.
2. Resolve `project.boi_approved: false` against a header conditioning the allowance on it.
3. Fix the mangled header sentence — the per-variant clause was glued onto an unrelated paragraph.
4. Resolve the Addendum 01 contradiction: one line declares no such addendum is held while another
   cites "Addendum 01 item 13" as live authority.
5. Reword the `construction_years: 1` comment as a conservative rounding of 0.33 years.
6. Record that the upstream generator in the private corpus is now stale and would silently revert
   all corrections if re-run.
7. Add a KPI-pinning test. There is currently none.

### Not verified

The Sri Lankan legal content itself — Second Schedule, the band, the Northern Province 150%, the
SSCL raw-materials rule and both gazette contents. None appears in the corpus. **The veto does not
rest on the band figure being wrong; it rests on the scenarios breaching the band as the author
states it.** Also not verified: whether "new undertaking" is assessed per site or per portfolio
(immaterial — every reading breaches); ESA Article numbering; and the allowance's claimable timing
profile.

## 3. Coordinator response

All seven amendments applied at `HEAD` (see §4 of the assurance record for the shared remediation
list). Amendment 6 concerns a file in a different repository and is recorded rather than applied.

## 4. Re-disposition

Recorded in the pull request against the final head, after the remediation and after this record
and its assurance counterpart were themselves committed.

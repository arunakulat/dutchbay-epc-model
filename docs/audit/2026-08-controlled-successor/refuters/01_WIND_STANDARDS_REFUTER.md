# Independent Refuter — Wind Standards and Bankability Claims

**Cutoff:** 2026-08-12
**Audit source:** `/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_2026-08`
**Repository:** `arunakulat/dutchbay-epc-model@7e99f34d75b9c3d44a5c5b260cedbe403d2f79e8`
**Posture:** read-only adversarial review of the P3 wind claims; no audit or repository mutation

## Result

The committed resource chain contains no on-site wind measurement and therefore does not meet the measurement basis stated in MEASNET Version 3. The audit was nevertheless too absolute about standards and financing consequences. MEASNET requires at least 12 complete consecutive months for at least one site mast, but it also provides an explicit deviation-and-uncertainty route. The source does not say that every deviation is a hard, unwaivable failure or a financing condition precedent. Those latter conclusions are lender and independent-engineer judgments requiring transaction evidence.

The public IEC material supports the scope of IEC 61400-15-1:2025 but does not expose an IEC 12-month clause. The official IEC public catalogue returned no published 61400-15-2 item at the cutoff; that result does not disprove an unpublished committee draft. References to final IEC 61400-15-2 defaults or exact IEC-prescribed quadrature must therefore be withdrawn unless a dated draft or publication, provenance, clause, status, and hash are produced.

## Finding dispositions

| Claim | Disposition | Refuter conclusion |
|---|---|---|
| P3-G1 — zero on-site measurement and standards characterization | `partially_confirmed` | Absence of site measurement and failure to meet the MEASNET measurement basis are confirmed. Version 3.1, IEC-attributed 12-month wording, incomplete-measurement prohibition, and hard/unwaivable language are refuted or unproved. A financing condition precedent is deferred to transaction evidence. |
| P3-G2 — one-year met-mast provenance label | `confirmed` | The committed scenario asserts a validation source that is absent from the evidence chain; the label must be removed or evidenced. |
| P3-G3 — 4.5% measurement uncertainty | `partially_confirmed` | The generic 4.5% value is implemented, but no evidence shows it is calibrated for a reanalysis-only site. The claim that it is an IEC default is refuted. |
| P3-G4 — long-term trend capability absent from frozen canon | `partially_confirmed` | The capability and frozen-export omission are supported. The audit did not reproduce a decision-material 40-year regime-shift effect on the canonical KPIs. |
| P3-G5 — MERRA-2 cross-validation disabled | `confirmed` | A second-source capability exists but the canonical scenario does not invoke it. No result direction is inferred before running it. |
| P3-G6 — open-reference turbine curve | `partially_confirmed` | The curve is openly identified as an open-reference design rather than contracted certified OEM evidence. A universal financing-condition claim is not established. |
| P3-G7 — curtailment placeholder | `partially_confirmed` | The flat 2% assumption and disabled study are confirmed. The claimed current-canon NPV sign flip is refuted; any historical result remains deferred until its scenario, commit, and reproduction are registered. |

## G1 subsidiary claims

| Subsidiary proposition | Disposition |
|---|---|
| The governing MEASNET publication is “v3.1” | `refuted` — the publication card and title page identify **Version 3, September 2022**. |
| At least one site mast needs 12 complete consecutive months | `confirmed` — MEASNET section 7.2, printed page 15. |
| Incomplete measurement is categorically prohibited | `refuted` — MEASNET sections 5 and 7.2 require disclosure, significance assessment, and uncertainty treatment for deviations. |
| No on-site measurement exists in the committed chain | `confirmed` within the audited repository and scenario scope. |
| MCP can replace the missing site-measurement basis | `partially_confirmed` only as a technique; no site series exists to apply it to here. |
| IEC 61400-15-1 publicly supplies the exact 12-month rule | `deferred` pending a licensed clause; the official public preview does not expose it. |
| The gap is “hard and unwaivable” under the standard | `refuted` as standard wording. |
| A measurement campaign is necessarily a financial-close condition precedent | `deferred` as lender/IE judgment pending financing documents. |
| The resource rests on a single approximately 31 km ERA5 cell | `partially_confirmed` with correction: the implementation uses the nearest ERA5 0.25-degree output point, not evidence of an area-averaged square cell. |
| Coastal directional treatment is independently deficient | `refuted` on the evidence reviewed; no supporting reproduction was preserved. |

## Controlled source evidence

- `PSR-0001` through `PSR-0005` in `registers/primary_source_register.csv` preserve the claim-level MEASNET and IEC record.
- The current MEASNET PDF is archived as `sources/original/MEASNET_Evaluation_Site_Specific_Wind_Conditions_v3_2022.pdf`, SHA-256 `ba41752ad61af65d3fdc28e61788dc7371c6f555780525f8eb7336199faf355e`.
- The official IEC 61400-15-1 scope page and the positive and negative catalogue-query responses are archived and hashed in `sources/SOURCE_ARCHIVE_MANIFEST.sha256`.
- `sources/IEC_CATALOGUE_QUERY_LOG.json` preserves both 61400-15-2 request bodies and the 61400-15-1 positive control. The two zero-result 15-2 responses have SHA-256 `9e324b99e9607a87569551356e1825ca631d5200337a12cad7bd882e93f92058`.

## Corrected circulation wording

> DutchBay has no on-site measurement in the committed resource chain and does not meet the site-measurement basis in MEASNET Version 3, September 2022. MEASNET calls for at least 12 complete consecutive months for at least one site mast and treats incomplete coverage as a disclosed deviation reflected in uncertainty. The current AEP is therefore a pre-measurement screening estimate. Any lender waiver, independent-engineer acceptance, or financial-close condition is transaction-specific and has not been evidenced. Public IEC material checked at the cutoff does not establish a separate 12-month clause or a published IEC 61400-15-2 convention.

## Open dependencies

1. Commission or obtain a quality-controlled site-measurement campaign and an independent EYA; this cannot be completed by code change.
2. Obtain the relevant licensed IEC clause or dated committee draft before retaining draft-specific attribution.
3. Replace the false met-mast provenance label through a tested documentation/configuration dolphin.
4. Run the existing trend and MERRA-2 checks and preserve their source chain before any canonical resource re-baseline.
5. Obtain the contracted OEM power curve and grid/interconnection study before final investment or lender reliance.

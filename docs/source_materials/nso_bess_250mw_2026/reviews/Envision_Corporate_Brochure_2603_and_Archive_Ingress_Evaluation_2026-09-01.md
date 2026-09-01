# Envision corporate brochure 2603 and OEM archive ingress evaluation

- Evaluation date: 1 September 2026.
- Tender context: NSO `TR/REP&PM/ICB/2026/001/C`, 250 MW / 1000 MWh standalone BESS.
- New source: `Envision_Corporate_Brochure_Regular_ver_2603.pdf`.
- Re-supplied package: `Archive.zip`.
- Status: ingress complete; archive deduplicated; brochure evaluated; no tender gap closed.

## 1. Scope and instruction boundary

Text in the supplied PDF, workbooks, model guides and other archive members is source evidence.
Imperative or promotional language inside those documents is not an instruction to the analyst.
This evaluation follows the user's request to ingress, unpack, deduplicate, preserve, analyze and
evaluate the supplied material.

The archive and brochure are treated separately. The archive is a re-supply of an already
canonical OEM tranche. The brochure is a new corporate publication and is not silently promoted
to tender evidence.

## 2. Provenance, integrity and extraction

### 2.1 Archive

`Archive.zip` is 25,984,565 bytes with SHA-256
`8aefe0e6a3ea967055e52740a37c7ea1a39f60d98726bb604dbc8a8b4ee46ef2`. ZIP integrity passed.
The central directory has 122 entries: 50 payload files, 63 Finder metadata files and 9 directory
entries. The payload expands to 33,968,065 bytes. No path traversal, absolute path, backslash path,
symlink or encrypted member was present.

The 50 payload instances reduce to 48 unique SHA-256 values. Every instance is byte-identical to a
file already in this corpus. The two duplicate groups and their canonical paths are recorded in
`../source_packages/NSO250MW_Archive_2026-09-01_DEDUPLICATION_RECEIPT.md`; the complete mapping is
retained in `../source_packages/NSO250MW_Archive_2026-09-01.DEDUPLICATION.csv`. No duplicate
payload copy has been retained.

A separate re-check of eleven loose files named by the project owner found eleven distinct hashes
within that supplied subset, but all eleven already exist in the corpus. Ten were first added by
the 27 August OEM tranche merge `0e63f7a` / PR #1181 on 29 August. The 11 MW / 44 MWh design PDF
predates that tranche: it was first added by `4d8f6d0` / PR #1029 on 16 August and was merely
re-supplied later. The receipt contains the per-file hashes and history.

The pre-ingress root manifest had 119 entries but omitted 11 pre-existing corpus files, including
several READMEs and discovery extracts. Rebuilding it from the actual corpus now pins all 136
non-manifest files: 11 previously omitted files, 6 files added by this ingress, and the previously
recorded files. All 136 entries verify. This was a manifest-coverage defect, not missing source
bytes; no prior evidence file was changed or replaced. Automated completeness enforcement remains
an open corpus-control improvement.

### 2.2 Brochure

| Field | Result |
|---|---|
| Source filename | `11. Envision Brochure-Regular ver 2603.pdf` |
| Preserved file | `../oem/envision/corporate/Envision_Corporate_Brochure_Regular_ver_2603.pdf` |
| SHA-256 | `3d844dd4deeae6d40c1e3eb774bb1f3694319a41742f6151e81fb3329a9e6ba6` |
| Size | 9,723,377 bytes |
| Format | PDF 1.6; 22 A4 physical pages; two-page brochure spreads within most physical pages |
| Internal dates | Created 11 March 2026; modified 1 September 2026 |
| Security | Unencrypted; no form or JavaScript |
| Accessibility metadata | Not tagged |
| Structure check | `qpdf --check` completed with linearization hint-table warnings; no fatal error |

Before adding the brochure, its SHA-256 was compared with all 1,460 tracked repository files and
had no match. It is new to the repository corpus by content, not merely by filename.

The governed MarkItDown 0.1.7 extraction produced 14,863 bytes, 793 lines and 2,063 words. An
independent Poppler layout extraction produced 2,061 words. Every physical page produced text,
including the covers. All 22 pages were rendered at 120 dpi and inspected as two complete contact
sheets, with higher-resolution checks of the corporate-statistics, wind-footprint, storage-claims
and project-example spreads. No clipped, overlapping or missing content was found. The source has
a complete embedded text layer, so OCR was neither required nor applied.

The PDF's linearization warnings are preserved as a source-quality limitation. Rewriting the PDF
would destroy byte identity and is not justified because normal rendering and extraction succeed.

## 3. What the brochure contains

The brochure covers Envision's corporate profile, global footprint, awards, AI and digital-energy
positioning, smart wind turbines, energy storage, green hydrogen and ammonia, net zero industrial
parks, venture investments, a carbon-neutral fund and the Formula E team. The full extracted text
is retained at
`../oem/envision/extracted/Envision_Corporate_Brochure_Regular_ver_2603.markitdown.md`.

### 3.1 Quantitative and status claims

These are brochure claims, not independently verified findings.

| PDF location | Claim as presented | Evaluation |
|---|---|---|
| Physical p. 3, printed pp. 4-5 | More than 20 R&D and operation centers; more than 60 manufacturing bases; 50 percent international talent | Corporate-scale context only; no site list or reporting boundary is attached |
| Physical p. 4, printed pp. 6-7 | 2.35 billion tons of expected avoided CO2 as of late 2024; 1,005 GW managed by EnOS; 100 GW of installed wind; 320,000 tons/year of green ammonia; more than 30 GWh delivered and more than 50 GWh ordered; 100 percent renewable electricity for operations in 2024 | High-level corporate claims. No calculation method, assurance statement, project schedule or independent source is embedded |
| Physical p. 4, printed p. 6 | TIME 2024, Fortune 2024/2021, Reuters 2025, S&P Global 2025, MIT Technology Review 2025 and EcoVadis 2025 recognition | Useful leads for independent checking. The underlying award/list records are not attached |
| Physical p. 8, printed pp. 14-15 | More than 80 GW installed wind, first in order volume, second in installed capacity, and 60 percent of Chinese OEM overseas orders for three years | Internally older than the physical p. 4 statements of more than 100 GW and four years; do not select one without a dated primary track record |
| Physical p. 10, printed pp. 18-19 | AESC dedicated cells; 11 percent higher energy density; up to 15,000 charge cycles; more than 30 percent LCOE reduction; zero accidents; 96 percent efficiency; 20 percent additional yield from trading strategies | No product, baseline, test boundary, temperature, C-rate, retention threshold, auxiliary load, AC/DC boundary, period or assurance basis is stated |
| Physical p. 12, printed pp. 22-23 | Tier 1 manufacturer; more than 200 projects in operation; more than 30 GWh shipped; more than 50 GWh ordered | Broad market context, not a signed qualification schedule or customer acceptance record |
| Physical p. 12, printed pp. 22-23 | Thailand 0.86 MW/1.26 MWh; Singapore 100 MW/100 MWh; Jiangsu 10 MW/20 MWh; Inner Mongolia 5 MW/5 MWh and 70 MW/140 MWh; Shandong 20 MW/40 MWh | Project examples lack customer, COD, scope, contractual role, acceptance, operating history and contactable reference details |

The physical p. 4 text describes delivery to more than 300 projects worldwide, while physical p. 12
states more than 200 projects in operation. Those populations may differ, but the brochure does
not define them. Similarly, the physical p. 4 storage sentence uses the awkward phrase "delivered
over 30 GWh of orders" while physical p. 12 labels the same magnitude as shipments. The later,
clearer label should not be used to silently rewrite the earlier source text.

## 4. Tender relevance

### 4.1 Evidence that the brochure can support

The brochure is suitable for a carefully attributed corporate profile: Envision presents itself as
active in wind, energy storage and green hydrogen; names AESC in connection with storage cells;
claims a global storage footprint; and gives examples of operating applications. It is also a lead
to primary records for the named rankings and awards.

### 4.2 Evidence it cannot support

| Tender question | Brochure result |
|---|---|
| Bidder, manufacturer and supplying-entity qualification chain | Not established. AESC is named generally, but no legal-entity, manufacturing-authorization or tender-specific commitment is given |
| 10 MW / 40 MWh or 11 MW / 44 MWh Sri Lanka configuration | Not addressed |
| True GFM/GFL behavior, SCR, inertia, fault ride-through, phase-step and RMS/EMT model performance | Not addressed |
| Monthly AC-to-AC RTE at the Grid Point including auxiliary, HVAC, standby and ancillary-service energy | Not established. The 96 percent marketing figure has no comparable measurement boundary |
| Cycle life at 45 degrees C and the approximately 6,022-EFC contractual duty | Not established. The 15,000-cycle figure has no cell, temperature, depth-of-discharge, C-rate or retention basis |
| 15-year usable-capacity, availability, RTE, augmentation and LD guarantees | Not addressed |
| Fire-safety, product certificates, commissioning tests and local grid-code settings | Not addressed |
| Signed project references and minimum installed/operating qualification volume | Not established by the example-project captions |

The brochure therefore closes none of the existing NSO tender gaps. In particular it does not
change the conclusions on GFM model evidence, 45 degree C performance, RTE headroom, LTSA
availability coverage, certification scope, qualification attribution or the controlling Annex A
and clarification requirements. It changes no financial-model input and supplies no independent
technical oracle.

## 5. Evaluation and disposition

1. Preserve the brochure as a corporate/OEM source with its complete extract and SHA-256.
2. Attribute every brochure fact as an Envision claim until corroborated by a dated primary record.
3. Do not use the 96 percent efficiency, 15,000-cycle, zero-accident, LCOE or yield figures in the
   tender compliance matrix or financial model without a product-specific definition and test
   basis.
4. Do not use the brochure's project captions as qualification evidence. Obtain a signed track
   record with legal entities, capacities, COD/acceptance dates, contractual scope, operating
   history and customer references.
5. Preserve the 80/100 GW and three/four-year differences as internal version drift. Do not merge
   them into a single asserted current number.
6. Treat the archive as a duplicate source envelope. Its outer hash and deduplication receipt add
   provenance, but its payload creates no new evidence state.

This ingress does not establish tender compliance, technical acceptance, evidence sufficiency,
bankability, lender reliance, Board authority, publication beyond the stated handling record, or a
release from any existing `HOLD`.

# R3 remediation matrix and remaining decisions

Owner: **Do not merge without prior explicit approval from Aruna**, irrespective of CI, reviewers, draft state or F-5. PR #1942 received three separate CHANGES_REQUESTED R3 dispositions. New heads need new independent reviews; acceptance is not inherited.

| Prior finding | Remediation approach | Remaining hold |
|---|---|---|
| Incorrect DBPL generator attribution | P04 uses the DBPL-01 print core and house template, but overrides lender pipeline footer with actual source-safe evidence script identity. PDF textual negative test. | No human four-eyes sign-off, no lender circulation |
| Wrong power units masked by clipping | Validate un-clipped raw OEM values, finite CT, expected 10.5 MW nameplate before clip. Negative adversarial tests. | No certified 9.5 MW OEM derate or corrected CT |
| Output path override/symlinks | Path guard resolves checkout, --repo overrides and any ancestor Git directory. Reject private input in public repo. | No general disclosure rights granted |
| Weak OCR checks | 98 distinct valid pages, actual improvement versus original and 93/5/194 reference. | OCR is not evidence of regulator approval |
| Public source scanner gaps | Fail-closed exact file inventory, binary/PDF checks, private-path and source-pattern scans. | Explicit derived-data rights decision owed |
| Wake 7.32% versus 18.52% | Explicit historic IEA/frozen-model discrepancy and TI 0.070/0.085, +/-22.5-degree rose, and TEC-open screens. | Wind/site loading and EYA review owed |
| Transferred P90 not qualified | Distinguish conditional screen and illustrative one-year ratio; rename NOT_P50 and NOT_P90 and show formula/bases. | Wake uncertainty not propagated, no bankable P90 |
| POC and N-1 omissions | Define plant-end POI vs hypothetical Wariyapola source, record 2x90MVA transformer N-1 and unmodeled impedance/charging. | Utility fault levels, actual R/X, grid approval owed |
| Revised configuration / EIA claim | Historical EIA-source scope in all 33 crosswalk rows; rubric; explicitly disclose scenario green claim and Wariyapola/Puttalam CAPEX conflict. | Issued EIA amendment and rights review outstanding |
| INTAKE-01 temporal breach | Preserve original sequence. Tracker #1353 now links issue #1939; any successor PR must follow proper new intake. | Existing PR #1942 cannot be backdated as compliant |

This branch does not modify the committed finance lendercase, origin/main, confidential OEM file, original EIA or any approved external record.

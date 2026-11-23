# Test/reproduction receipts (PERSIST-01 / VERIFY-01)

**Risk:** R3. This branch is a frozen review candidate, not an independently accepted lender deliverable.

1. Original 23 Nov wind study, commit 49b9527c: 7 PyWake configurations with private OEM curve at runtime; one-turbine frozen Blue Whale numerical agreement to 0.02%; no accepted wake loading or bankability claim.
2. Original 23 Nov grid screen, commit 49b9527c: 10 Wariyapola fault/circuit sensitivities, advisory only, no utility fault-equivalent basis.
3. Replay on newer 071d7476: all 7 wind and 10 grid numerical cases matched firstpass within 1e-8.
4. New #1939 branch from 13ec3c62: config-first wind tool independently reproduces the exact seven earlier derived figures within 1e-8 using runtime-only authorized private OEM power/Ct curve. Grid script reproduces 10 previous SRC cases within 1e-9.
5. Previous component regression at 071d7476: 199 passed / 1 skipped (the private complete-series integration test), three SWIG warnings. It did not prove genuine reviewer independence and was not full suite.
6. DBPL-P03 uses the established repository print core; source-safe 13-page A4 output, font embed, no EIA source-page bitmap, 33-item EIA/feasibility crosswalk and 25-module matrix. PDF private-data scan and layout inspection completed.
7. Private OCR validation: 98 targeted pages, 93 substantial text, 5 weak; 194 other pages preserved. Script included for reproducing QC with private EIA PDFs. Full originals not pushed.

**Explicit not run/not satisfied:** full project CI/review pair, licensed wind/DERATE independent engineering study, updated ERA5 hourly fetch, site-specific P50/P90 qualification, verified utility network fault model, issued EIA amended consent, grid commissioning, updated OEM landed offer, FX/tenor under new case, Board/lender circulation authority and F-5 exit.

**Current public-source-safe controls:** run tools/verify_public_package.py (does not require private OEM curve). The wind and grid reproduction scripts require their respective inputs and refuse to write output within the Git checkout. No secret-bearing environment contents are committed.

## R3 remediation retest — 24 November 2026

- Prior formal exact-head R3 review on PR #1942: three separate CHANGES_REQUESTED verdicts (domain, assurance and finance/E&S). They remain valid for the previous frozen head, not automatically resolved by remediation.
- D1 safety tests cover OEM raw power units (watts, MW, NaN, negative), path overrides, Git trees, symlinks and invalid OCR selection.
- D2 five wind/rose/TI/TEC screens (not stochastic bounds), explicit 7.32% vs 18.52% unresolved wake, retained 10.5 MW Ct at 9.5 MW clip and 2x90 MVA transformer N-1 not included in SCR.
- D3 P04 DBPL regeneration corrects footer attribution and separates Puttalam/Wariyapola, historical 15-WTG EIA from proposed 14 EN206; full finance pipeline unchanged.
- D4 public package verifier uses allowlisted inventory and PDF text/image and SHA checks, with extra hostile negative tests. Third-party derived-data rights remain unconfirmed.
- Repeat independent reviews at new exact head; no green FAST test or deferred draft CI implies lender release.

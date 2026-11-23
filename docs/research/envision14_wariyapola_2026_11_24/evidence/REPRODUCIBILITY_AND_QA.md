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

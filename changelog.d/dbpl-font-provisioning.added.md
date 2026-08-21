Added `app/reports/dbpl/fonts.py` and bundled the DBPL house superfamily — Source Serif 4 (body),
Source Sans 3 (tables and furniture) and Source Code Pro (identifiers), all SIL OFL and all
verified tabular by default, which is what aligns a column of DSCRs without decimal tabs.
Resolution is bundled → system → web (opt-in) → metric-compatible fallback, and the tier that
answered is surfaced: WeasyPrint renders happily with a substituted face, so a successful render
is no evidence the house font was used.

Added the DutchBay Presentation Layer (`app/reports/dbpl/`) and GWTF rule **DBPL-01**. DBPL now
names a print contract, not a look: any PDF described as a DutchBay Presentation Layer / dbpl
document must be produced through `render_dbpl_pdf`, which requires the complete `[report]` extra
(weasyprint, reportlab, geopandas, contextily) plus the DBPL font stack, applies the house style,
and surfaces font provenance. The style tokens were measured from
`DUTCHBAY_ANALYST_GENERATED_SYNTHETIC_LENDER_TERM_SHEET_2026-08-18.pdf`, not invented. The image
now installs `fonts-liberation` so the house families resolve natively. Documented in
`docs/dbpl_styleguide.md` and `AGENTS.md`.

- **Draft Envision proposal build chain** — `docs/source_materials/nso_bess_250mw_2026/proposal/`
  now holds the generator, the Word renderer and the v0.1-v0.3 drafts, committed on the project
  owner's explicit instruction. Committing it **closed a defect**: `make_docx.js` consumed a
  `proposal.json` that nothing produced, so the Word issue had no reproducible source and the two
  formats could drift silently. The generator now exports that document model itself, deliberately
  **without** the PDF render-provenance lines, which describe how the PDF was rasterised and would
  read in a Word file as claims about a document they do not describe. Verified against the
  delivered v0.3: 474 text runs, 82 red gap-fill runs, **zero differing runs — exact text match**.
  The directory README records the red-text convention (black = sourced, red = drafted gap-fill and
  not a representation about the offered product) and the `make_docx.js` spread-order bug that once
  produced 1 red run instead of 83, presenting every drafted gap-fill as sourced.

- Add `libharfbuzz-subset0` to the image's WeasyPrint runtime library set. WeasyPrint 70.0 dlopens
  it by name at import with `allow_fail=True`; without it the import emits a `DeprecationWarning`
  that the library "will be required by future versions", and every subsequent render falls back to
  fontTools and logs, once per font face:

      Using fontTools instead of HarfBuzz-Subset for font "Source Serif 4". This will be
      unsupported in future versions of WeasyPrint. Please install HarfBuzz-Subset >= 4.1.0
      with your package manager.

  Six of those on a small DBPL page, none with the library present. The Dockerfile comment calls its
  list "the exact bookworm set", so the omission was a claim as well as a gap.
- Nothing is broken today and this is not a security fix. fontTools is a hard WeasyPrint dependency,
  so the fallback is always available; output without the library is a valid, correctly tagged
  PDF/UA-1 document. It is taken now because the warning is a deprecation notice, and the version
  that removes the fallback would otherwise land as a surprise on whoever runs the next bump, on the
  lender-facing PDF path.
- **The deliverable does not change; the container bytes do.** Rendered pages, extracted text,
  structure, tagging, page geometry and `pdf/ua-1` marking are identical either way. What differs is
  the embedded font programs: fontTools passes through tables HarfBuzz drops -- `BASE` on the
  variable house faces, `FFTM` on DejaVu -- and produced a larger program in every face measured
  (four faces, +44 to +88 bytes each). **Glyph coverage never differs.** Both subsetters are driven
  by the same shaped GID set, and outlined-glyph counts and cmap codepoint counts matched exactly in
  every face, both ways: this change cannot drop a glyph from a lender document. The direction of
  the size effect is consistent, but its magnitude depends on which faces and glyphs a document
  uses, so no figure is quoted here as if it were a property of the change.
- No byte-level receipt is published, because the fontTools path is not byte-stable: three renders
  of one fixed document on one host gave two distinct hashes and two distinct sizes on that path
  while the HarfBuzz path gave one. An earlier draft of this fragment quoted a single pair of byte
  counts as a receipt; they do not reproduce, and a figure a reviewer cannot re-run is not a receipt.
- Retracted from an earlier draft: the assertion that "the byte-identical-output expectation for
  DBPL PDFs does not survive this commit". There is no such expectation and there never was. DBPL
  output is already not byte-reproducible run to run, with or without this change -- four renders of
  one document through `app.reports.dbpl.print_core.render_dbpl_pdf` gave four distinct hashes and
  three distinct sizes, because fontTools restamps `head.modified` with wall-clock time when it
  instantiates the variable house fonts, and that runs on both paths. Nothing in the tree asserts a
  PDF hash, size or byte-identity; the only byte assertions on a PDF are `pdf[:5] == b"%PDF-"`.
- The CI image build proves that `libharfbuzz-subset0` **resolves and installs** on bookworm
  (`6.0.0+dfsg-3`) -- the `RUN` line changed, so its layer cache key changed and the install genuinely
  re-executed. It does not prove WeasyPrint can use it: `/health` renders no PDF. The library is
  nonetheless reachable there rather than inert, because WeasyPrint gates the HarfBuzz path on
  `hb_version_atleast(4, 1, 0)` and bookworm's 6.0.0 clears it. Asserting the HarfBuzz path inside
  the built image is a real gap in the image gate, but it predates this change and belongs in its
  own commit rather than loaded onto a one-package change.

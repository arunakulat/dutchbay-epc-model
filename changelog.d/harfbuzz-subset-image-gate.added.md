- **The image gate now proves WeasyPrint takes the HarfBuzz-Subset path, inside the image.**
  `docker-build` renders a PDF in the built image and fails unless
  `scripts/check_image_harfbuzz_subset.py` finds the HarfBuzz path live. This is the gap
  [#1266](https://github.com/arunakulat/dutchbay-epc-model/pull/1266) deferred rather than loaded
  onto a one-package change.
- What the gate proved before: that `libharfbuzz-subset0` **resolves and installs** on bookworm.
  That is a fact about the build host's package index, not about the runtime stage. It did not
  prove the loader finds the library **at run time** -- from a different stage, under the non-root
  account, with the venv's interpreter -- and nothing else could, because WeasyPrint 70.0 `dlopen`s
  the library with `allow_fail=True`. Absent, it does not fail: it warns once, subsets every face
  with fontTools on its own deprecated path, and keeps emitting valid PDFs. `/health` renders no
  PDF, so the boot check could not see it either.
- Four checks, each with its own receipt: `weasyprint.text.ffi.harfbuzz_subset` is not `None`;
  a subset symbol called through that handle returns a live object (the handle binds the ABI, not
  merely a file that opened); `hb_version_atleast(4, 1, 0)`, the other half of the gate in
  `Font.subset`; and a real `write_pdf()` that reaches `Font.subset` with glyphs and logs neither
  the fontTools fallback nor an `Unable to subset` failure. The first three say the path is
  **available**; the fourth says it was **taken**.
- The fourth check counts `Font.subset` calls as well as reading the log. `Font.subset` returns
  early on an empty glyph set, so a render that embedded no font would log no warning and let a
  warnings-only check pass while proving nothing. Both halves were exercised against WeasyPrint
  70.0 on a host with and without `libharfbuzz-subset0`: the check passes only with the library
  present, fails on check 1 without it, and its fourth check fires on a forced fallback.
- The script is piped into the image over stdin rather than executed from it, so the gate does not
  depend on `.dockerignore` continuing to ship `scripts/` into the runtime layer.

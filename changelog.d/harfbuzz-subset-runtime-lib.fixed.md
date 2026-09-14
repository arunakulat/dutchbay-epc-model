- Add `libharfbuzz-subset0` to the image's WeasyPrint runtime library set. WeasyPrint 70.0 asks for
  it by name at import and warns that the library "will be required by future versions"; without it
  it falls back to a coarser font subsetter. That makes this a live difference in the deliverable
  rather than a quieter log — verified on one document, same version, same fonts: 2254 bytes and the
  warning present without the library, 2234 bytes and no warning with it. The Dockerfile comment
  calls its list "the exact bookworm set", so the omission was a claim as well as a gap. Nothing is
  broken today, and this is not a security fix: 70.0 renders correctly without the library and the
  structural markers DBPL-01 governs (PDF/UA marking, `/StructTreeRoot`, `/Lang`, page geometry,
  embedded subsets) were confirmed unchanged when the pin moved to 70.0. It is taken now because the
  warning is a deprecation notice, and the version that removes the fallback would otherwise land as
  a surprise on whoever runs the next bump, on the lender-facing PDF path.
- Because subsetting changes, the byte-identical-output expectation for DBPL PDFs does not survive
  this commit either: a PDF rendered by the image after this change will differ from one rendered
  before it. Structure, tagging and page geometry are what DBPL-01 pins, and those are unaffected.

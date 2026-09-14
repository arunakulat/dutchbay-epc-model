- Stop `app/reports/grid_screening_emit.py` describing its `[grid]` pin provenance as metadata. It
  resolves through `app.ops.extras.declared_extras`, which #1263 changed to read the governing
  `pyproject.toml` first and the installed distribution's metadata only behind it -- and metadata
  is specifically *not* authoritative any more, because it describes whichever tree last built it
  rather than the tree executing. Four claims in this module said otherwise: the fallback constant
  called metadata "AUTHORITATIVE", `_grid_extra_pins`'s summary said it "prefer[s] the installed
  distribution's own recorded metadata", its CASPER note said an uninstalled source tree "has no
  metadata to read" (it has the pyproject that answers), and `GRID_EXTRA_PINS` said it resolved
  "from metadata (authoritative)". Verified live: `probe_extra("grid").spec_source` is `pyproject`.
- The same staleness had spread to the controls' own names. `..._are_read_from_distribution_metadata`
  and `..._fallback_matches_declared_metadata` assert against `declared_extras`, which no longer
  means metadata; `..._degrade_to_the_fallback_without_metadata` documents an uninstalled checkout
  as the degradation trigger, which stopped being one. Renamed to say what they check. Their skip
  reason -- "project not installed as distribution metadata" -- named a condition that can no longer
  arise in a checkout, so it is now "no `[grid]` extra in pyproject or in distribution metadata".
- Correct the rationale for comparing specifier clause *sets* rather than strings. It said "metadata
  normalises their order", which is true only of the path that now answers second; pyproject returns
  its own text verbatim. The set comparison is still right, and now for the stated reason: the same
  pin reads `>=70,<71` from pyproject and `<71,>=70` from metadata, so a string compare would pass
  or fail on which artifact answered.
- Fix a citation that pointed nowhere. The fallback constant credited
  `test_grid_extra_pins_match_declared_metadata` with holding it to the declared value. No such name
  has ever existed -- the control is real but spelled differently -- so a reader following the
  reference to check the claim found nothing. Added a control that derives both sides (citations by
  scanning the module's source, definitions from pytest-collectable module functions and `Test*`
  class methods) and fails when a cited name is only nested, belongs to a non-collected class, or is
  misspelled.
- Add typed source and resolution-status provenance to the grid report and render it structurally.
  A complete declaration records `pyproject` or `metadata`; a genuinely absent declaration is
  labelled `static_fallback`. Resolution exceptions, malformed requirements, duplicate normalized
  names and partial dependency sets now fail loudly instead of appearing as resolved provenance.
- Read the declarations and their source through one atomic `ExtraDeclarations` observation, so a
  source-tree change between two lookups cannot relabel one artifact's dependency values as the
  other's. An explicit empty `[grid]` declaration is rejected as partial rather than treated as an
  absent declaration. PEP 508 extras, markers and direct URLs are rejected rather than stripped
  from the lender-facing representation. Production parsing now uses the declared runtime
  `packaging.Requirement` implementation, so valid PEP 508 whitespace is normalized and accepted
  rather than falsely classified as malformed.
- Preserve complete PEP 508 markers from pyproject. Installed metadata now removes only a marker
  whose entire expression is one `extra == ...` association; conjunctive, repeated, disjunctive and
  nested selectors remain complete on the declaration and therefore fail the strict lender
  resolver instead of being simplified. Unsupported `extra` operators produce a retained
  resolution diagnostic. A present-but-falsy non-table `project.optional-dependencies` value is
  malformed, never equivalent to an absent declaration. The atomic observation is deeply immutable
  and distinguishes a missing or foreign pyproject from present-but-malformed/unreadable input.
  Health probes retain their degrade behavior, while the lender-facing resolver fails loudly on
  that diagnostic.
- Strengthen the fallback drift oracle: it parses the governing `pyproject.toml` directly with TOML
  and PEP 508 tooling, rejects duplicates and malformed declarations, and compares the complete
  bidirectional normalized name/specifier mapping. A hostile declaration-only dependency is a
  negative control. This is provenance-only and changes no finance or project KPI.

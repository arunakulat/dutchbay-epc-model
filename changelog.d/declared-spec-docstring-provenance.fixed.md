- Correct `app.ops.extras.PackageStatus.declared_spec`'s field docstring, which still said the
  specifier comes "verbatim from metadata". That stopped being true when the pins began to be read
  from the governing `pyproject.toml` first and metadata only as the fallback: the module docstring
  and `declared_extras` were both updated then, and this one field description was not. It is the
  field that carries a declared pin inside the module rewritten to fix a provenance bug, so a stale
  provenance claim on it is worth more than its size. The docstring now names both possible sources
  and points at `ExtraStatus.spec_source`, which is where the answer actually lives. It also spells
  out what "verbatim" costs a caller: the two sources render one pin as two different strings
  (`>=70,<71` from `pyproject.toml`, `<71,>=70` once metadata has round-tripped it), so testing this
  field against a literal needs a `SpecifierSet`, not a string compare. The stale `<70,>=69` example
  is replaced by both real forms rather than by one of them, since naming a single form would have
  reintroduced the same provenance mismatch the change exists to remove. No behaviour change -- this
  is the prose catching up with the code.

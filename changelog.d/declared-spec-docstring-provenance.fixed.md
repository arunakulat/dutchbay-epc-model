- Correct `app.ops.extras.PackageStatus.declared_spec`'s field docstring, which still said the
  specifier comes "verbatim from metadata". That stopped being true when the pins began to be read
  from the governing `pyproject.toml` first and metadata only as the fallback: the module docstring
  and `declared_extras` were both updated then, and this one field description was not. It is the
  field that carries a declared pin inside the module rewritten to fix a provenance bug, so a stale
  provenance claim on it is worth more than its size. The docstring now names both possible sources
  and points at `ExtraStatus.spec_source`, which is where the answer actually lives; the illustrative
  specifier is also brought to `<71,>=70`, since `<70,>=69` no longer describes anything the project
  declares. No behaviour change -- this is the prose catching up with the code.

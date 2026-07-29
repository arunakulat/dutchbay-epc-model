- **Forward-compat with newer type stubs (#992 dependency group)** — the weekly group's
  `types-requests` and `pandas-stubs` bumps tightened two signatures and tripped the mypy
  gate. Annotated the NASA POWER request `params` as `dict[str, str | float]` (the exact
  `SupportsItems[...]` shape `requests` accepts) and widened the DSCR zero→NA replacement
  value to `Any` so `pandas-stubs` accepts the `NAType`. Typing-only: runtime is
  byte-identical, and mypy stays clean under both the current and bumped stubs.

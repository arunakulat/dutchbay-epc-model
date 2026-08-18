- **`docs/MODULE_REFERENCE.md` pointed at the wrong path for the local CI
  orchestrator** — it listed `go_with_the_flow_ci.py` among the `scripts/ci/`
  guards and gave its path as `scripts/ci/go_with_the_flow_ci.py`. The file is
  and has always been at `scripts/go_with_the_flow_ci.py`; nothing was ever
  committed under `scripts/ci/` by that name. Corrected in both places. The
  module's description was verified against the file and is unchanged.

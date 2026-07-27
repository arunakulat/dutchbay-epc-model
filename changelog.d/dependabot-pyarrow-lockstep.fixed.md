- **Dependabot: freeze `pyarrow` against major bumps (#983 post-mortem)** — `streamlit 1.60.0`
  requires `pyarrow<25`, so the weekly group's `pyarrow 24→25` bump (landing alongside the
  `streamlit 1.60` bump) produced an internally contradictory, un-installable lock
  (`ResolutionImpossible`: `pyarrow==25.0.0` vs streamlit's `pyarrow<25`) — #983 was closed
  un-installable, mirroring #978. `pyarrow` now ignores semver-major bumps (24.x patches stay
  welcome) and lifts only in lockstep with a streamlit release that raises the ceiling.
  Extends the grouped-bump lockstep guardrails from #977/#978/#980.

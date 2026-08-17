- **`feasibility` extra — the reproduce kit installs in one line** — `pip install -e
  ".[dev,feasibility]"` now provides everything `feasibility_reproduce/run_all.sh` needs,
  replacing the hand-typed dependency list in `HOWTO.md` §0. Composes `wind`,
  `micrositing`, `gis` and `report`, and adds `mistune` (Markdown→HTML for the PDF
  builders) and `SALib` (the global-sensitivity step, which otherwise only arrived via
  `[dev]`).
- **`[grid]` is deliberately excluded from `feasibility`, resolving a real lock conflict** —
  pandapower's scipy pin is incompatible with the pinned lock on *every* supported
  interpreter: `pandapower==3.3.0` requires `scipy~=1.15`, and 3.5.4 requires `scipy<1.17`
  on Python 3.11 and `scipy~=1.18` on 3.12, while `requirements.txt` pins `scipy==1.17.1`
  and `[dev]`'s `scipy-stubs` requires `scipy>=1.17.1`. Installing grid alongside dev
  silently downgraded scipy off the lock **and** broke the mypy gate's stubs. The grid
  screen is advisory and KPI-neutral, so `run_all.sh` step 7 now skips it with a pointer to
  an isolated `.venv-grid` rather than corrupting the environment that produces the
  committed numbers. Verified in a clean venv: `requirements.txt` + `.[dev,feasibility]`
  holds scipy at 1.17.1 with every kit dependency present. The canonical KPIs are
  unaffected either way — the canon reproduces byte-identically under scipy 1.16.3 and
  1.17.1 (#1040).
- **Kit helper scripts committed — `run_all.sh` is closer to genuinely one-shot** — steps
  2, 4, 5 and 10 called `feasibility_reproduce/lib/*.py` files that were never committed
  (the unanchored `.gitignore` `lib/` rule swallowed them until #1040). Added `mc_run.py`
  (wraps the canonical MC CLI, distils the committed summary shape, and REFUSES to emit a
  summary when `toy_fallback_count > 0` so fabricated trial KPIs can never be presented as
  evidence), `wind_provenance.py` (fresh bankable AEP + AEP tornado, both pure functions of
  the committed scenario) and `run_global_sa.py` (drives Morris/Sobol/PAWN through
  `scripts/run_global_sensitivity.py`, with a `--quick` smoke mode explicitly marked
  not-evidence-grade), alongside the two PDF builders from #1040.
- **Micro-siting stays skipped, loudly, rather than fabricated** — `optimize_layout()` needs
  a site boundary polygon and baseline turbine coordinates, and neither is committed
  anywhere in the tree; the pinned `cache/expected/layout_optimized.json` came from geometry
  that was never checked in. `wind_provenance.py` reports exactly that instead of inventing
  a boundary, which would yield an authoritative-looking uplift that is not the project's.
  Micro-siting is KPI-neutral, so the finance canon does not depend on it.
- **SessionStart hook for Claude Code on the web** — `.claude/hooks/session-start.sh`
  provisions `.venv` with the pinned lock plus the `[dev]` gate toolchain so a remote
  session can run tests and linters immediately, and puts `.venv/bin` on `PATH` via
  `CLAUDE_ENV_FILE`. Remote-only (local sessions keep `make setup`), idempotent via a
  manifest-hash stamp, and it creates a real venv because a system-interpreter install hits
  Debian's patched-setuptools `install_layout` failure on the lock's legacy sdists
  (`antlr4-python3-runtime`, `odfpy`). The heavy `[feasibility]` extra is opt-in behind
  `DUTCHBAY_INSTALL_FEASIBILITY=1` so it is not paid for on every session start.

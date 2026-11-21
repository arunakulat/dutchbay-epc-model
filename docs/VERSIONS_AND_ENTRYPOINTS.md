# Versions and supported entrypoints: product 15.x and the v14 contracts

Status: **reference** (#1426, roadmap milestone P2.1 in
[`CAPABILITY_AND_ASSURANCE_ROADMAP_2026-10-11.md`](CAPABILITY_AND_ASSURANCE_ROADMAP_2026-10-11.md)).
Written against `main` `4cfed491` (`VERSION` 15.28.0). It explains names and routes only. It
changes no code, no KPI, no release and no `HOLD`.

## Two numbering systems, which mean different things

A reader meets two numbers in this repository: a **15.x** number and a **v14** label. They are
not two versions of the same thing.

| What you see | What it is | Where it lives | What it is not |
|---|---|---|---|
| `15.28.0` | The **product version** of the code on `main`. It moves with every change to committed financial behaviour (`CLAUDE.md`, the changelog format; `DOC-02`). | `VERSION` (the single source) and `pyproject.toml` `[project].version` | Not a published release. A version number on `main` is not a release until a signed `v*` tag is pushed and `release-run.yml` publishes it. |
| `v15.6.1` | The **latest published release** (tag `v15.6.1`, 2026-10-04, `CHANGELOG.md`). | Git tag and GitHub Release | Not cleared for Board or lender circulation. #1110 is open with its circulation `HOLD`, and the F-5 bar (no quarterly CFADS or intra-year DSCR figure supports a lender representation) also stands. Later product versions on `main` carry the same holds. |
| `v14` in a file or function name (`run_full_pipeline_v14.py`, `run_v14_pipeline`, `contracts_v14`) | The **contract and pipeline generation**: the hardened execution path and its result contracts. | Module, script and function names | Not a product version. The 15.x product runs on the v14 contracts. A name ending `_v14` is not "older than 15". |
| `manifest_schema_version`, `*_SCHEMA_VERSION` | The **schema version of one output document**. | For example `analytics/run_manifest.py` (`MANIFEST_SCHEMA_VERSION`), `analytics/aep_reconciliation.py`, `analytics/wind/wind_bess_options.py` | Not tied to either number above. Each schema moves only when its own document's shape changes. |

So "15.28.0 on the v14 contracts" is a complete, consistent description of `main` today. A
change of the product version does not by itself rename or re-version any v14 contract.

## Supported entrypoints

Pick by what you need. Each line is the supported route; everything else in the tree is an
internal module, a single-purpose analysis script, or frozen tooling.

| Need | Supported entrypoint | Notes |
|---|---|---|
| One scenario's authoritative lender-grade economics | `python run_full_pipeline_v14.py config=<scenario.yaml>` (Hydra; `conf/run_full_pipeline_v14.yaml`) | Canonical single-scenario route. Hydra `key=value` syntax, not `--flags`. |
| The same pipeline from Python | `analytics.pipeline_v14_enhanced.run_v14_pipeline` | An alias of `run_v14_pipeline_enhanced`; the canonical orchestrator ([`ARCHITECTURE.md`](ARCHITECTURE.md)). |
| Evaluate a scenario with overrides (sensitivity, Monte Carlo, optimisation callers) | `analytics.evaluation_v14.evaluate_with_overrides` | The single evaluation gateway. Do not import evaluation internals directly (`AGENTS.md`). |
| Rank or compare several scenarios | `python run_scenario_analytics_v14.py` (Hydra; `conf/run_scenario_analytics_v14.yaml`) | Deliberately lighter batch path on a snapshot basis. For one scenario's authoritative figures use the single-scenario route ([`ARCHITECTURE.md`](ARCHITECTURE.md), "Canonical execution map"). |
| Result types | `analytics.contracts_v14` (`ScenarioResult`, `WaccResult`, ...) | The canonical result contracts. |
| IRR, XIRR and NPV | `finance.irr` | Defined only there; consumers import them. |
| Wind resource to AEP (producer) | `python scripts/run_wind_analysis_v14.py location=<site>` (Hydra; `conf/wind_analysis.yaml`; `location` is required and names an entry in `wind_resource/config/locations.yaml`) | Writes the frozen wind export that the finance pipeline reads. Downloads ERA5 data unless it is already cached, so a first run needs Copernicus CDS credentials. The wind-to-finance bridge is a narrow frozen-export contract ([`ARCHITECTURE.md`](ARCHITECTURE.md), "Wind → finance integration"). |
| Grid interconnection screening | `analytics/grid/` (opt-in `[grid]`) | Advisory and design-stage only, default off ([`GRID_INTERFACE_SCHEMA.md`](GRID_INTERFACE_SCHEMA.md)). |
| Web service and lender report | `app/` (FastAPI, async jobs, `app/reports/`) | `api/` holds the pipeline and sensitivity routers that `app/api/main.py` mounts under `/v1` and `/v1/sensitivity`, and `app/reports/` imports from it. It is live code inside the web service, not a separate entrypoint. |

Other `scripts/*_v14.py` files are single-purpose analysis CLIs, each run from its own Hydra
config under `conf/` (`scripts/FINAL_CORRECTED_sensitivity_v14.py` is a comment stub, not a CLI). They are supported for their own analysis, not as alternative routes to
the lender case.

Frozen tooling: legacy Typer and Click tools are tolerated but frozen and must not be extended
(`CLI-01`). New canonical CLIs use Hydra and emit JSON first; `argparse` is banned.

## Canonical imports are not renamed without a migration case

The `_v14` names above are load-bearing. Tests, historical run manifests, review records and
external notes cite them, and a manifest written by an earlier run must stay interpretable.
So:

- A canonical import path or entrypoint is **not renamed** (for example to `_v15`, or to drop
  the suffix) without a migration case: the consumers it breaks, the compatibility alias it
  keeps and for how long, and the condition that removes the alias.
- Before any rename, inventory the genuinely duplicate APIs and frozen-export routes with their
  consumers and removal conditions (roadmap P2.1).
- A naming-only or documentation change is **not** a v15 model migration and must not be
  described as one.

The pattern already in use is the one to follow: `run_v14_pipeline` is kept as an alias of
`run_v14_pipeline_enhanced`, and the legacy wind-only `analytics/pipeline_v14.py` was retired
only after every caller had moved (#286, #456; [`ARCHITECTURE.md`](ARCHITECTURE.md)).

## Where to read more

- [`ARCHITECTURE.md`](ARCHITECTURE.md): canonical execution map, pipeline sequence, package
  import graph.
- [`PIPELINE_ARCHITECTURE.md`](PIPELINE_ARCHITECTURE.md): pipeline and technical design.
- [`../RELEASING.md`](../RELEASING.md): how a product version becomes a published release.
- [`../CHANGELOG.md`](../CHANGELOG.md): what each product version changed.

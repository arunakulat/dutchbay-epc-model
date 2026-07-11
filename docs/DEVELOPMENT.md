# Development Guide

This guide covers local setup, the quality gates, the contribution workflow, and the
governance rules that apply to every change. It is the single entry point for a developer
working on the DutchBay EPC model. For a five-minute orientation see
[QUICK_START.md](../QUICK_START.md); for the release process see
[RELEASING.md](../RELEASING.md); for deployment see [docs/deploy/DEPLOY.md](deploy/DEPLOY.md).

## Prerequisites

- Python 3.11 (the project requires `>=3.11`; the pinned toolchain and CI run 3.11 and 3.12).
- Git.
- A POSIX shell. macOS, Linux, or Windows with WSL are supported.
- Optional system libraries only for specific extras (for example pango/cairo for the
  WeasyPrint PDF report in `[report]`). The base install needs none of them.

## Setup

The repository ships a `Makefile` target that installs the pinned reproducibility lock plus
the development and CI toolchain:

```bash
git clone https://github.com/arunakulat/dutchbay-epc-model.git
cd dutchbay-epc-model

python3.11 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

make setup                           # pip install -r requirements.txt + pip install -e ".[dev]"
```

`make setup` is the canonical bootstrap. The equivalent manual steps are:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt      # the pinned reproducibility lock CI installs
pip install -e ".[dev]"              # the dev/CI toolchain from pyproject (the abstract source of truth)
```

`requirements.txt` is the single pinned lock; `pyproject.toml` is the abstract source of
truth for the core dependencies and the optional extras. There is no `requirements_dev.txt`
(retired in favour of the `[dev]` extra).

### Optional install extras

The base install runs the finance engine and the Hydra CLI with no heavy scientific stack.
Each capability below is an opt-in extra whose imports are guarded so that a missing extra
fails at call time with an actionable message, never at import time (the CASPER pattern).

| Extra | Powers |
| --- | --- |
| `[dev]` | The full CI gate (ruff, black, isort, mypy and stubs, bandit, pip-audit, pytest stack, hypothesis, libcst, build) |
| `[api]` | The HTTP API (`api/`, `app/`) |
| `[dashboard]` | The Streamlit sensitivity dashboard |
| `[wind]` | The ERA5 to bankable-AEP wind pipeline |
| `[micrositing]` | The DTU TopFarm layout optimizer |
| `[solar]` | The pvlib solar producer for hybrid multi-tech |
| `[pareto]` | NSGA-II multi-objective search (pymoo) |
| `[gis]` | The GIS-for-wind raster/vector siting toolchain |
| `[report]` | The PDF lender report (WeasyPrint) and location/context maps |
| `[jobs]` | The durable cross-process async job worker (arq, Redis) |
| `[grid]` | The grid interconnection screening study (pandapower, ANDES, OpenDSS) |

The `[grid]` extra pins `pandapower==3.3.0` exactly and must be installed under the
constraints file so the core numeric pins are not downgraded:

```bash
PIP_CONSTRAINT=constraints.txt pip install -e ".[grid]"
```

## Running the model

All command-line entry points use Hydra: overrides are `key=value`, not `--flags`.

```bash
# Canonical single-scenario lender pipeline
python run_full_pipeline_v14.py config=scenarios/dutchbay_lendercase_2025Q4.yaml

# Monte Carlo (deterministic with an explicit seed)
python -m analytics.cli.cli_monte_carlo_hydra \
  config=scenarios/dutchbay_lendercase_2025Q4.yaml n_trials=200 seed=42

# Sensitivity tornado
python -m analytics.cli.cli_sensitivity_hydra \
  config=scenarios/dutchbay_lendercase_2025Q4.yaml output_dir=_out/sensitivity
```

Run the `analytics/cli/*` entry points with `python -m` so the `analytics` package is
importable. The Python API entry point is the evaluation gateway:

```python
from analytics.evaluation_v14 import evaluate_with_overrides

kpis = evaluate_with_overrides("scenarios/dutchbay_lendercase_2025Q4.yaml")
print(kpis["project_irr"], kpis["min_dscr"])
```

To run the web service locally, see the Docker Compose section of
[docs/deploy/DEPLOY.md](deploy/DEPLOY.md).

## Quality gates

The `Makefile` mirrors the gates CI runs. Run them before pushing.

| Command | What it does |
| --- | --- |
| `make lint` | `ruff check .` (mandatory), plus `black --check` and `isort --check-only` (advisory locally) |
| `make type` | Strict, complete-annotation `mypy` over the engine surface and entry points |
| `make security` | `bandit` SAST (fail on medium severity/confidence) and `pip-audit` of the pinned lock |
| `make test` | `pytest -n auto` with the coverage floor `--cov-fail-under=95` over the six engine packages |
| `make cov` | The test run with a terminal coverage report but no floor |
| `make html` | The test run with an HTML coverage report at `htmlcov/index.html` |

Notes:

- **Coverage** is gated at 95% over `finance`, `analytics`, `wind_resource`, `api`, `app`,
  and `solar_resource` (`.coveragerc`). The floor is enforced in `make test` and in the CI
  test step, not in `pyproject.toml` `addopts`, so a partial local run
  (`pytest tests/foo.py`) does not spuriously trip it.
- **Type checking** runs with the full type-stub set (`pandas-stubs`, `scipy-stubs`, and
  others); the gate is only faithful with them installed, which `[dev]` provides.
- **Security** runs with an empty `pip-audit` allowlist: the pinned lock is expected to be
  free of non-allowlisted advisories.

### Pre-commit hooks

Install the hooks once; they then run on every commit (black, ruff, isort, mypy, and file
hygiene checks, plus a `no-commit-to-branch` guard that blocks commits on `main`):

```bash
pre-commit install
pre-commit run --all-files      # run the whole hook set on demand
```

## Testing

The full suite is large (several thousand tests). Common invocations:

```bash
pytest tests/                                   # full suite
pytest tests/finance/ tests/integration/ -q     # a focused subset
pytest -m "not slow"                             # deselect the slow-marked tests
```

The canonical result is protected by a single end-to-end oracle that runs the real pipeline
on the lender case and pins the eight canonical KPIs at `1e-9`:

```bash
pytest tests/finance/test_multitech_generation.py::test_canonical_lendercase_economics_unchanged -q
```

Any change intended to be result-neutral must leave this test passing unchanged. Structural
rules (IRR/NPV isolation, the contract gateway, the Hydra-only entry-point policy, the ban
on argparse) are enforced by LibCST lint tests under `tests/lint/`.

## Contribution workflow

Every change follows branch to pull request to green CI to self-merge. Never commit directly
to `main`.

1. Create a feature branch from the latest `main`: `git switch -c feature/short-description origin/main`.
2. Confirm the active branch before committing: `git branch --show-current` (a `checkout -b`
   success message is not proof the switch took effect).
3. Make the change; keep each branch to one small, complete, independently revertable unit of
   work.
4. Run the gates locally until green: `make lint type security test`.
5. Add a changelog fragment under `changelog.d/` (see below) rather than editing
   `CHANGELOG.md` directly.
6. Push and open a pull request; wait for required CI to pass before merging.
7. After merge, delete the branch and sync `main`.

### Changelog

`CHANGELOG.md` is not edited by hand. Drop a per-change fragment in `changelog.d/`
(see `changelog.d/README.md` for the naming convention) and let the release process fold it
in:

```bash
python scripts/compile_changelog.py --check    # show pending fragments
python scripts/compile_changelog.py            # fold changelog.d/*.md into [Unreleased]
```

### Concurrency and worktrees

When more than one agent or session mutates the working tree at the same time (for example a
background review running alongside hands-on edits), each writer must work in its own git
worktree, never in a shared clone:

```bash
git worktree add -b feature/short-description ../dutchbay-wt-feature origin/main
```

A branch is checked out in exactly one worktree, so two writers cannot commit to the same
branch, and edits cannot collide on a shared index or HEAD.

## Continuous integration

The CI gate topology is:

- **Fast lane** — `ruff` and `mypy` over the v14 entry point, for fast feedback.
- **Regression smoke** — a required smoke check over the CLI and core analytics.
- **Test suite** — the full suite split into six time-balanced shards
  (`pytest-split`), each run with `pytest -n auto`, combined into a single 95% coverage gate,
  plus mandatory `ruff`/`black`/`isort`/`mypy` and `bandit`/`pip-audit` gates.
- **Docker build** — builds the runtime image and boots it to check `/health` (it does not
  push the image; deployment is manual, see [docs/deploy/DEPLOY.md](deploy/DEPLOY.md)).

Pull-request runs currently exercise Python 3.12 and pushes to `main` exercise 3.11.

## Governance

Development is governed by the "Go With The Flow" ruleset (GWTF v3.0, 64 rules) in
[go_with_the_flow_rules_v3_0_clean.csv](../go_with_the_flow_rules_v3_0_clean.csv). The rules
most relevant day to day:

- **Config first.** All scenario parameters and business values live in YAML
  (`conf/*.yaml`, `scenarios/*.yaml`, `config/defaults.yaml`), validated by the strict schema
  guard. `constants.py` holds only universal physical constants.
- **IRR, NPV, and WACC isolation.** These are defined only in `finance/irr.py` and
  `finance/wacc_v14.py`; other modules import them.
- **The contract gateway.** Analytics modules consume result types from `analytics/contracts_v14.py`
  and evaluate only through `analytics.evaluation_v14.evaluate_with_overrides`.
- **Never commit to `main`.** Branch, open a pull request, pass CI, then self-merge.
- **Incremental delivery.** Ship small, complete, independently revertable changes rather than
  one large change.

## Troubleshooting

- Confirm the interpreter is the project venv (`which python` should resolve inside `.venv`)
  and that it is Python 3.11+.
- If an optional capability raises an import error at call time, install its extra (the error
  message names the exact `pip install` command).
- If a commit is rejected on `main`, you are on the wrong branch; create a feature branch and
  move the work to it.

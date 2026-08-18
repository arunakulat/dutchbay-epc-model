# Environment provisioning — venv, extras, locks

How a working environment is built, what each extra buys, and where the pinned
lock and the optional extras disagree. Current as of **v15.4.0**.

Canonical bootstrap remains `make setup` / `setup_venv.sh`; this document explains
what those produce and how to go beyond them.

---

## 1. Baseline

**Python 3.12** (`requires-python = ">=3.12"`). 3.11 is no longer supported and the
CI matrix is a single 3.12 leg.

The move was forced, not preferred: flipping `grid.qsts.finance_wiring.enabled`
(#923) makes pandapower a runtime dependency of the canonical path, and on 3.11 no
assignment satisfied both pandapower and the pinned scipy. See §5.1.

```bash
python3.12 -m venv .venv
.venv/bin/pip install --upgrade pip setuptools wheel
.venv/bin/pip install -r requirements.txt      # the pinned lock
.venv/bin/pip install -e ".[dev]"              # gate toolchain
```

> **Always build a real venv.** A `pip install` into the system interpreter hits
> Debian's patched setuptools (`AttributeError: install_layout`) building the
> lock's legacy sdists — `antlr4-python3-runtime`, `odfpy` — and fails the whole
> install. A fresh venv ships clean build tooling.

---

## 2. What the lock contains

`requirements.txt` is a fully-pinned reproducibility lock. `make lock` installs
the cleared lock first, then resolves the complete abstract capability set from
pyproject under the policy constraints. This prevents an additive dependency
dolphin from silently refreshing unrelated packages inside broad version ranges:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
make lock PIP=.venv/bin/pip
```

**CI installs the lock and nothing else.** That is the single most important fact
about this file — see §4.

| Extra | In the lock? | Buys |
|---|---|---|
| `dev` / `test` | ✅ | ruff, black, isort, mypy + stubs, pytest + xdist/cov/split, bandit, pip-audit |
| `api` / `dashboard` | ✅ | FastAPI/uvicorn, Streamlit |
| `wind` | ✅ | cdsapi, xarray, netCDF4, windpowerlib, PyWake |
| `gis` | ✅ | rasterio, shapely, **pyproj** |
| `grid` | ✅ | pandapower, andes, opendssdirect |
| `micrositing` | ✅ (v15.4.0) | TopFarm |
| `ingestion` | ✅ | MarkItDown with PDF support, pdfplumber, PyMuPDF |
| `report` | ❌ | WeasyPrint, reportlab, geopandas, contextily |
| `solar` | ❌ | pvlib |
| `jobs` | ❌ | arq, redis |
| `pareto` | ❌ | pymoo |
| `feasibility` | ❌ (composite) | `wind,micrositing,gis,report,grid` + mistune + SALib |

**BESS needs no extra.** `finance.bess_revenue`, `finance.bess_lcos`,
`finance.bess_project_economics` and `analytics.grid.capabilities.bess_soc` are
core and always available.

---

## 3. Provisioning a session

The SessionStart hook (`.claude/hooks/session-start.sh`) provisions remote
sessions. It is remote-only and idempotent via a manifest+extras hash stamp.

**A web session provisions FULLY and automatically — no flag to remember.**
`DUTCHBAY_EXTRAS` is supplied by the `env` block in `.claude/settings.json`, which
the harness injects before the hook runs:

```json
{ "env": { "DUTCHBAY_EXTRAS": "dev,feasibility,jobs,solar,pareto" } }
```

The hook's own fallback is the **same full set**, not a bare `dev`. Relying on the
env alone would mean a silently under-provisioned session if injection ever failed
— and that fails LATE (a missing import halfway through a run) rather than loudly
at start. Both paths are verified.

| `DUTCHBAY_EXTRAS` | Result |
|---|---|
| unset → full set (fallback) | everything; redis started |
| `dev,feasibility,jobs,solar,pareto` | everything; redis started |
| `dev,feasibility` | the reproduce kit, no job path |
| `dev` | tests + linters only (explicit fast path) |

Redis is started only when `jobs` is among the extras, and never fatally — the
async job path is opt-in and must not break session start. The `redis-server`
binary ships in the image.

Cost of the full default: roughly a gigabyte (JAX/numba/openmdao/jupyterlab via
TopFarm) and a few minutes at session start. Paid deliberately — this repo's work
needs grid, micro-siting and the job path far more often than it needs a fast
start, and a half-provisioned environment is the more expensive failure.

The container is **ephemeral**: the venv does not survive it. The hook is the
recipe that makes the environment reproducible rather than persistent — do not try
to persist a venv, and never commit one (`.venv` is correctly gitignored).

---

## 4. Where the lock and the extras disagree

Three times in one release cycle an optional extra quietly contradicted the lock.
Each was found the hard way; they are recorded so the next one is found faster.

### 4.1 pandapower vs scipy — resolved by the 3.12 migration

| | scipy required |
|---|---|
| `pandapower==3.3.0` (pre-v15.4.0 `[grid]` pin) | `~=1.15` |
| `pandapower 3.5.4` on Python 3.11 | `<1.17` |
| `pandapower 3.5.x` on Python 3.12 | `~=1.18` |

The lock pinned `scipy==1.17.1` and `[dev]`'s `scipy-stubs` required `>=1.17.1`, so
on 3.11 installing grid alongside dev silently downgraded scipy off the lock **and**
broke the mypy gate's stubs. Resolved by moving to 3.12 and pinning
`scipy==1.18.0` + `scipy-stubs==1.18.0.1`.

### 4.2 pyproj — declared in no extra at all

`pyproj` reached development venvs only transitively via topfarm. Because the lock
was built without micrositing, CI never received it, so geometry work passed
locally and failed on six CI shards. Now declared in `[gis]` (rasterio/shapely work
*is* projection work) and pinned in the lock.

### 4.3 protobuf — accepted downgrade

Adding `[micrositing]` pulls topfarm → optiwindnet → **ortools**, which caps
`protobuf<6.34`. The lock therefore moves `protobuf` 7.35.1 → **6.33.6**.

Accepted deliberately: 6.33.6 satisfies every consumer in the tree
(`ortools <6.34,>=6.33.1`; `streamlit <8,>=5.26.1`; `esy-osm-pbf >=3.20`) and no
first-party module imports protobuf — it is purely transitive. Pinning it in the
lock is strictly better than the previous state, where installing micrositing on
top of the lock produced a live resolver conflict.

### The rule this yields

> **A dev venv is not the CI environment.** `[dev,feasibility]` drags in packages
> CI never receives. Validate anything dependency-sensitive in a venv built from
> the **lock alone** before pushing:
> ```bash
> python3.12 -m venv /tmp/ci && /tmp/ci/bin/pip install -r requirements.txt \
>   && /tmp/ci/bin/pip install -e . && /tmp/ci/bin/python -m pytest -q
> ```

---

## 5. What CI still skips

With the v15.4.0 lock, **13** tests skip on a CI run (down from 23), verified against
a venv built from the lock alone: 5184 passed, 13 skipped, 0 failed.

Ten are honest guards that declare a missing optional dependency:

| Missing | Extra | Skips |
|---|---|---|
| `pvlib` | `solar` | 5 |
| `weasyprint` | `report` | 2 |
| `reportlab` | `report` | 1 |
| `arq` | `jobs` | 1 |
| `pymoo` | `pareto` | 1 |

Plus three that are correct by construction:

- `test_self_curtailment_enablement_readiness.py:147` — skips *because* `[grid]` is
  installed; it tests the absent-dependency guard, now unreachable. This skip is
  evidence the migration worked.
- `test_mc_exports.py:293` — "requires pandas to be missing" (inverse guard).
- `test_fx_sensitivity_real.py:409` — requires a real scenario file and pipeline.

**Closed in v15.4.0:** the 9 `test_layout_optimizer.py` cases (TopFarm now in the
lock — that is the suite for `optimize_layout()`, which the synthetic micro-siting
work drives) and `test_evaluation_v14_lender_stack.py:58`, whose fixture
`tests/data/minimal_lender_scenario.yaml` had never been committed, leaving the
file's self-described PRIMARY regression pin silently skipping on every run.

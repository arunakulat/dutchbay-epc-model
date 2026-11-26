# Dependency Holds Survey & Expiry Governance (#1414)

**Work item:** #1414 (tracker: #1353; related: #1169, #1388)
**Observed baseline:** `origin/main` `1c45d3bb5e2c5baecaebcc5e6de75d443d32bcdf` (`2026-11-25`)
**Status:** Survey and decisions recorded; any lock/workflow change is scoped as its own follow-up issue.

---

## 1. Survey of `.github/dependabot.yml` `ignore` entries

| Package | Ignored update types | Owner | Rationale / Cap | Lift condition |
|---|---|---|---|---|
| `pandas` | `semver-major` | Finance engine | Copy-on-Write / `str` dtype breaking changes (`<3`) | Deliberate KPI-oracle-verified pandas 3.0 migration (#593) |
| `pandas-stubs` | `semver-major` | Typed surface | Must stay aligned with `pandas<3` | Lockstep with pandas 3.0 migration (#593) |
| `numpy` | `semver-major`, `semver-minor` | Grid & numerics | `pandapower 3.5.4` requires `numpy<2.5,>=1.26` (#1169) | `pandapower` release lifting `<2.5`, moved in lockstep with `numpy-typing-compat` |
| `numpy-typing-compat` | `semver-major`, `semver-minor`, `semver-patch` | Grid & numerics | Patch segment encodes numpy floor (`20260602.2.4` -> `<2.5`) | Lockstep with `numpy` / `pandapower` lift (#1169) |
| `mpmath` | `semver-major`, `semver-minor` | Symbolic / numerics | `sympy 1.14.0` requires `mpmath<1.4,>=1.1.0` | `sympy` release lifting `<1.4` |
| `scipy` | `semver-major` | Numerics | Engine numerics major policy | KPI-oracle-verified major migration |
| `scipy-stubs` | `semver-major` | Typed surface | Must stay aligned with `scipy` major | Lockstep with `scipy` major migration |
| `pydantic` | `semver-major` | Contracts / API | Strict v14 schema contract stability | Deliberate major contract migration |
| `pydantic-core` | `semver-major`, `semver-minor`, `semver-patch` | Contracts / API | Exact-pinned by `pydantic` (`==2.46.4` for 2.13.4) | Never bumped standalone; moves only with `pydantic` |
| `cachebox` | `semver-major` | Tests / diffing | `deepdiff 9.1.0` requires `cachebox>=5.2,<6` | Compatible `deepdiff` migration |
| `redis` | `semver-major` | Jobs backend | `arq 0.28.0` requires `redis>=4.2,<6` | `arq` / backend major migration |
| `protobuf` | `semver-major` | Micrositing | `ortools` caps `protobuf` below `7.x` | Resolver-clean `ortools` / micrositing migration |
| `mypy` | `semver-major`, `semver-minor`, `semver-patch` | Lint / CI gate | Diagnostics shift on any release; must match `test-suite.yml` pin `1.19.0` | Dedicated typed-surface dolphin updating lock, `constraints.txt`, and `test-suite.yml` together |
| `isort` | `semver-major` | Lint / CI gate | Gate rule stability (`<8`) | Dedicated lint dolphin |
| `ruff` | `semver-major`, `semver-minor` | Lint / CI gate | `0.x`-versioned; minors are breaking (`<0.15`) | Dedicated lint dolphin |
| `black` | `semver-major` | Format / CI gate | CalVer annual major (`<27`) | Dedicated format dolphin |
| `antlr4-python3-runtime` | `semver-major`, `semver-minor` | Hydra / config | `hydra-core 1.3.7` / `omegaconf 2.3.1` require `==4.9.*` | Lockstep with `hydra-core` / `omegaconf` upgrade |
| `pandapower` | `semver-major`, `semver-minor`, `semver-patch` | Grid screening | #1229 adapter & `config/pandapower_screening.json` pin `3.5.4` | Dedicated grid dolphin verifying `scipy` + `numpy` + adapter |
| `pyarrow` | `semver-major` | Dashboard / UI | `streamlit 1.60.0+` requires `pyarrow<25,>=7.0` | Lockstep with `streamlit` release lifting `<25` |
| `magika` | `semver-major`, `semver-minor` | Ingestion | `markitdown` requires `magika~=0.6.1` | `markitdown` release lifting `~=0.6.1` |
| `openmdao` | `semver-major`, `semver-minor` | Micrositing | `topfarm 2.6.2` requires `openmdao==3.39.*` | Lockstep with `topfarm` release accepting newer `openmdao` |
| `websockets` | `semver-major` | Dashboard / API | `streamlit` requires `websockets<17,>=12.0.0` | Lockstep with `streamlit` release lifting `<17` |
| `starlette` | `semver-major` | API runtime | `streamlit` requires `starlette<2,>=0.46.0` | Lockstep with `streamlit` release lifting `<2` |

---

## 2. Survey of `constraints.txt` pins

| Pin in `constraints.txt` | Owner | Rationale | Lift condition |
|---|---|---|---|
| `pandas<3` | Finance engine | Copy-on-Write / dtype safety | #593 KPI-verified pandas 3 migration |
| `mypy==1.19.0` | CI / typed surface | Matches `.github/workflows/test-suite.yml` pin | Dedicated typed-surface dolphin |
| `isort<8`, `ruff<0.15`, `black<27` | CI / lint surface | Prevents unreviewed formatting/lint rule churn | Dedicated lint/format dolphin |
| `pandas-stubs==2.3.3.260113`, `requests==2.34.2` | Typed surface | Gate-cleared stub/HTTP typing versions | Dedicated typed-surface dolphin |
| `markitdown==0.1.9`, `pdfplumber==0.11.10`, `pymupdf==2.1`, `pre-commit==4.6.2` | Ingestion & hooks | Reproducibility surfaces for PDF extraction and hooks | Dedicated ingestion/hook verification dolphin |
| `weasyprint==70.0`, `arq==0.28.0`, `brotli==1.2.1`, `hiredis==3.5.0`, `zopfli==0.4.3` | Reports & jobs | Python 3.12 rebaseline cleared production surfaces | Dedicated report/jobs verification dolphin |
| `antlr4-python3-runtime<4.10` | Hydra / config | Hard cap from `hydra-core 1.3.7` / `omegaconf 2.3.1` (`==4.9.*`) | `hydra-core` / `omegaconf` grammar regeneration upgrade |
| `pandapower==3.5.4` | Grid screening | Verified adapter and `config/pandapower_screening.json` pin | Reviewed policy + adapter update |

---

## 3. Recorded Decisions (#1414)

1. **Scheduled cap re-check vs `RELEASING.md` step-2 check alone:**
   - **Decision:** Keep the advisory check in `security-audit.yml` (daily scheduled, non-blocking) rather than relying solely on `RELEASING.md` step 2 at release cut time, so expired upstream caps (e.g. `pandapower` lifting `numpy<2.5` or `sympy` lifting `mpmath<1.4`) surface proactively as advisory signals without blocking PR merges.
2. **Auditing the installed `pip` package itself:**
   - **Decision:** Audit `pip` via `pip-audit` against the installed CI/environment `pip` version in `security-audit.yml` (separate from `requirements.txt`, which intentionally excludes the installer), and track any `pip` upgrade through the base environment / CI `setup-python` pin rather than `requirements.txt`.

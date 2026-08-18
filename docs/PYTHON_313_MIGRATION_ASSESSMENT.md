# Python 3.13 migration assessment

Status: **HOLD for baseline promotion; approve a future shadow-CI compatibility phase.**

Assessment cutoff: 2026-08-18 (Asia/Colombo)

Repository baseline: `384e990cf6319a4bad1148f2a5c7b5ce72619436`

Host used for local comparison: macOS 26.6.1, Apple Silicon (`arm64`)

## Executive decision

Python 3.13 is technically plausible for DutchBay, but it should not replace Python 3.12
yet. The complete current core suite and the separately installed optional capability
surfaces passed on the available Python 3.13 interpreter, and the canonical financial KPIs
were identical. That is strong compatibility evidence.

It is not yet sufficient release evidence because:

1. The single pinned lock was generated on Python 3.12 and is not complete for Python 3.13.
   LibCST selects an additional Python-3.13-only dependency, `PyYAML-ft`, which is absent
   from `requirements.txt` and was therefore resolved live rather than from the lock.
2. All protected CI, release, type-checker, Docker, and bootstrap surfaces remain qualified
   on Python 3.12 only.
3. The available local Python 3.13 was 3.13.11, while Homebrew offered 3.13.15 at the cutoff.
   The installed interpreter was not upgraded because another active DutchBay worktree was
   running tests from its 3.13.11 installation; invalidating that environment would have
   disrupted concurrent work.
4. On two small project-relevant benchmarks, standard CPython 3.13.11 was approximately
   11-13% slower than CPython 3.12.13 on this machine. There is no demonstrated performance
   case for immediate migration.
5. Python 3.13's free-threaded mode and JIT are experimental, separate build choices. The
   tested Homebrew interpreter was a normal GIL-enabled build, and no `python3.13t`
   interpreter was installed. Those features cannot be counted as benefits of a routine
   3.12-to-3.13 switch.

The recommended course is therefore:

- make Python 3.12 the enforced prerequisite now;
- add Python 3.13 later as a non-release, non-required shadow CI leg;
- close the 3.13 lock and cross-platform evidence gaps;
- promote 3.13 only in a separate, reversible baseline-change dolphin.

## Evidence collected

### Interpreter and environment

| Item | Python 3.12 baseline | Python 3.13 candidate |
| --- | --- | --- |
| Local interpreter | 3.12.13 | 3.13.11 |
| Homebrew stable at cutoff | 3.12.13 | 3.13.15 |
| Build | Standard GIL-enabled CPython | Standard GIL-enabled CPython |
| Free-threaded executable | Not applicable | `python3.13t` not installed |
| Project install | Pinned lock + `[dev]` passed | Pinned lock + `[dev]` passed |
| Full extras install | Existing qualified recipe | `[dev,feasibility,jobs,solar,pareto]` passed |
| `pip check` | Passed | Passed after core and full-extras installs |

The 3.13 candidate was deliberately not upgraded in place while another DutchBay process
was using the installed 3.13.11 Homebrew keg. A formal migration must repeat every result in
this document on the selected, fully patched 3.13 release.

### Dependency resolution

The core/dev environments contained the same 275 package name/version pairs, except that
Python 3.13 installed one additional package:

```text
pyyaml-ft==8.0.0
```

The cause is LibCST 1.9.0's interpreter marker:

```text
pyyaml>=5.2; python_version < "3.13"
pyyaml-ft>=8.0.0; python_version == "3.13"
pyyaml>=6.0.3; python_version >= "3.14"
```

`requirements.txt` pins `libcst==1.9.0` and `pyyaml==6.0.3`, but it does not pin
`pyyaml-ft`. The existing lock-generation recipe uses `pip freeze` from one interpreter,
so it cannot truthfully produce a complete multi-interpreter lock by itself. A Python 3.13
baseline change therefore requires either:

- a separately generated and governed Python 3.13 lock; or
- adoption of a lock compiler that resolves and records environment markers for both
  supported interpreter minors.

Hand-editing a marker into the generated lock is not an acceptable durable solution.

The principal scientific versions installed successfully on 3.13 were:

```text
numpy==2.4.6
pandas==2.3.3
scipy==1.18.0
pandapower==3.5.4
pydantic==2.13.4
matplotlib==3.11.1
numba==0.67.0
jax==0.11.1
topfarm==2.6.2
py-wake==2.6.20
```

The full optional installation also resolved WeasyPrint 69.0, ReportLab 5.0.0,
GeoPandas 1.1.4, Contextily 1.7.1, pvlib 0.15.2, arq 0.28.0, redis 5.3.1, and
pymoo 0.6.2.

### Test and canonical-result evidence

Core/dev 3.13 run:

```text
5184 passed, 13 skipped, 17 warnings, 0 failed
elapsed: 262.65 seconds
```

The 13 skips matched the documented lock-only profile: optional report, solar, jobs, and
pareto dependencies plus three intentional construction skips. After installing the full
declared extras, a focused test of all previously dependency-skipped capability families
produced:

```text
224 passed, 1 skipped, 7 warnings, 0 failed
elapsed: 88.97 seconds
```

The remaining skip was the expected inverse guard: WeasyPrint was installed, so the
"WeasyPrint missing" error-path test was not applicable.

The canonical lender-case results were identical between the two local environments:

| KPI | Python 3.12.13 | Python 3.13.11 |
| --- | ---: | ---: |
| Project IRR | `-0.001166233356501311` | `-0.001166233356501311` |
| Equity IRR | `-0.07853839579881605` | `-0.07853839579881605` |
| Minimum DSCR | `1.3` | `1.3` |
| Project NPV | `-91810995.06051566` | `-91810995.06051566` |

A deterministic 50-trial lender-case Monte Carlo run (`seed=42`) also produced identical
summary values on both interpreters, including:

```text
project_irr_mean = -0.009462165248267726
dscr_min_p50     = 1.2903390356984243
failed_iterations = 0
toy_fallback_count = 0
```

This is compatibility evidence, not authorization to rebaseline: protected CI and the
governed release path have not yet run on 3.13.

### Performance evidence

The comparison used the same repository revision and package versions on the same host.
Routine logging was suppressed. These are small local engineering benchmarks, not formal
cross-platform performance studies.

| Workload | Python 3.12.13 | Python 3.13.11 | Candidate change |
| --- | ---: | ---: | ---: |
| Canonical evaluation, median of 30 warmed calls | 0.071952 s | 0.079980 s | 11.16% slower |
| 50-trial lender MC, median of 3 runs | 2.419702 s | 2.736982 s | 13.11% slower |

The Python 3.13 candidate offered no measured speed advantage for the present DutchBay
workloads. The finance pipeline is a mixture of Python orchestration and compiled numeric
libraries; generic interpreter claims must not substitute for project measurements.

### Compatibility scans

- No first-party Python file imports any of the 19 standard-library modules removed under
  PEP 594 in Python 3.13.
- Three `locals()` references were found. Two inspect whether a local variable has been
  assigned and one is emitted diagnostic instrumentation; none attempts to mutate the
  returned mapping. The 3.13 `locals()` semantic change is therefore not a current blocker.
- A NumPy binary-size warning arose when importing `netCDF4==1.7.4` in two wind tests.
  Warning-as-error probes reproduced it on both Python 3.12 and 3.13, so it is a pre-existing
  NumPy/netCDF4 lock issue rather than a 3.13 regression. It should be resolved as a separate
  dependency-quality dolphin, not hidden inside the interpreter migration.

## Advantages of eventually adopting Python 3.13

### Longer supported life

Python 3.13 is scheduled to receive source security fixes until approximately October 2029;
Python 3.12's security window ends approximately October 2028. Promotion therefore buys
roughly one additional year before the next mandatory interpreter move.

### Better diagnostics and typing surface

Python 3.13 adds improved tracebacks and error suggestions, defined `locals()` behavior,
default values for type parameters, `typing.ReadOnly`, `typing.TypeIs`, and a standard
deprecation decorator. These can improve developer ergonomics and type expressiveness.

Most new syntax and standard-library typing features cannot become a project-wide advantage
while 3.12 remains supported. During a dual-version period the code must remain valid on the
3.12 floor or use compatibility backports.

### Future concurrency and optimization options

Python 3.13 introduces experimental free-threaded CPython and an experimental JIT. These are
strategic options worth monitoring for simulation workloads, but neither comes automatically
with a standard Python 3.13 installation:

- free-threading uses a separate build and executable and requires compatible C extensions;
- unsupported extensions can cause the GIL to be re-enabled;
- the Python documentation warns of experimental bugs and a substantial single-threaded
  performance penalty in free-threaded builds;
- the JIT is disabled by default, must be enabled at CPython build time, and had only modest
  expected gains in Python 3.13.

DutchBay already obtains parallelism through process-based test execution and compiled
numeric libraries. A free-threaded migration would be a separate architecture and
benchmarking programme, not part of a routine 3.13 baseline bump.

### Security and maintenance improvements

Python 3.13 includes stricter default TLS certificate verification behavior and continues
standard-library correctness and diagnostic improvements. Stricter TLS behavior is generally
beneficial, but live integrations such as data providers must be smoke-tested because an old
or non-compliant certificate chain may begin failing rather than being accepted.

## Constraints and disadvantages

### Reproducibility gap

The unpinned `PyYAML-ft` selection is the first concrete blocker. A lender-grade model cannot
claim a pinned environment while interpreter-specific dependencies are being selected from
the live package index.

The repository's optional extras are also not all represented in the present lock. That is an
existing design choice, but a claim that "all DutchBay runs on 3.13" needs an explicit full-
extras resolution record or governed lock, not only the core CI lock.

### CI and release cost

Python 3.12 is currently embedded in:

- the six-shard test and coverage matrix;
- fast-lane, FX, regression-smoke, nightly, and release workflows;
- both Docker build stages;
- mypy's target version;
- local, remote-session, and sourced-shell bootstrap paths;
- developer and feasibility reproduction documentation.

Adding 3.13 as a full second CI leg would approximately double interpreter-dependent test
work unless the shadow phase is limited to nightly or carefully selected gates. Replacing
3.12 immediately would remove the comparison needed to identify version-specific drift.

### No demonstrated performance return

The measured candidate was slower on both project-relevant workloads. The experimental JIT
was not active, and free-threading was not installed. Migration should therefore be justified
by support life and ecosystem maintenance, not by an unsupported speed claim.

### Binary-extension and platform risk

DutchBay uses a large compiled stack: NumPy, SciPy, pandas, netCDF4, rasterio, pyproj,
Shapely, pandapower dependencies, JAX, TopFarm, PyWake, WeasyPrint system libraries, and
others. Successful Apple-Silicon wheels and tests do not prove Linux `x86_64` Docker parity,
free-threaded compatibility, or live external-service behavior.

### Baseline churn soon after the 3.12 migration

The repository moved to 3.12 specifically to make pandapower and SciPy resolve together for
the grid-to-finance path. Moving again before the 3.12 baseline has completed its operational
soak adds lock, CI, Docker, and incident-response churn without a present functional need.

## Required migration gates

The following dolphins preserve a reversible path and must not be collapsed into one baseline
"whale".

### Dolphin 1 — shadow compatibility

- Upgrade an isolated candidate environment to the selected current Python 3.13 patch.
- Add a non-required 3.13 nightly test leg while retaining required 3.12 CI.
- Keep `python_version = "3.12"`, Docker, release, and production bootstrap unchanged.
- Record test totals, warnings, package resolution, and canonical KPIs separately by minor.

### Dolphin 2 — lock completeness

- Choose and document a multi-interpreter lock strategy.
- Pin the LibCST-selected `PyYAML-ft` dependency for 3.13 through the generator, not by hand.
- Resolve the existing netCDF4/NumPy binary-size warning or record an evidenced upstream
  disposition.
- Run `pip check` and the zero-allowlist security audit on both interpreter locks.

### Dolphin 3 — cross-platform and full-capability evidence

- Run the six-shard suite and coverage gate under Python 3.13 on Linux `x86_64`.
- Build and health-check a `python:3.13-slim-bookworm` shadow container.
- Repeat core and full-extras tests on macOS Apple Silicon.
- Smoke ERA5/CDS, GIS, grid, report/PDF, jobs/Redis, solar, pareto, and feasibility paths.
- Run canonical deterministic and stochastic identity gates with fixed seeds.

### Dolphin 4 — baseline promotion

Only after the shadow evidence is green:

- change `.python-version`, bootstraps, CI, mypy, and Docker together in one controlled
  baseline PR;
- regenerate the governed lock under the selected policy;
- update documentation and the model change record;
- retain a simple rollback to the last green Python 3.12 container and lock;
- do not introduce free-threading or the JIT in the same PR.

### Dolphin 5 — optional performance programme

If concurrency performance remains a goal, evaluate free-threaded CPython separately with:

- an explicit `python3.13t` build;
- an extension-by-extension GIL and wheel compatibility inventory;
- race-detection and shared-mutable-array review;
- deterministic MC/canon identity tests;
- lender-case and Monte Carlo benchmarks against process-based parallelism.

## Primary sources

- [Python 3.13: What's New](https://docs.python.org/3.13/whatsnew/3.13.html)
- [PEP 703: Making the Global Interpreter Lock Optional](https://peps.python.org/pep-0703/)
- [PEP 719: Python 3.13 release schedule](https://peps.python.org/pep-0719/)
- [PEP 693: Python 3.12 release schedule](https://peps.python.org/pep-0693/)
- [NumPy 2.3 release notes](https://numpy.org/doc/2.3/release/2.3.0-notes.html)
- [SciPy 1.15 release notes](https://docs.scipy.org/doc/scipy-1.16.0/release/1.15.0-notes.html)
- [LibCST 1.9.0 package record](https://pypi.org/project/libcst/1.9.0/)

## Conclusion

Python 3.13 has crossed the threshold from "probably incompatible" to "credible migration
candidate." It has not crossed the threshold to "qualified DutchBay baseline." Python 3.12
remains the correct prerequisite now, while 3.13 should enter a controlled dual-version shadow
phase after the current concurrent development work stabilizes.

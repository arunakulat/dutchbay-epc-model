# Hydra maintenance risk: stalled upstream cadence (ADR, #609 / benchmarking §4)

Status: **Accepted** (2026-07; refreshed 2026-11-27 under #1423). Decision: **stay on Hydra as
the canonical CLI framework** (GWTF CLI-01/R1 unchanged), declare `hydra-core` as an abstract
runtime dependency in `pyproject.toml`, keep the **OmegaConf + thin-CLI fallback** below as the
exit path should upstream become unmaintained, and track security-floor bumps in the lock
(originally `1.3.3` in 2026-07; subsequently `1.3.7` in #1339/#1341 and `1.3.8` in #1460).

## Context

Hydra (`hydra-core`, `hydra-ecosystem/hydra`, GitHub repository id `191632914`; transferred from
`facebookresearch/hydra`) is load-bearing in this repo:

- GWTF **CLI-01** mandates Hydra for all v14 CLIs (argparse banned repo-wide; Typer/Click
  frozen); **R1** names the two canonical entrypoints.
- `@hydra.main` sites (**30** non-test Python files; verified 2026-11-27):
  - **2** canonical root entrypoints: `run_full_pipeline_v14.py` and `run_scenario_analytics_v14.py`.
  - **3** packaged analytics CLIs (`analytics*` is in the wheel's
    `[tool.setuptools.packages.find]` include list, and each imports `hydra` at module scope):
    `analytics/cli/cli_sensitivity_hydra.py`, `analytics/cli/cli_monte_carlo_hydra.py`, and
    `analytics/cli/cli_capital_structure_optimize_hydra.py`.
  - **25** `scripts/*.py` runners: `scripts/01_github_repo_scanner.py`,
    `scripts/analyze_dutchbay_wake_deficit_gap_1589.py`,
    `scripts/generate_financing_questionnaire.py`,
    `scripts/run_blue_whale_capex_solar_resource_v14.py`,
    `scripts/run_blue_whale_met_mast_transfer_v14.py`,
    `scripts/run_blue_whale_solar_bess_v14.py`,
    `scripts/run_blue_whale_wind_siting_v14.py`,
    `scripts/run_dutchbay_wake_rebaseline_v14.py`,
    `scripts/run_equipment_parity_v14.py`,
    `scripts/run_f5_exit_evidence_v14.py`,
    `scripts/run_fx_tenor_screening_v14.py`,
    `scripts/run_neighbour_wake_sensitivity_v14.py`,
    `scripts/run_p90_recomputed_downside_v14.py`,
    `scripts/run_pysam_energy_crosscheck.py`,
    `scripts/run_site_analysis_v14.py`,
    `scripts/run_solar_bess_sizing_v14.py`,
    `scripts/run_synthetic_feeder_placeholder_v14.py`,
    `scripts/run_synthetic_input_records_v14.py`,
    `scripts/run_synthetic_qsts_finance_report_v14.py`,
    `scripts/run_synthetic_qsts_output_records_v14.py`,
    `scripts/run_wind_analysis_v14.py`,
    `scripts/run_wind_bess_options_v14.py`,
    `scripts/validate_audit_recovery.py`,
    `scripts/validate_f5_02_lender_return.py`, and
    `scripts/verify_p03_primary_sources.py`.
- The Hydra-only discipline for the four canonical pipeline CLIs (`CANONICAL_CLIS`:
  `run_full_pipeline_v14.py`, `run_scenario_analytics_v14.py`,
  `analytics/cli/cli_sensitivity_hydra.py`, `analytics/cli/cli_monte_carlo_hydra.py`) is
  lint-enforced by `tests/lint/test_entrypoints_hydra_only.py` (R3) and
  `tests/lint/test_no_argparse_anywhere.py`.

The 2026-07-01 SOTA benchmarking report (§4 register) flagged that Hydra's release cadence
has stalled and that a user-raised maintainer-status question in the upstream tracker went
unanswered. This ADR records the risk assessment and the accepted position.

## Evidence (verified 2026-07-02, not asserted)

Queried live from PyPI (`https://pypi.org/pypi/hydra-core/json`) and the upstream GitHub
release:

| fact | value |
|---|---|
| 1.3.2 upload date | 2023-02-23 |
| 1.3.3 upload date | 2026-06-11 (**~3 years 4 months** after 1.3.2) |
| 1.3.3 content | packaging-only: fixes source builds with modern setuptools by removing the `setup.py` dependency on `pkg_resources` (upstream #3207); no runtime behaviour change |
| 1.3.3 requires | `omegaconf<2.4,>=2.2` · `antlr4-python3-runtime==4.9.*` · `packaging` — all already satisfied by the lock (omegaconf 2.3.0, antlr4 4.9.3, packaging 25.0), so the bump moves **one line** of the lock |
| Hydra surface this repo consumes | `@hydra.main(version_base="1.3", config_path=..., config_name=...)` + the `key=value` dotlist override grammar. **No** multirun/sweeper, **no** launcher plugins, **no** `hydra.utils.instantiate`, no `hydra_plugins` (re-verified 2026-11-27 across `analytics/`, root CLIs, `scripts/`, and `conf/`) |
| pip-audit status (2026-07-02 baseline) | at the 2026-07 decision date, `pip-audit -r requirements.txt` passed with no known CVEs against `hydra-core` 1.3.3 or `antlr4-python3-runtime` 4.9.3; **superseded below** |

### Refreshed evidence (verified 2026-11-27 under #1423)

| fact | value |
|---|---|
| Upstream publisher & Trusted Publishing | Transferred from `facebookresearch/hydra` (owner id `16943930`) to `hydra-ecosystem/hydra` (owner id `296379823`, same GitHub repository id `191632914`). From `1.3.6` onward, PyPI Trusted Publishing is configured for `hydra-ecosystem/hydra` (branch `1.3_branch`, `workflow_dispatch`). |
| Current lock & transitive pins | `hydra-core==1.3.8`, `omegaconf==2.3.1`, `antlr4-python3-runtime==4.9.3`, `packaging==26.3` (`requirements.txt`). |
| Abstract floor in `pyproject.toml` | `hydra-core>=1.3.8,!=1.4.0.dev0,...,!=1.4.0.dev10,!=1.4.0rc1,!=1.4.0rc2` (`1.4.0rc3` is the first fixed 1.4 prerelease). |
| Subsequent CVEs & remediations | The 2026-07 "no known CVEs" statement was invalidated in October–November 2026: `CVE-2026-106441`, `CVE-2026-106442`, and `CVE-2026-106439` (affecting `1.3.4–1.3.6` and `1.4.0.dev0–dev9`, fixed in `1.3.7` under #1339/#1341), followed by `GHSA-wf6j-7hvr-gr93` (affecting `1.3.6–1.3.7` and `1.4.0.dev9–dev10`, `rc1`, `rc2`, fixed in `1.3.8` under #1460). |
| Current pip-audit status | `pip-audit --no-deps --disable-pip -r requirements.txt` passes with `No known vulnerabilities found` on `hydra-core==1.3.8` and an empty allowlist (`Makefile`). |

Assessment: the dependency is **stale but stable**. The consumed surface is deliberately
narrow (config-first per ARCH-01 — all behaviour lives in `conf/*.yaml` and scenario YAMLs,
not in Hydra features), Hydra sits on OmegaConf (already a direct runtime dep), and the lock
pins everything, so an unmaintained upstream cannot silently change behaviour. The realistic
failure modes are (a) an unpatched CVE in `hydra-core`/`antlr4-python3-runtime`, or (b) a
future Python/omegaconf version the frozen release cannot support.

## Decision

1. **Accept the risk; stay on Hydra.** CLI-01/R1 are unchanged. The stalled cadence is not,
   by itself, grounds to migrate: the consumed surface is tiny, pinned, and CVE-clean, and a
   preemptive migration would churn all four CLIs for zero user-visible benefit.
2. **Bump the pin to 1.3.3** in the reproducibility lock (`requirements.txt`). Because
   1.3.3's transitive requirements are unchanged and already satisfied, the single-line edit
   is exactly what the header's full regeneration recipe (`pip install -e '.[…]'` +
   `pip freeze`) produces for this package; a full regeneration was deliberately **not** run
   to avoid unrelated lock churn in a dolphin-sized change.
3. **Declare `hydra-core>=1.3.3` in `pyproject.toml` `[project.dependencies]`.** Settled
   nuance from #609: hydra-core previously appeared **only** in the lock, not in pyproject —
   an inconsistency, not intent. Packaged `analytics.cli` modules import `hydra` at module
   scope, so the wheel has a hard runtime dependency on it; worse, regenerating the lock
   from pyproject alone (the lock header's own instruction) would have silently **dropped**
   hydra-core and broken every canonical CLI.

## Fallback plan (if Hydra becomes unmaintained)

Replace `@hydra.main` with a **thin OmegaConf shim** — no config migration required:

- `omegaconf>=2.3` is already a direct runtime dependency (Hydra is built on it), so the
  fallback layer is partially staged today.
- All CLI config already lives in `conf/*.yaml` + scenario YAMLs (ARCH-01 config-first);
  none of it is Hydra-specific.
- The shim per entrypoint: `OmegaConf.load("conf/<name>.yaml")` merged with
  `OmegaConf.from_dotlist(sys.argv[1:])` — the same `key=value` override grammar the four
  CLIs consume today. No argparse (CLI-01/R3 stay intact: the dotlist is split on `=`, as
  Hydra itself does), no output-directory management beyond what the CLIs already do
  explicitly (`export_dir` is plain config, not Hydra job magic).
- Scope: all **30** `@hydra.main` sites (listed in Context above: 2 root entrypoints, 3
  `analytics/cli/*_hydra.py` modules, and 25 `scripts/*.py` runners), plus updating
  `tests/lint/test_entrypoints_hydra_only.py` to bless the shim as the canonical decorator,
  and a GWTF CSV amendment to CLI-01/R1 (a user-gated governance change, not a code detail).
- Not needed: multirun, sweepers, launchers, instantiate — the repo never adopted them, so
  the fallback loses nothing.

## Re-evaluation triggers

Revisit this ADR (open an issue, do not silently migrate) when **any** of:

1. `pip-audit` flags a CVE against `hydra-core` or `antlr4-python3-runtime` with no fixed
   upstream release — the mandatory CI gate makes this loud.
2. A planned interpreter bump (repo requires Python `>=3.12` today) or an `omegaconf` upgrade is
   blocked by the frozen Hydra release.
3. The upstream repo is archived, or a further ≥18 months pass with no release **and** an
   open incompatibility affecting this repo.
4. A further upstream repository transfer or PyPI Trusted Publishing identity change away from
   `hydra-ecosystem/hydra` (repository id `191632914`, owner id `296379823`).

## Consequences

- `requirements.txt`: `hydra-core==1.3.2` → `==1.3.3` (one line; transitive pins untouched).
- `pyproject.toml`: `hydra-core>=1.3.3` added to `[project.dependencies]` — the lock's
  regeneration recipe is now self-consistent and the wheel's dependency metadata is honest.
- No code change; 1.3.3 is packaging-only upstream, so runtime behaviour and all committed
  KPIs are unchanged (oracle-verified on the bumped environment).
- The fallback is documented and partially staged, keeping a future forced migration
  dolphin-sized instead of a whale.

Related: [`MONEY_PRECISION_DECISION.md`](MONEY_PRECISION_DECISION.md) /
[`CURRENCY_NUMERAIRE_DECISION.md`](CURRENCY_NUMERAIRE_DECISION.md) (the ADR pattern this
follows), GWTF rows CLI-01, R1, R3, ARCH-01.

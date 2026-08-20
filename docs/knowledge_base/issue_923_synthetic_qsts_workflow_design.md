# Issue #923 synthetic QSTS workflow: historical audit and A/B disposition

## Document control

| Field | Value |
|---|---|
| Status | Historical audit preserved with current A/B addendum and governed #1077/#1073 entrypoints |
| Audit date | 2026-08-19 |
| Audited commit | `4eda5ab09baae940848b01ebfa59ffd8764d587f` |
| Audited branch tip | `origin/main` at the historical cutoff |
| Preserved source SHA-256 | `779aaf3d272f04f0054431482e11e522e05c1c1c17708948b635b320cf77ae78` |
| Current addendum base | `6f8d279166912a7589f206f3e0bbeebc8272966a` |
| GitHub issue | [#923](https://github.com/arunakulat/dutchbay-epc-model/issues/923) |
| Issue state at cutoff | Open; state reason `reopened` |
| Current issue topology | #923 closed as split index; #1072-#1078 remain the open delivery outcomes |
| Evidence grade | Software-path evidence only; not site-representative or bankable |
| Canonical-finance effect | None; `grid.qsts.finance_wiring.enabled` remains false |

This record preserves the 2026-08-19 audit of the synthetic feeder and QSTS path and its
then-recommended implementation sequence. The current addendum below records the later
A/B decision without rewriting the audit evidence. It does not authorize a canonical
finance change, close a child outcome, or replace the real-feeder acceptance gate.

## Current A/B disposition

This section is the current decision surface. The audit, reproduction, gap register, and
historical recommendations that follow remain evidence at commit `4eda5ab`; they are not
silently rewritten as if they had been produced after the later merges.

### Delivered after the audit cutoff

| Slice | PR | Candidate | Squash on main | Current disposition |
|---|---:|---|---|---|
| Verified package-to-QSTS adapter | #1069 | `c42d5c0b9f4fc17803228d6898fbd21ef18757bb` | `d06c7a6a303c378814836ea5ba00240a040fc4d9` | Delivered; candidate and squash trees are identical |
| Runtime profile/export-cap binding | #1071 | `e481eae871c7049b4432f5f340c86ef18b009776` | `6f8d279166912a7589f206f3e0bbeebc8272966a` | Delivered; candidate and squash trees are identical |

These merges close the audit's G-01 package-to-runtime translation gap. They do not deliver
the governed workflow runner, authenticated real feeder, governed convergence/telemetry,
or either financial outcome.

### Live issue topology

| Outcome | Ingress | Calculation and records | Financial outcome |
|---|---|---|---|
| Shared mode/evidence gate | [#1072](https://github.com/arunakulat/dutchbay-epc-model/issues/1072) | - | - |
| #923-A: synthetic process provenance | [#1077 / #1075-A](https://github.com/arunakulat/dutchbay-epc-model/issues/1077) | [#1073 / #1076-A](https://github.com/arunakulat/dutchbay-epc-model/issues/1073) | [#1074 / #923-A](https://github.com/arunakulat/dutchbay-epc-model/issues/1074) |
| #923-B: authenticated real-data outcome | [#1075 / #1075-B](https://github.com/arunakulat/dutchbay-epc-model/issues/1075) | [#1076 / #1076-B](https://github.com/arunakulat/dutchbay-epc-model/issues/1076) | [#1078 / #923-B](https://github.com/arunakulat/dutchbay-epc-model/issues/1078) |

Issue #923 is closed only as the split index. The #923-B outcome remains open and blocked
until #1075-B and #1076-B deliver real, authenticated evidence.

### Authorized #923-A outcome

On explicit user instruction, the synthetic path may produce:

1. a governed synthetic AEP figure;
2. governed synthetic QSTS records; and
3. a segregated financial report carrying the exact prominent warning:

> based on synthetic data - non-bankable - only for process provenance purposes

This authorization changes the historical *separate synthetic counterfactual/reporting*
decision. It does not change the canonical-finance evidence firewall. The #923-A path must:

- be selected through an explicit YAML mode under #1072, with the synthetic mode default-off;
- bind the selected mode to verified evidence identity rather than a cosmetic label;
- keep generated inputs and outputs segregated from authenticated real-data outputs;
- retain `site_representative=false`, `bankable=false`, and
  `canonical_finance_eligible=false` throughout every result and report surface;
- retain zero weight for the real-data/sign-off closure gate;
- avoid canonical KPI pins, `VERSION`, or lender/board release claims; and
- fail before calculation or reporting if mode, evidence identity, or output segregation is
  inconsistent.

Canonical `grid.qsts.finance_wiring.enabled` therefore remains false for synthetic inputs.
The authorized report is a noncanonical process-provenance product, not permission to route
synthetic data through the canonical finance enablement boundary.

### Governed #1077 synthetic input-record handoff

Issue #1077 composes the existing deterministic package generator, detached verifier, and
production package-to-QSTS adapter through one input-only Hydra entrypoint:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" \
  "${DUTCHBAY_VENV:-.venv}/bin/python" scripts/run_synthetic_input_records_v14.py
```

Configuration is in `conf/synthetic_input_records.yaml`; it references rather than copies
the existing controlled `conf/synthetic_feeder_placeholder.yaml` generator configuration.
The command generates and compiles the package, verifies every payload against its external
manifest identity, ingresses it through `build_verified_synthetic_qsts_overlay()`, and then
re-verifies the package to close the post-ingress mutation window. It publishes only:

- `outputs/synthetic_process_provenance/issue_1077/synthetic_input_records.json`; and
- its detached `synthetic_input_records.sha256` trust anchor.

The handoff records the resolved generator-config SHA, generator/verifier/adapter source
hashes, repository commit and engine version, generation time, package schema and manifest
identity, every package payload hash, full profile horizon/timezone/unit/seed/algorithm,
source locations, limitations, the export cap, and the explicit absence of observed operator
instructions. Its centralized `SyntheticInputRecordHandoff` contract fixes QSTS and finance
execution, publication, lender/board eligibility, bankability, site representativeness, and
canonical-finance eligibility to false. It contains no QSTS, AEP, curtailment, KPI, or
financial outcome; those remain the sequential responsibilities of #1073 and #1074.

### Governed #1073 synthetic AEP/QSTS output record

Issue #1073 consumes only the authenticated #1077 JSON/SHA pair and the same package
manifest identity retained by that handoff. The caller must provide the detached handoff
SHA-256 as an external Hydra override; neither the JSON nor its sibling checksum is allowed
to authenticate itself:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" \
  /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python \
  scripts/run_synthetic_qsts_output_records_v14.py \
  input.expected_handoff_sha256=<64-lowercase-hex>
```

Configuration is in `conf/synthetic_aep_qsts.yaml`. The orchestrator re-verifies all eight
package payloads, uses the production package adapter without caller-supplied profile, cap,
or timestep overrides, clears the OpenDSS engine, explicitly activates and reads back the
controlled generator, and attempts every one of the 8,760 ordered UTC hours. It refuses to
publish if any timestep is non-converged or any generator setpoint is not accepted.

The retained JSON/SHA pair under
`outputs/synthetic_process_provenance/issue_1073/` records AEP in MWh/GWh, explicit energy
accounting, exact code/config/package/profile identities, Python and OpenDSS versions,
start/end times, convergence counts and first/last failure indexes, voltage/thermal
threshold counts and extrema, and the absent observed operator-schedule status. It carries
the mandatory warning and structurally fixes finance execution/wiring, canonical
eligibility, bankability, lender/board eligibility, and publication eligibility to false.
It is an input only to the segregated #1074 report gate.

The voltage/thermal observations are on the disclosed gross pre-export-cap and
pre-operator-instruction injection basis. A converged solve does not mean that those
thresholds passed, that the feeder is site-representative, or that a utility accepted it.
The OpenDSS result also does not convert the absent synthetic operator schedule into a claim
that CEB issued no instructions.

### #923-B outcome

The real-data path remains the only route to a bankability or canonical-finance decision. It
requires authenticated feeder evidence under #1075-B, governed real-feeder AEP/QSTS and
engineering validation under #1076-B, and the separate #923-B finance-wiring/sign-off
decision under #1078. No synthetic result may satisfy or substitute for those gates.

### Historical gap translation

| Audit gap | Current disposition |
|---|---|
| G-01: no verified package-to-QSTS adapter | Delivered by #1069 and hardened by #1071 |
| G-02: no governed workflow runner | Still open; decomposed across #1072 and the #923-A record/report chain |
| G-03: convergence and telemetry absent | Still open for governed real-feeder engineering evidence under #1076-B |
| G-04: synthetic KPI counterfactual absent | Explicitly authorized only as the segregated, noncanonical #923-A outcome |
| G-05: report dependency provenance stale | Still a separate KPI-neutral correction; this record does not change it |
| G-06: report existence does not prove QSTS success | Still applicable to both modes; receipts must bind calculation state and evidence identity |
| G-07: environment and path dependencies | Still applicable; PERSIST-01 requires the persistent central `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv` with `PYTHONPATH="$PWD"` in every worktree |

### Framework acceptance

The A/B implementation must remain explicit under the canonical frameworks:

- **CASPER:** mode/evidence APIs have predictable failure responses; optional grid
  dependencies remain call-time guarded; results expose their evidence limitations.
- **CESSPIT:** YAML mode is explicit, schema validation is strict, and pre-flight integrity
  refuses mixed, unauthenticated, or contradictory evidence before execution.
- **CCCDIR:** result contracts and eligibility fields remain centralized, and all consumers
  use the governed evaluation/grid gateways rather than a second finance or evidence path.

## Historical outcome at the audit cutoff

At the audit cutoff, a complete synthetic workflow could not be invoked through one governed
entrypoint.
The components can be composed manually, and that manual composition has demonstrated all
of the following:

- deterministic governed-package generation;
- detached manifest and payload verification against an external SHA-256 trust anchor;
- a real OpenDSS 8,760-step QSTS calculation;
- a report carrying the required synthetic-evidence warning and manifest identity;
- canonical KPI generation with exact invariance while finance wiring is disabled; and
- refusal when a synthetic feeder is presented to the canonical finance boundary.

The manual path is not yet an operator-ready workflow because no production adapter loads
the verified package profile into `grid.qsts.generation_profile_mw`, and no workflow runner
coordinates the package, QSTS, report, KPI-invariance, and refusal controls. Production QSTS
also does not yet govern timestep convergence or feeder telemetry, and the segregated
synthetic KPI counterfactual is explicitly deferred.

The verdict at the audit cutoff was therefore:

> Manual engineering composition: available. Complete governed workflow: unavailable.
> Canonical use of synthetic evidence: correctly refused.

## Historical governing boundary at the audit cutoff

Issue #923 was the evidence firewall between diagnostic grid calculations and lender-facing
project facts. Its acceptance criteria at the audit cutoff were:

1. A real feeder/QSTS model is available.
2. The user decides to incorporate self-curtailment into the base case.
3. `grid.qsts.finance_wiring.enabled` is enabled only against admissible real/site evidence.
4. A `kpi_oracle` before/after comparison is produced.
5. The user explicitly signs off the resulting canon movement.
6. Canonical pins are updated in the same controlled PR.

Synthetic packages have zero finding-closure weight. They may exercise software and support
scenario learning, but they cannot satisfy any real-data, site-representativeness,
engineering-acceptance, bankability, lender, board, or canonical-finance gate.

## Verified repository and GitHub state

At the audit cutoff, local `HEAD` and `origin/main` both resolved to:

```text
4eda5ab09baae940848b01ebfa59ffd8764d587f
```

Relevant merged slices were:

| Slice | PR | Merge | Delivered control |
|---|---:|---|---|
| #923-A | #1052 | `372edae` | Typed feeder provenance, strict validation, synthetic-finance refusal |
| #923-B1 | #1056 | `231b39d` | Deterministic governed synthetic feeder and profile package |
| #923-B2 | #1058 | `9e987c1` | Detached runtime verification and manifest propagation |
| #923-E | #1061 | `90ef428` | Warning-bearing presentation and release exclusion |

No implementation of #923-C or #923-D was present. All Actions runs associated with the
audited commit were completed successfully, including the push Test Suite, CI fastlane,
Regression Smoke, and the later scheduled Test Suite. Relevant PR suites were green, but
their conditional Grid Study job was skipped; those PR checks do not constitute a governed
8,760-step convergence record.

The shared `main` checkout contained ten pre-existing tracked deletions during the audit:
seven NSO/Envision BESS source, review, or RFP PDFs; two feasibility report PDFs; and the
Kalpitiya solar TMY CSV. None was restored, staged, or modified. The Issue #923 source files
were not locally modified.

## Component chain at the audit cutoff

| Stage | Existing entrypoint | Current status | Missing control |
|---|---|---|---|
| Package generation | `scripts/run_synthetic_feeder_placeholder_v14.py` | Available | None within #923-B1 scope |
| Detached verification | `verify_synthetic_feeder_package()` | Available | No production consumer exposes the verified profile values as a QSTS overlay |
| Runtime feeder binding | `_verify_synthetic_feeder_runtime_package()` | Available | Verifies feeder and manifest but returns only master path and digest |
| QSTS | `run_qsts_curtailment()` | Available | Caller must manually supply `generation_profile_mw`; no governed convergence or telemetry record |
| Advisory report | `emit_grid_screening_report_from_pipeline()` | Available | Reloads a scenario path; there is no package-derived effective scenario |
| Canonical KPIs | `run_v14_pipeline()` / `run_full_pipeline_v14.py` | Available | Synthetic QSTS remains finance-off, so it can prove invariance but not a synthetic KPI effect |
| Finance boundary | `require_canonical_self_curtailment_finance_config()` | Available | Correctly refuses synthetic/test inputs |
| Synthetic KPI counterfactual | Deferred in source to #923-D | Unavailable | Requires a separately governed noncanonical KPI result surface |

The manual flow at the audit cutoff was:

```text
Hydra package generator
        |
        v
manifest.json + MANIFEST.sha256 + feeder/*.dss + profile/*.csv
        |
        | external manifest SHA-256 supplied manually
        v
detached package verifier
        |
        | profile CSV parsed manually into an 8,760-value list
        v
manually constructed grid.qsts mapping
        |
        +---------------------> run_qsts_curtailment()
        |                              |
        |                              v
        |                    advisory CurtailmentShareResult
        |                              |
        |                              +------> warning-bearing HTML report
        |
        +---------------------> canonical finance pipeline
                                       |
                                       +------> unchanged KPIs while wiring is false
                                       |
                                       +------> refusal if synthetic wiring is true
```

The manual profile conversion is the principal B-series orchestration gap. It is not a
convergence or finance-model gap and should not be combined with either.

## Reproduced evidence

The governed package generator completed with:

| Field | Reproduced value |
|---|---|
| Status | `PASS` |
| Profile rows | `8760` |
| OpenDSS engine | `15.4.0` |
| Compile status | `passed_compile_only_no_convergence_claim` |
| Convergence status | `not_examined_deferred_issue_923_C` |
| Finance status | `not_run_scope_923_B` |
| Finding-closure weight | `0` |
| Issue closable | `false` |
| Manifest SHA-256 | `7b303ab3e4be1f4aff8a0ca9d733921b53b15adb87d0f309d0ac73e821562685` |

After manually constructing the required QSTS mapping, the real OpenDSS path produced:

| Field | Reproduced value |
|---|---:|
| QSTS ran | `true` |
| Timesteps | `8760` |
| Gross generation | `554674.3580389891 MWh` |
| Self-curtailed energy | `11022.075924000075 MWh` |
| Self-curtailment | `1.9871255565099177%` |
| Deemed-paid curtailment | `0 MWh` |
| Generated input | `true` |
| Site representative | `false` |
| Bankable | `false` |
| Canonical-finance eligible | `false` |

An independent diagnostic probe observed 8,760 converged OpenDSS solves. This does not close
#923-C because the production QSTS loop does not query, enforce, or persist convergence, and
the manifest truthfully records that convergence and telemetry were not examined.

The baseline and synthetic-disabled canonical KPI dictionaries were exactly equal. Enabling
finance wiring with the synthetic feeder raised the intended canonical-configuration
`ValueError`. This proves the evidence firewall, not a synthetic finance counterfactual.

The scoped audit suite completed with:

```text
224 passed, 1 skipped, 4 warnings in 42.07s
```

The skipped case was the missing-grid-dependency branch because the governed grid packages
were installed.

## Gap register

### G-01: no verified package-to-QSTS adapter

`VerifiedSyntheticFeederPackage` exposes the master path, profile path, manifest digest,
row count, timestamps, maximum generation, compile status, and convergence status. The
verifier already parses and validates every generation row, but discards the values after
validation. `run_qsts_curtailment()` separately requires an explicit
`grid.qsts.generation_profile_mw` sequence. Tests and the manual audit therefore reconstruct
the mapping outside production code.

### G-02: no governed workflow runner

The generator, finance pipeline, and report have independent entrypoints. The report reloads
its scenario from a file path, so an in-memory QSTS overlay is not sufficient. There is no
Hydra runner that produces a package-derived effective scenario, runs QSTS, verifies that the
curtailment screen did not degrade, generates canonical KPIs, proves KPI invariance, renders
the report, and confirms finance refusal.

### G-03: #923-C convergence and telemetry are absent

The production OpenDSS loop calls `Solution.Solve()` but does not check or persist:

- `Solution.Converged()` per timestep;
- POC and feeder voltage extrema;
- line/cable and transformer thermal loading;
- generator activation and delivered injection at every step; or
- a governed exception/failure policy for non-converged timesteps.

This is a distinct engineering-evidence dolphin. The package-runtime adapter must not invent
or infer any of these fields.

### G-04: #923-D synthetic KPI counterfactual is absent

Source validation explicitly refuses `finance_wiring.enabled=true` for synthetic and test
inputs and states that the separate counterfactual path will exist once #923-D is implemented.
Canonical KPI invariance while wiring is false is available today; a governed noncanonical
KPI delta attributed to the synthetic QSTS is not.

### G-05: report dependency provenance is stale

`app/reports/grid_screening_emit.py` declares `pandapower==3.3.0`. The governed lock and
audited runtime use `pandapower==3.5.4`. This should be corrected in an independent,
KPI-neutral presentation-provenance dolphin rather than bundled into the runtime adapter.

### G-06: report existence does not prove QSTS success

The report emitter degrades the curtailment screen on an exception and can still render an
HTML report. Any workflow receipt must therefore assert all of the following independently:

- the QSTS result is present;
- `ran` is true;
- the verified manifest digest matches the external trust anchor;
- input kind is `synthetic_placeholder`;
- generated input is true;
- site representativeness, bankability, and canonical eligibility are false; and
- no `curtailment` degradation entry exists.

### G-07: environment and path dependencies

The governed runtime requires Python 3.12 and the checkout-local `.venv` created by
`./setup_venv.sh`. The grid lock includes `dss-python==0.15.7`,
`opendssdirect.py==0.9.4`, `pandapower==3.5.4`, and `andes==2.0.0`. The shared main checkout
did not contain `.venv` at the audit cutoff.

On macOS, path verification resolves symlink ancestry. `/tmp` resolves to `/private/tmp`, so
a caller must use the resolved path when a temporary package is involved. The controlled
repository output path is not affected by that particular alias.

## Historical recommended implementation sequence

The sequence below keeps package adaptation, convergence, synthetic finance, and real-data
replacement separate.

### Dolphin 0: correct the report dependency stamp

Scope: one presentation-provenance correction and its focused test. Change the declared
pandapower pin from `3.3.0` to the governed `3.5.4` value. This is independent of Issue #923
runtime behaviour and must remain KPI-neutral.

### Dolphin #923-B3: verified package-runtime adapter

Purpose: remove the manual profile/config translation without claiming a complete workflow.

The adapter should accept only:

- a package `manifest.json` path; and
- an externally supplied expected manifest SHA-256.

It should call the existing detached verifier before returning any runtime input. The
existing verifier should retain the already-validated generation values during its single
CSV pass and add the following immutable fields to `VerifiedSyntheticFeederPackage`:

```text
generation_profile_mw: tuple[float, ...]
export_cap_mw: float
```

Retaining values inside the verifier avoids a second unverified CSV read and the associated
time-of-check/time-of-use gap. `export_cap_mw` must be read from the externally pinned
manifest field `profile.export_cap_mw_for_future_counterfactual` and checked as a positive
finite value.

The adapter should return only the `qsts` submapping so the caller deep-merges it into the
base scenario's existing `grid` block rather than replacing grid-study data. Its controlled
shape should be exactly:

```yaml
enabled: true
input_kind: synthetic_placeholder
feeder_model_path: <resolved verified package>/feeder/Master.dss
source_manifest_sha256: <externally pinned and verified digest>
export_cap_mw: <verified manifest export cap>
generation_profile_mw: <verified immutable 8760-value sequence>
finance_wiring:
  enabled: false
  mode: synthetic_counterfactual
  canonical_eligible: false
```

The finance triple is a fixed adapter invariant, not a caller option. The adapter must not
return `grid_instructed_profile_mw`: absence means no utility/operator instruction is
asserted. It must not replace absence with an all-zero schedule because that would present an
assumption as observed operator evidence.

Suggested implementation surfaces are:

```text
analytics/grid/synthetic_feeder_placeholder.py
analytics/grid/synthetic_feeder_qsts_adapter.py
tests/grid/test_synthetic_feeder_qsts_adapter.py
```

If the adapter introduces a public result type rather than a private typed mapping, that
contract belongs in `analytics/contracts_v14.py` under CCCDIR.

#### #923-B3 required acceptance tests

1. Correct external digest returns exactly 8,760 finite, non-negative profile values.
2. Returned master path is the verifier-resolved packaged `Master.dss`.
3. Export cap equals the verified manifest value.
4. The generated QSTS mapping passes the existing grid-interface validation.
5. Finance wiring is exactly false/counterfactual/noncanonical and cannot be overridden.
6. No grid-instructed schedule is manufactured.
7. Wrong external digest fails before an overlay is returned.
8. Tampered profile, feeder, manifest, or checksum fails before an overlay is returned.
9. Compile-disabled test packages remain invalid runtime inputs.
10. The adapter returns no convergence, telemetry, bankability, or issue-closure claim.

This dolphin is complete when callers no longer need custom CSV parsing or hand-written QSTS
profile/config construction. It does not need to run finance or render a report.

### Dolphin #923-B4: governed synthetic workflow runner

Purpose: compose existing components after #923-B3 without implementing #923-C or #923-D.

Add a Hydra-only, JSON-first runner and matching config. A suitable controlled interface is:

```text
run_synthetic_qsts_workflow_v14.py
conf/synthetic_qsts_workflow.yaml
```

Required config inputs should include:

```yaml
base_scenario_path: scenarios/dutchbay_lendercase_2025Q4.yaml
manifest_path: outputs/synthetic_placeholders/issue_923/manifest.json
expected_manifest_sha256: <external trust anchor>
export_dir: outputs/issue_923_synthetic_workflow
emit_grid_screen: true
```

The runner should:

1. Load the base scenario with the canonical scenario loader.
2. Invoke #923-B3 and deep-merge only its `qsts` submapping into `grid`.
3. Validate the complete effective scenario strictly.
4. Save the effective scenario or an equivalent lossless run specification as a governed
   evidence artifact carrying its hash, package digest, model version, and source scenario.
5. Run QSTS and require `ran=true` with the exact verified manifest identity.
6. Run the canonical baseline and finance-off synthetic-overlay pipelines and require exact
   KPI equality. Label this a canonical-invariance control, not a synthetic KPI oracle.
7. Render the warning-bearing grid report from the effective scenario path.
8. Fail the workflow if the report's curtailment screen degraded or its result does not match
   the separately obtained QSTS result.
9. Perform a controlled refusal probe by presenting the synthetic classification to the pure
   canonical-finance configuration guard and requiring the expected refusal category.
10. Emit one concise JSON receipt and durable structured results; do not retain high-volume
    runtime logs.

Minimum governed output set:

```text
effective_scenario.yaml
workflow_receipt.json
qsts_result.json
canonical_kpi_invariance.json
finance_boundary_refusal.json
grid_screening_report.html
```

The receipt must distinguish calculation success from evidence eligibility. A suggested
status surface is:

```json
{
  "workflow_status": "PASS",
  "qsts_ran": true,
  "manifest_verified": true,
  "convergence_governed": false,
  "canonical_kpis_unchanged": true,
  "synthetic_finance_refused": true,
  "site_representative": false,
  "bankable": false,
  "canonical_finance_eligible": false,
  "issue_923_closable": false
}
```

The workflow must fail rather than emit `PASS` if QSTS degraded, the manifest identity is
lost, canonical KPIs differ, or synthetic finance is not refused.

### Dolphin #923-C: governed convergence and telemetry

Implement separately after the B-series workflow seam exists. Required decisions include
the exact monitored buses/elements, voltage and thermal limits, generator-delivery check,
non-convergence policy, evidence schema, and concise retained validation record. A diagnostic
8,760/8,760 observation is not an adequate substitute for these contracts.

### Dolphin #923-D: segregated synthetic KPI counterfactual

Implement separately from #923-C and the canonical finance path. It must produce a clearly
noncanonical before/after KPI comparison without enabling
`grid.qsts.finance_wiring.enabled` in the canonical pipeline. The result requires its own
contract, warning, export path, and anti-promotion tests.

### Dolphin #923-R: real-feeder replacement and user gate

This remains the only route to canonical enablement. It requires admissible utility-observed
or engineer-prepared site evidence, complete package provenance, governed convergence and
telemetry, the lender KPI oracle, explicit user sign-off, and canon repinning.

## Explicit non-goals for #923-B3 and #923-B4

The adapter and workflow runner must not:

- set `finance_wiring.enabled` to true;
- use `mode: canonical`;
- set `canonical_eligible` to true;
- call a synthetic result site representative, utility observed, engineering accepted,
  bankable, lender eligible, board eligible, publishable, or canonical;
- infer an operator dispatch schedule from generation, export-cap exceedance, voltage, or
  thermal monitors;
- claim timestep convergence merely because the QSTS loop returned;
- close Issue #923 or assign positive finding-closure weight;
- update canonical KPI pins, `VERSION`, or `CHANGELOG.md`; or
- bundle the #923-C or #923-D implementation into the package-adapter PR.

## Environment and commands

Create the governed environment in the active worktree:

```bash
./setup_venv.sh
source .venv/bin/activate
```

Generate the controlled package:

```bash
.venv/bin/python scripts/run_synthetic_feeder_placeholder_v14.py
```

Run the focused evidence suite used for the audit:

```bash
.venv/bin/python -m pytest \
  tests/grid/test_synthetic_feeder_placeholder.py \
  tests/grid/test_synthetic_feeder_runtime_provenance.py \
  tests/grid/test_curtailment_qsts_dynamics.py \
  tests/grid/test_qsts_finance_real_solver_e2e.py \
  tests/finance/test_self_curtailment_enablement_readiness.py \
  tests/app/test_grid_screening_emit.py \
  tests/integration/test_grid_screening_report_emit.py \
  --no-cov -p no:cacheprovider -q
```

Run the grid-marked lane:

```bash
.venv/bin/python -m pytest tests/ -m grid
```

Until #923-B4 exists, report generation still requires a manually prepared effective
scenario file:

```bash
.venv/bin/python run_full_pipeline_v14.py \
  config=/absolute/path/to/prepared-synthetic-scenario.yaml \
  +emit_grid_screen=true \
  write_artifacts=true \
  run_scoped=true \
  export_dir=outputs/issue_923_synthetic_run
```

## Historical decision request and resolution

At the audit cutoff, the recommended next Issue #923 implementation was #923-B3 only: retain
the generation values already parsed by the verifier and add the fixed noncanonical QSTS
adapter with focused tests. That adapter and its runtime binding were subsequently delivered
by #1069 and #1071.

The later user decision authorizes the segregated #923-A synthetic process-provenance outcome
described in the current addendum. It does not authorize canonical synthetic finance,
manufactured real-data evidence, or closure of the #923-B authenticated-data outcome.

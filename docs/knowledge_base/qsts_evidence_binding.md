# QSTS evidence binding and output modes

Issue #1072 adds a control-plane boundary around the existing QSTS input-kind vocabulary.
It does not provide the missing CEB feeder, a bankable AEP, convergence evidence, utility
acceptance, or financial approval. It prevents a path or YAML label from being mistaken for
those things.

## YAML mode boundary

The input kind remains explicit. A governed synthetic package uses its detached B1 manifest
identity and keeps finance disabled:

```yaml
grid:
  qsts:
    enabled: true
    input_kind: synthetic_placeholder
    feeder_model_path: /controlled/package/feeder/Master.dss
    source_manifest_sha256: <externally-pinned-lowercase-sha256>
    finance_wiring:
      enabled: false
      mode: synthetic_counterfactual
      canonical_eligible: false
```

An observed utility model or engineer-prepared site model instead requires a separate,
externally pinned evidence manifest:

```yaml
grid:
  qsts:
    enabled: true
    input_kind: engineer_prepared_site_model
    feeder_model_path: /controlled/site-package/feeder/Master.dss
    evidence_manifest_path: /controlled/site-package/evidence-manifest.json
    evidence_manifest_sha256: <externally-pinned-lowercase-sha256>
    finance_wiring:
      enabled: false
      mode: canonical
      canonical_eligible: false
```

The second example is still non-bankable and finance-disabled. Enabling canonical finance is
a separate user-gated change after the real-data dependencies, KPI reconciliation, and
sign-off gates close. Neither an evidence-manifest hash nor a successful solve grants that
approval.

The two identity families are mutually exclusive. A synthetic/test input cannot carry a
real/site evidence identity, and a utility/site input cannot carry the synthetic package
identity. Cross-mode reclassification fails before solving or report construction.

## Real/site evidence manifest v1

`dutchbay_qsts_evidence_manifest_v1` uses exact keys. The following is an illustrative
shape; every SHA-256 value is calculated over the exact payload bytes and the manifest's own
digest is pinned outside the package.

```json
{
  "schema": "dutchbay_qsts_evidence_manifest_v1",
  "package_id": "ceb-or-engineer-package-id",
  "input_kind": "engineer_prepared_site_model",
  "classification": {
    "generated_input": false,
    "observed_network_data": false,
    "site_representative": true,
    "bankable": false
  },
  "provenance": {
    "source_authority": "named issuing authority",
    "source_reference": "controlled transmittal or document reference",
    "issued_at_utc": "2026-08-20T00:00:00Z"
  },
  "feeder_model_path": "feeder/Master.dss",
  "runtime_inputs": {
    "generation_profile_mw_path": "profiles/generation.json",
    "grid_instructed_profile_mw_path": "profiles/instructions.json",
    "export_cap_mw": 150.0,
    "timestep_hours": 1.0
  },
  "payload_sha256": {
    "feeder/Master.dss": "<sha256>",
    "profiles/generation.json": "<sha256>",
    "profiles/instructions.json": "<sha256>"
  }
}
```

Both profile files use the strict shape below. Generation and instruction schedules must
have the same non-zero length; values are finite MW quantities greater than or equal to
zero.

```json
{"schema":"dutchbay_qsts_profile_v1","unit":"MW","values":[0.0,1.0]}
```

Every `Redirect`, `Compile`, or static DSS file reference must resolve to a safe relative
path listed in `payload_sha256`. Absolute, dynamic, escaping, unlisted, missing, symlinked,
or digest-mismatched payloads are refused. The verifier retains the accepted bytes and QSTS
executes a private temporary snapshot, so later source mutation cannot alter the run.

## Result and report boundary

An accepted run propagates its external manifest digest and a typed
`dutchbay_qsts_run_manifest_v1` receipt. The receipt records the package ID, input kind,
payload digests, finance declarations, and output class. It structurally keeps `bankable`,
`lender_eligible`, `board_approval_eligible`, and `release_eligible` false.

Generated/test results are routed only under `synthetic_process_provenance` and always carry
this exact warning:

> based on synthetic data - non-bankable - only for process provenance purposes

Paths labelled real, canonical, lender, board, approval, release, or bankable are refused
for generated QSTS output. This is segregation and provenance, not a synthetic-data
bankability pathway.

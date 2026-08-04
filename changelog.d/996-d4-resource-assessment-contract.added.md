- **Frozen `ResourceAssessment` contract (#996 D4)** — a new, dependency-light
  `analytics/resource_contracts.py` adds a read-only `ResourceAssessment` dataclass: a
  versioned projection of a wind assessment's P50/P75/P90 net AEP + capacity factors, farm
  capacity/turbine count, report grade (`analytics.run_modes.RunMode`), and an optional
  `RunManifest` (so an instance is a self-identifying resource snapshot). Constructing one
  fails loud (CESSPIT) on two invariants: the `AEP = capacity_mw × 8760 × CF` identity for
  every P-level, and `P90 ≤ P75 ≤ P50` monotonicity of AEP and CF. A `from_assessment(...)`
  classmethod projects a `WindPipeline.run_complete_assessment` result, and the type is
  re-exported through `analytics.contracts_v14` (no import cycle — it does not subclass
  `ContractMixin`; it provides an equivalent `model_dump()`/`dict()` via `asdict`). This slice
  is purely additive and consumed nowhere yet, so the canonical KPI vector is byte-identical;
  a follow-up wires construct-and-validate into the async location-assessment path and surfaces
  the snapshot on `CaseResult`. Ref #996.

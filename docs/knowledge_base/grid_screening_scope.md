# Grid interconnection SCREENING — scope, boundary and the EMT gap (#884, D8)

This document is the scope contract for the in-house Python grid study surfaced by
`app/reports/grid_screening_emit.py` (the D8 reporting dolphin of grid-capability epic #870). It
states, once and canonically, **what the screen IS, what it is NOT, and where the hard boundary
lies** — the RMS/phasor → EMT gap, evidenced by real Sri Lankan CEB/NSO BESS tenders.

## 1. What this screen IS

A **design-stage, advisory pre-check** that runs entirely in-house on the finance model's stack:

- **SCR @ POC / GFL-vs-GFM (D1)** — the short-circuit ratio at the point of connection from an
  IEC 60909 **minimum-case** short-circuit screen (pandapower, or a closed-form Thevenin fallback
  when the `[grid]` extra is absent), banded weak/moderate/strong with a grid-following vs
  grid-forming recommendation.
- **Reactive capability / PQ box (D3)** — whether the plant holds the grid-code power factor across
  the P × grid-voltage envelope, and the Mvar shortfall (STATCOM/MSC sizing figure) if not.
- **Harmonics & flicker (D7)** — an **SCR-coupled** screening approximation of harmonic voltage
  distortion (IEEE 519:2022, indexed by the Isc/IL ratio) and IEC 61400-21 flicker Pst, plus the
  frequency-response de-load headroom. Both the harmonic voltage and flicker **worsen as SCR drops**.
- **Ride-through (D4a)** — an RMS envelope screen (LVRT / HVRT / frequency) using the **generic WECC
  IBR model** (REGCA1/REECA1/REPCA1), optionally solved through ANDES.
- **Hybrid-POC aggregation (D5b)** — the composite/weighted SCR and aggregate ±Q envelope for a
  multi-tech fleet behind one POC.
- **Combined frequency-droop (D5c)** — the ENPPC plant-controller split of a P(f) obligation across
  the droop-capable groups, with the settling frequency screened against the ride-through band.
- **Curtailment split (D6)** — an OpenDSS QSTS split of curtailed energy into deemed-paid
  (grid-instructed, KPI-neutral under the CEB SPPA) vs self-curtailed (a real loss, wired to finance
  only later by D6b).

Every sub-screen is **advisory (`bankable=false`)** and **NEVER feeds the financial model**. The
committed finance canon (projIRR / eqIRR / min_dscr) is **oracle byte-identical** whether or not this
study runs — the report is default-off (`emit_grid_screen:false`) and produces only an additional
advisory HTML artifact when enabled.

## 2. What this screen is NOT — the bankable connection study

This is **NOT the utility-accepted bankable grid-connection study.** The bankable study is a
**PSS®E or PowerFactory** run against the **CEB / NSCC confidential grid base case**, with the
**OEM-certified `.dyr` / `.dll` / `.pfd`** dynamic models — an EMT (PSCAD/EMTDC or EMTP) study where
the phasor screen cannot be trusted. This in-house screen is a design-stage pre-check to catch
problems early and size mitigations; it is **never a sign-off**.

## 3. The EMT gap (the hard boundary)

ANDES and pandapower are **RMS / positive-sequence (phasor)** tools only. They cannot represent the
sub-cycle EMT phenomena (converter control-loop interaction, PLL instability, harmonic resonance)
that govern a **weak grid**. Therefore:

- A **marginal SCR (below ~2–3)** or any weak-grid interconnection is stamped
  **"EMT confirmation required"** — the RMS screen is not authoritative there, and an EMT
  (PSCAD/EMTDC) study against the utility base case with the OEM binaries is **mandatory**.
- The generic WECC ride-through model is **not** the OEM-certified `.dyr`/`.dll`; a true
  fault-ride-through compliance verdict is an EMT run.
- The harmonics/flicker screen is a **screening approximation that degrades as SCR falls**, not a
  standalone pass/fail; the bankable version is a frequency-domain PSS/E or PowerFactory harmonic scan
  against the utility's confidential harmonic base case with the OEM current-emission spectra.

## 4. Real evidence — the #868 CEB/NSO BESS tenders (why the boundary is evidenced, not abstract)

The EMT boundary is grounded in real Sri Lankan procurement (sources: the `BESS_868_*` deliverable /
memory `dutchbay-bess-ceb-tender-and-huawei-quote` §8 + `nso-bess-250mw-round-2026`):

- **Real per-GSS 3-phase fault levels → SCR ≈ 33–77 across all 16 POCs**
  (SCR = √3 · 33 kV · I_fault / 10 MW; **Vavunathivu 5.8 kA → SCR 33** weakest,
  **Matara 13.5 kA → SCR 77** strongest). This is real validation data for the pandapower SCR@POC
  screen: at SCR 33–77 the Sri Lankan grid is stiff, well clear of the marginal-SCR EMT territory.
- **160 MW round (CEB 2025/003/C):** grid-forming was **NOT required** ("functional availability is
  sufficient"); SCR 33–77 ≫ the RFP GFL floor of 1.2 → a grid-following plant is **compliant**.
- **250 MW round (NSO 2026/001/C):** true grid-forming (V/F) is **MANDATORY** (Vol I clause 3c;
  IEEE 1547-2018 + IEEE 2800-2022 + UL 1741-SB) → a GFL-only plant is **non-compliant**. The
  control-mode decision is round-specific: the July-2024 national Grid Code Annex B is **silent** on
  grid-forming — it lives in each round's Annex A / Vol I.
- **Both rounds mandate PSS®E + PSCAD/EMTDC** dynamic models proving V/P/Q at
  **SCR = 1, 3, 5, 10 (X/R 5)** plus a **±50° phase step**. A real OEM (Envision) delivered
  **RMS-only** (PSS/E + DIgSILENT) → a **documented EMT/PSCAD gap** that had to be closed. That gap is
  exactly the RMS→EMT boundary this in-house screen stamps.

The takeaway the report surfaces: an in-house RMS screen can validate stiffness (SCR@POC) and size
reactive/harmonic mitigations early, but the **utility mandate is an EMT (PSCAD/EMTDC) study** — the
screen flags where that is required and never substitutes for it.

## 5. Provenance surfaced in the report (not internal)

Per the `surface-provenance-in-presentation-layer` directive, the report SURFACES:

- **Dependency reproducibility** — the resolved `[grid]` optional-extra pin set
  (`pandapower==3.3.0` / `andes>=2.0` / `opendssdirect.py>=0.9.4`) with the **CASPER
  available-vs-degraded state** of each engine at run time (which optional engines were present vs
  guard-degraded to closed-form / not-run).
- **Verification discipline** — that the study is additive and default-off, adversarially reviewed,
  KPI-neutral (oracle byte-identical), and degrades gracefully (a missing engine or config gap
  downgrades that screen to an honest "not run" state, never a fabricated pass and never a crash).

## 6. Un-suppressibility

The SCREENING-not-bankable caveat, the EMT-gap caveat, the per-SCR "EMT confirmation required" stamp
and the tender-evidence note are **module constants baked structurally** into the report model and its
Jinja2 template. **There is no config path that removes them** — a grid screen presented without them
would be a lender-facing misrepresentation.

## 7. D6b finance-wiring enablement — the missing input (#923)

The ONE parked KPI-mover of epic #870 is the D6b self-curtailment finance wiring
(`grid.qsts.finance_wiring.enabled`, shipped default-off in #885). **It stays parked because its
required input does not exist yet**, and the code's own gate makes flipping the flag today vacuous:
with the flag on but no real feeder, `analytics/grid/curtailment_qsts.py` emits an inert NOT-RUN
result and `finance/self_curtailment_v14.py` refuses to fabricate a haircut — the committed canon
stays byte-identical (verified end-to-end by
`tests/finance/test_self_curtailment_enablement_readiness.py`).

**The missing input — precisely:** the real **CEB 33 kV distribution feeder model at the DutchBay
point of connection** (Kalpitiya / Puttalam GSS side).

- **Acceptable format:** an OpenDSS master file (`.dss`, `Redirect`-able by OpenDSSDirect — a
  `Master.dss` plus its component files is fine; the path handed over must be the master).
- **What it must contain:** the feeder topology with conductor/cable impedances (positive- and
  zero-sequence), transformer data, the **POC bus** where the plant injects, and the **upstream
  source equivalent** (fault level / Thevenin impedance at the GSS busbar). Optionally, the
  operator's feeder-limit / dispatch schedule — that becomes the committed
  `grid.qsts.grid_instructed_profile_mw` (deemed-paid, KPI-neutral under the CEB SPPA).
- **Where it plugs in:** `grid.qsts.feeder_model_path` on the target scenario, with
  `grid.qsts.enabled: true`, a strict `grid.qsts.export_cap_mw` (falls back to the
  top-level `grid.export_cap_mw`; raises only when neither is present), and a committed
  `grid.qsts.generation_profile_mw` (or the resource-driven profile follow-up). The engine
  requires the `[grid]` extra (`opendssdirect.py>=0.9.4`); absent, it raises the actionable
  CASPER ImportError rather than silently returning canon.
- **What happens next (the user-gated sequence, all in the SAME PR):** QSTS run against the real
  feeder → `kpi_oracle` before/after diff → **explicit user sign-off** → set
  `grid.qsts.finance_wiring.enabled: true` on the target scenario → re-pin the canon
  (`tests/finance/test_multitech_generation.py` / `test_senior_fees.py`).

Wiring readiness is already proven demo-grade: with a synthetic demo feeder + stubbed solver
(labelled, NOT site physics), the production chain moves the KPIs exactly as designed — measured
**projIRR −1.007 pp, eqIRR −1.636 pp, min_dscr −0.0092 at an exact 8.0 % self-curtailment**
(matching the #885/#923 reference) while the committed canon in the same suite stays bit-for-bit
unchanged. Only the self-curtailed fraction ever haircuts; the deemed-paid (grid-instructed)
fraction is paid as deemed energy and is proven KPI-neutral through the same real chain.

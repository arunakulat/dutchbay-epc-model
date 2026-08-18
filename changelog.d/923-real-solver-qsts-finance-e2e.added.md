- **D6a→D6b end-to-end through the REAL grid solvers (#923)** — the self-curtailment wiring
  was covered from both ends but never joined through the real solvers:
  `test_self_curtailment_enablement_readiness.py` drives the production chain into finance
  but substitutes a `_RecordingStubDss` for `_require_opendss`, while
  `test_curtailment_qsts_dynamics.py` runs the real solver and stops at the
  `CurtailmentShareResult` without reaching the cashflow. Nothing asserted that the real
  solve moves the finance KPIs the way the stubbed chain claims — if the stub drifted from
  `opendssdirect`'s actual behaviour, every existing test would still have passed.
  `tests/grid/test_qsts_finance_real_solver_e2e.py` closes that gap with no monkeypatch on
  the solver seam.
- **The real solver agrees with the stub, and that agreement is now pinned** — driven on the
  same demo physics the stubbed suite uses (4 h at 120 MW against a 100 MW cap = 80 MWh shed
  on 1,000 MWh gross), the real OpenDSS solve returns **exactly the 8.0 %** self-curtailment
  the stubbed suite pins as `DEMO_SELF_CURTAILMENT_DECIMAL`. Divergence between the two now
  fails a test instead of passing silently.
- **Covered end-to-end**: the composed `curtailment_pct` equals the demo self share; every
  headline KPI (projIRR, eqIRR, CFADS, NPV, max debt) moves down and correctly signed; the
  committed canon is untouched when only `finance_wiring.enabled` is off (proving the QSTS
  block alone is inert, which is why the flag can sit unflipped); and deemed-paid
  (grid-instructed) curtailment is revenue-neutral through the real chain, as the CEB SPPA
  requires.
- **andes is exercised and proven NOT to reach finance** — it ships in the lock alongside
  opendssdirect since the 3.12 migration, so the ride-through study is run here. Unlike the
  QSTS path it has no finance seam (grep-confirmed: no `ride_through` import under
  `finance/`), and the test states that intentionally so a future wiring of ride-through
  into finance has to break this test first.
- DEMO evidence only: the feeder is a synthetic 3-bus radial with no site physics. The
  deltas quantify the WIRING, never DutchBay curtailment — #923 stays user-gated on a real
  feeder model, a `kpi_oracle` before/after diff and explicit sign-off.

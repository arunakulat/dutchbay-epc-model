# Independent PySAM energy cross-check of the lender case's wind energy (#1888)

**Result.** NREL PySAM, run on the lender case's own declared inputs, reproduces the
committed wind energy to within 0.03%. The agreement band is 0.5%.

| Figure (14 turbines) | Committed (GWh) | PySAM (GWh) | Difference |
|---|---|---|---|
| Gross energy | 517.2 | 517.2889 | +0.0172% |
| Modelled net energy (after the loss stack) | 442.1 | 442.1588 | +0.0133% |
| Bankable net P50 (after the 2.0% haircut) | 433.2 | 433.3156 | +0.0267% |
| Control: gross with the density shift left out | 517.2 | 539.5746 | +4.3261% (fails, as it should) |

The record is [`pysam_energy_crosscheck_1888.json`](pysam_energy_crosscheck_1888.json). It is
an assurance record, not a KPI, and it is not lender-facing. It changes no input or output
of any scenario. The committed figures in the table are the AEP summary's own one-decimal
values, so part of each difference is rounding.

## What was compared

- **Subject.** `scenarios/dutchbay_lendercase_2025Q4.yaml` and the AEP summary it consumes,
  `scenarios/aep_summary_dutchbay_10mw.json`. The machine is the IEA Wind Task 37 10 MW
  reference turbine, a public BSD-3 curve from the repository's power-curve store.
- **Repository method.** An analytic Weibull integral over the density-shifted power
  curve (`wind_resource.aep_integral.gross_aep_farm_gwh`, a trapezoid on a 0.05 m/s grid),
  then a multiplicative loss stack (wake, availability, electrical, curtailment, other),
  then a 2.0% P50 haircut.
- **Independent method.** PySAM `Windpower` 7.1.1.post1 in Weibull mode. No repository
  energy code runs. The runner reads the scenario and the curve store as plain data and
  passes PySAM the declared Weibull shape and mean speed at the fit height, the shear, the
  hub height and rotor, the curve, and the five declared losses mapped one to one onto
  PySAM's loss inputs (the wake loss as PySAM's constant internal wake loss). PySAM applies
  its losses multiplicatively, as the repository does. The haircut, which PySAM has no
  input for, is applied to PySAM's net afterwards.

## Two things PySAM needs that are easy to get wrong

1. **Air density.** PySAM's Weibull mode has no air-density input. The runner shifts the
   curve to site density itself, with the IEC 61400-12-1 velocity factor
   `(rho_site / rho_ref) ** (1/3)`, before handing it to PySAM. The control run shows what
   leaving this out does: gross energy rises 4.3% and fails the band.
2. **Curve grid.** SAM's Weibull sum (`windPowerUsingWeibull` in NREL's `ssc`) pairs each
   curve point with the probability of a fixed 0.25 m/s bin centred on it. A curve on any
   other grid is mis-weighted: the store's own 20-point curve gave 558.9 GWh gross (+8%),
   and a 0.05 m/s grid gave 503.8 GWh (-2.6%). The runner therefore resamples the curve
   linearly onto a uniform 0.25 m/s grid, which is the grid SAM's own turbine library uses.
   On that grid PySAM's midpoint sum and the repository's trapezoid agree to 0.02%.

## Dependency decision

PySAM is not a dependency of this repository. The owner's choice on 2026-11-22 was an
out-of-repo run pinned by SHA-256, which keeps this change R1 and leaves the lock untouched.
The run used the `nrel_pysam-7.1.1.post1-cp312-cp312-manylinux2014_x86_64.whl` wheel
(SHA-256 `27c965f0f8be6afb1d8625250fc4c3973a408b8c368d657eb3cd22f02a1c82e0`, BSD 3-Clause, no
dependencies), installed with `--no-deps --target` into a throwaway directory beside the
repository's Python 3.12 environment. The runner refuses any other PySAM release.

## Keeping the record honest

`tests/wind/test_pysam_energy_crosscheck_1888.py` needs no PySAM. It fails when any declared
energy input changes (it re-reads them and compares them and their SHA-256 with the record),
when the runner or its config changes, when the committed AEP summary changes, when the
record's differences do not follow from its own figures or leave the band, or when the
control stops failing. A hostile control changes the Weibull scale by 0.01 m/s in a copy of
the scenario and shows the digest moves. Where the pinned PySAM release is importable, one
more test re-runs PySAM and requires the record exactly; elsewhere it is skipped.

To re-run after a change to any of those inputs:

```bash
pip install --no-deps --target /tmp/pysam-site NREL-PySAM==7.1.1.post1
PYTHONPATH=.:/tmp/pysam-site .venv/bin/python scripts/run_pysam_energy_crosscheck.py \
    crosscheck.summary_json=docs/wind/pysam_energy_crosscheck_1888.json
```

## What this does not check

- **Wake.** The declared wake loss is passed to PySAM as a constant, so this record checks
  the energy arithmetic around the wake figure, not the figure itself. The gap between the
  frozen wake loss and the live wake model is the subject of #1589 and its investigation
  (`dutchbay_wake_loss_gap_investigation_1589.md`). A PySAM wake-model run on the recorded
  layout would be a separate, independent check of that figure.
- **The resource.** The Weibull fit itself is an input here. The fit's basis and its
  screening-grade status are recorded in the scenario and in `config/report_defaults.yaml`.
- **Finance.** PySAM's financial modules are not used. This record covers energy only.

HOLD union unchanged: F-5, #1110, v15.6.1.

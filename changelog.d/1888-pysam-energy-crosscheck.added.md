- **Independent PySAM energy cross-check (#1888).** `scripts/run_pysam_energy_crosscheck.py`
  recomputes the lender case's gross, modelled net and bankable net wind energy with NREL
  PySAM `Windpower` from the scenario's own declared inputs. The record,
  `docs/wind/pysam_energy_crosscheck_1888.json`, agrees with the committed AEP summary to
  within 0.03% against a 0.5% band, and its control (no density shift) fails as it should.
  PySAM stays out of the lock: the run is out-of-repo, pinned by SHA-256, and
  `tests/wind/test_pysam_energy_crosscheck_1888.py` fails when the record goes stale. No KPI
  or scenario output changes.

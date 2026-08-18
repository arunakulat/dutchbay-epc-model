### Added

- Add Dolphin #923-B1: a deterministic, manifest-bound synthetic OpenDSS feeder and
  8,760-hour generation-profile generator, exposed through the governed Hydra entry
  point under `scripts/`, for software-wiring tests while the real CEB feeder is
  unavailable. Every file is explicitly generated, non-observed,
  non-site-representative, non-bankable, noncanonical, and zero-weight for issue or
  finding closure. The seeded hourly chronology is calibrated only to a hashed
  ERA5-derived summary, is machine-labelled `synthetic_era5_summary_calibrated`, and is
  not represented as actual 2021 ERA5 data. Its controlled user-authorisation addendum is
  hash-bound in the manifest. This slice does not run finance, change canon, prove
  convergence, publish lender results, or close #923.

# Quarantined tests

These tests were moved here because they violate current v14 contracts:
- absolute IRR band asserts without explicit frozen regression labeling
- legacy assumptions about project_irr location
- legacy Monte Carlo API usage (config_path=)

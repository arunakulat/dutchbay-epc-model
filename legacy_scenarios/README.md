# Legacy Scenarios Archive

**Date:** 2025-12-13
**Reason:** Cleanup for v14 focus

This directory contains:
- Old quarterly scenario variants (e.g., 2025Q3)
- Experimental edge case scenarios
- Legacy example scenarios

## Status

These scenarios are kept for **historical reference only**.

For v14 production work, use current scenarios:
- `scenarios/dutchbay_lendercase_2025Q4.yaml` - Current lender case
- `scenarios/dutchbay_optimistic_2025Q4.yaml` - Upside scenario
- `scenarios/dutchbay_pessimistic_2025Q4.yaml` - Downside scenario

## `dutchbay_lendercase_2025Q4_15_turbines.yaml` (#1577)

The canonical lender case as it stood at `39048e89` (15.22.0), byte-for-byte, before DutchBay
dropped from 15 to 14 turbines when the Blue Whale turbine took T2's position. It is **not** a
scenario and is not run by the model. The #923 synthetic feeder placeholder
(`conf/synthetic_feeder_placeholder.yaml`) pins it by SHA-256 as its wiring basis, because the
package exists to exercise a 150 MW export cap that the 14-turbine, 148.9 MW plant never
reaches. Do not edit it: its hash is pinned, and the live lender case is
`scenarios/dutchbay_lendercase_2025Q4.yaml`.

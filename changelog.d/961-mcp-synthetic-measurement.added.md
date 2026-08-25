- **`wind_resource/mcp.py` now has a production consumer, inside the governed synthetic lane
  (#961)** — measure-correlate-predict has been implemented but unwired since it was written,
  because DutchBay has no on-site mast to correlate against. A new
  `wind_resource/synthetic_mcp_measurement.py` supplies a deterministically generated one, so
  the MCP path is exercised, typed and tested before the blocked real-evidence chain
  (#1075 → #1076 → #1078) lands. The generated series is not a measurement and carries a
  config-declared planted bias rather than any discovered site property. Output is a
  `SyntheticMCPMeasurementRecord`, which is finance-ineligible by contract: it cannot be
  relabelled canonical, cannot shed the mandatory synthetic warning, shares no field name
  with the canonical wind interface, and is refused by `require_canonical_wind_measurement`.

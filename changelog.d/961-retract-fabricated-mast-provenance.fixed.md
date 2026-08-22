- **Retracted a fabricated met-mast provenance claim from the lender-facing scenario set
  (#961)** — ten tracked files asserted
  `data_confidence: "Medium (5-year ERA5 validated against 1-year met mast)"`, describing a
  one-year on-site measurement campaign that has never existed, and
  `docs/WIND_AEP_CHAIN_OF_CUSTODY.md` quoted that string back as corroborating evidence in a
  lender-DD register. All ten now record the true screening-grade / pre-measurement basis: no
  on-site met mast or IEC-accepted LiDAR/SoDAR, and the MCP long-term correction present in
  `wind_resource/mcp.py` but unwired. The register's red flag R5 is corrected — it had cited
  "no MCP module" as evidence, which was false in the opposite direction — and regraded
  Medium to High to match the `high` severity `config/report_defaults.yaml` already assigns
  the same Resource risk. No numeric value changed anywhere; the canonical KPIs are unmoved.

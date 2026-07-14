# EPC Cost-Basis Parameters (partial schema)

This file documents only the four EPC cost-basis parameters below. It is not the full model
input contract. The authoritative, strictly validated configuration surface (FX, tax, debt,
financing terms, generation technologies, wind, solar, and grid blocks) is defined and
enforced in code:

- `analytics/config_schema.py` — the configuration schema.
- `analytics/schema_guard.py` — the strict pre-flight validator (`validate_config_for_v14`).
- `analytics/scenario_loader.py` — the scenario loader.
- `scenarios/*.yaml` — worked example scenarios (see `scenarios/dutchbay_lendercase_2025Q4.yaml`).

Field naming follows the units convention: `*_usd`, `*_lkr`, `*_pct`, `*_years` (see GWTF
rule FIN-02).

## EPC cost-basis parameters

| Key | Units | Range | Notes |
| --- | --- | --- | --- |
| `base_cost_usd` | USD | [1, 1e10] | Base EPC cost in USD |
| `freight_pct` | fraction | [0, 1] | Freight as a fraction of base EPC |
| `contingency_pct` | fraction | [0, 1] | Contingency as a fraction of (base + freight) |
| `fx_rate` | LCY/USD | (0, 1e6] | Local currency per USD |

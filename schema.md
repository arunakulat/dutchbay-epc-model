# Parameters Schema

## EPC Parameters

| Key              | Units   | Range               | Notes                                        |
|------------------|---------|---------------------|----------------------------------------------|
| base_cost_usd    | USD     | [1, 1e10]           | Base EPC cost in USD                         |
| freight_pct      | fraction| [0, 1]              | Freight as fraction of base EPC              |
| contingency_pct  | fraction| [0, 1]              | Contingency as fraction of (base+freight)    |
| fx_rate          | LCY/USD | (0, 1e6]            | Local currency per USD                       |

# Analytics Master Suite

Batch scenario analytics and board-ready Excel reporting for DutchBay EPC Model.

## Quick Start

```bash
# Run analytics on all scenarios in ./scenarios directory
python analytics/scenario_analytics.py \
  --dir ./scenarios \
  --output ./exports/DutchBay_Report_$(date +%Y%m%d).xlsx
```

## Features

- **Batch Scenario Processing**: Process multiple scenario configs in one run
- **KPI Calculation**: NPV, IRR, DSCR statistics, debt metrics, CFADS aggregates
- **Excel Export**: Multi-sheet workbook with formatting, conditional formatting, embedded charts
- **QC Diagnostics**: Automated checks for DSCR violations, negative CFADS, failed calculations
- **Visualization**: DSCR comparison, debt waterfall, NPV/IRR bar charts
- **CSV Backups**: Long and wide format CSV exports for external analysis

## Installation

```bash
# Install dependencies (from project root)
pip install -e .[dev]

# Or manually install analytics dependencies
pip install openpyxl matplotlib pyyaml scipy
```

## Usage

### Basic Usage

```bash
python analytics/scenario_analytics.py \
  --dir ./scenarios \
  --output ./exports/report.xlsx
```

### Custom Discount Rate and DSCR Threshold

```bash
python analytics/scenario_analytics.py \
  --dir ./scenarios \
  --output ./exports/report.xlsx \
  --discount 0.10 \
  --dscr 1.30
```

### Skip Charts for Faster Processing

```bash
python analytics/scenario_analytics.py \
  --dir ./scenarios \
  --output ./exports/report.xlsx \
  --no-charts
```

### Skip CSV Backups

```bash
python analytics/scenario_analytics.py \
  --dir ./scenarios \
  --output ./exports/report.xlsx \
  --no-csv
```

## Command-Line Options

| Option | Short | Description | Default |
|--------|-------|-------------|--------|
| `--dir` | `-d` | Directory containing scenario YAML/JSON files | Required |
| `--output` | `-o` | Output Excel file path | Required |
| `--discount` | `-r` | Discount rate for NPV calculations | 0.08 |
| `--dscr` | `-t` | DSCR threshold for QC checks | 1.25 |
| `--no-charts` | | Skip chart generation | False |
| `--no-csv` | | Skip CSV backup exports | False |

## Output Structure

### Excel Workbook

The generated Excel file contains multiple sheets:

#### 1. Summary Sheet
- One row per scenario
- Columns: scenario name, NPV, IRR, DSCR stats, debt stats, CFADS stats
- Conditional formatting: Red cells for DSCR < threshold
- Auto-filter enabled
- Frozen header row

#### 2. Timeseries_Long Sheet
- Long format: one row per scenario-year
- Columns: scenario, year, label, revenue, opex, cfads, dscr, debt_outstanding
- Ideal for time-series analysis and plotting

#### 3. Wide_Format Sheet
- Wide format: one row per scenario, columns for each year
- Columns: scenario, cfads_y1, cfads_y2, ..., dscr_y1, dscr_y2, ..., debt_y1, debt_y2, ...
- Ideal for Excel pivot tables and crosstab analysis

#### 4. Charts Sheet
- Embedded PNG images of all generated charts
- DSCR comparison line chart
- Debt waterfall chart
- NPV comparison bar chart
- IRR comparison bar chart

### CSV Backups

- `scenario_summary.csv`: Summary sheet in CSV format
- `scenario_timeseries.csv`: Timeseries_Long sheet in CSV format

### Chart Files

All charts saved as PNG in `./exports/charts/` directory:
- `dscr_comparison.png`
- `debt_waterfall.png`
- `npv_comparison.png`
- `irr_comparison.png`

## Module Architecture

```
analytics/
├── __init__.py                  # Package metadata
├── README.md                    # This file
├── scenario_analytics.py        # Main orchestrator (CLI entry point)
├── core/
│   ├── __init__.py
│   └── metrics.py               # KPI calculations (NPV, IRR, DSCR)
└── export_helpers.py            # Excel export and chart generation
```

### Core Modules

#### `scenario_analytics.py`
Main orchestrator that:
1. Loads all scenario configs from directory
2. Processes each scenario through finance engine
3. Calculates KPIs using `metrics.py`
4. Aggregates results into DataFrames
5. Runs QC diagnostics
6. Generates charts using `export_helpers.py`
7. Exports to Excel and CSV

#### `core/metrics.py`
Financial metrics calculations:
- `calculate_npv()`: Net Present Value
- `calculate_irr()`: Internal Rate of Return
- `calculate_dscr_stats()`: DSCR min/max/mean/median
- `calculate_debt_stats()`: Max and final debt outstanding
- `calculate_cfads_stats()`: Total, final, and mean operational CFADS
- `calculate_scenario_kpis()`: Comprehensive KPI calculation
- `format_kpi_summary()`: Human-readable text summary

#### `export_helpers.py`
Excel and chart utilities:
- `ExcelExporter`: Multi-sheet Excel workbook creation with formatting
  - Header styling (bold, colored background)
  - Freeze panes
  - Auto-filter
  - Conditional formatting
  - Chart image embedding
  - Auto-width columns
- `ChartGenerator`: Matplotlib chart generation
  - DSCR comparison line charts
  - Debt waterfall charts
  - KPI bar charts
  - NPV distribution histograms

## Integration with Existing Code

The analytics suite integrates with existing DutchBay v14 modules:

```python
from dutchbay_v14chat.finance.cashflow import build_annual_rows_v14
from dutchbay_v14chat.finance.debt import apply_debt_layer
```

No modifications to existing finance modules required.

## API Contracts

### Input: Scenario Config Files

Supported formats: `.json`, `.yaml`, `.yml`

Expected structure (same as existing DutchBay configs):
```yaml
# Scenario config structure depends on your model
# No changes required to existing configs
```

### Output: Scenario KPIs

The `calculate_scenario_kpis()` function returns:
```python
{
    "npv": float,                      # Net Present Value (USD)
    "irr": float,                      # Internal Rate of Return (decimal)
    "dscr_min": float,                 # Minimum DSCR across all years
    "dscr_max": float,                 # Maximum DSCR
    "dscr_mean": float,                # Mean DSCR
    "dscr_median": float,              # Median DSCR
    "max_debt_outstanding": float,     # Peak debt (USD)
    "final_debt_outstanding": float,   # Final year debt (USD)
    "total_cfads": float,              # Sum of all CFADS (USD)
    "final_cfads": float,              # Last year CFADS (USD)
    "mean_operational_cfads": float,   # Mean CFADS for operational years
    "total_idc_capitalized": float,    # Total interest during construction
    "grace_years": int,                # Number of grace periods
    "timeline_periods": int            # Total project years
}
```

## QC Diagnostics

Automated checks performed:

1. **DSCR Violations**: Flags scenarios where minimum DSCR < threshold
2. **Negative Final CFADS**: Identifies scenarios with negative last-year CFADS
3. **Failed IRR Calculations**: Reports scenarios where IRR couldn't be computed
4. **Failed Scenarios**: Lists scenarios that errored during processing

All diagnostics printed to console and visible in Excel conditional formatting.

## Extending the Suite

### Adding New KPIs

Edit `analytics/core/metrics.py`:

```python
def calculate_my_custom_kpi(annual_rows, debt_result):
    # Your calculation logic
    return value

# Add to calculate_scenario_kpis():
kpis["my_custom_kpi"] = calculate_my_custom_kpi(annual_rows, debt_result)
```

### Adding New Charts

Edit `analytics/export_helpers.py`:

```python
class ChartGenerator:
    def plot_my_custom_chart(self, data, output_file):
        # Your matplotlib code
        plt.savefig(os.path.join(self.output_dir, output_file))
        return output_path
```

Then call in `scenario_analytics.py`:

```python
chart_paths['my_chart'] = self.chart_gen.plot_my_custom_chart(data, 'my_chart.png')
```

## Troubleshooting

### Import Errors

```bash
# Ensure parent directory is in Python path
export PYTHONPATH="/Users/aruna/Desktop/DutchBay_EPC_Extracted/DutchBay_EPC_Model:$PYTHONPATH"

# Or run from project root
cd /Users/aruna/Desktop/DutchBay_EPC_Extracted/DutchBay_EPC_Model
python analytics/scenario_analytics.py --dir ./scenarios --output ./exports/report.xlsx
```

### Missing Dependencies

```bash
pip install openpyxl matplotlib pyyaml scipy numpy-financial
```

### Chart Display Issues

If charts aren't displaying in Excel:
- Ensure PNG files exist in `exports/charts/`
- Check file permissions
- Verify openpyxl version >= 3.1

### Performance Issues

For large scenario sets (50+ scenarios):
- Use `--no-charts` to skip chart generation
- Process scenarios in smaller batches
- Consider parallelization (future enhancement)

## Future Enhancements

Planned features:

- [ ] Monte Carlo module (`analytics/montecarlo.py`)
- [ ] Optimization module (`analytics/optimization.py`)
- [ ] Sensitivity analysis module (`analytics/sensitivity_analysis.py`)
- [ ] Parallel scenario processing
- [ ] PDF report generation
- [ ] Interactive HTML dashboards
- [ ] Integration with CI/CD pipeline

## Support

For issues or questions:
1. Check existing scenario configs are valid YAML/JSON
2. Verify finance engine runs successfully on individual scenarios
3. Review console output for detailed error messages
4. Check `exports/` directory permissions

## License

Same as parent DutchBay project.

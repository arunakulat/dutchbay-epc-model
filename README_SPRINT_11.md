# Sprint 11: Tax Profile v14 Implementation

**Status:** ✅ Complete and Deployed

## What's New

### Tax Module (v14)
- 12-year tax holiday (0% rate, Years 1-12)
- Full corporate taxation (30% rate, Years 13-20)
- 15-year straight-line depreciation
- Statutory deductions (4% of revenue)
- Loss carryforward (25 years)

### Tests
- 11 regression tests: `tests/api/test_tax_v14_regression.py`
- 13 compliance tests: `tests/lint/test_tax_module_compliance.py`
- All 26 tests passing (✅ 100%)

### Performance
- Monte Carlo: 1500x faster
- Dev mode: 50 iterations
- Prod mode: 3000 iterations

## Key Metrics

| Metric | Value |
|--------|-------|
| Project IRR | 17.88% |
| Project NPV | LKR 55.3B |
| Min DSCR | 1.30 |
| Debt Repaid | Year 13 |

## Quick Start

```bash
# Run tests
pytest tests/api/test_tax_v14_regression.py -v

# Run pipeline
python run_full_pipeline_v14.py config=scenarios/dutchbay_lendercase_2025Q4.yaml
```

## Documentation

- `SPRINT_11_COMPLETE.md` - Overview
- `ANALYSIS_SUMMARY.md` - Detailed analysis
- `SPRINT_11_FINAL_DELIVERY.md` - Completion report
- `VERIFICATION_CHECKLIST.md` - Verification status

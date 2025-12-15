#!/usr/bin/env python3
import json
from pathlib import Path

"""
QUICK REFERENCE: Running the Swimlane 1 Inspector
==================================================

This file provides copy-paste ready commands to run the inspection.
No modifications needed - just execute!
"""

# ============================================================================
# COMMAND 1: BASIC INSPECTION (Recommended)
# ============================================================================
"""
WHAT IT DOES:
  ✅ Extracts WaccResult and EquityResult contract fields
  ✅ Analyzes test coverage for both modules
  ✅ Runs performance benchmarks (1000 scenarios)
  ✅ Verifies governance compliance (CCCDIR/CESSPIT/CASPER/GWTF)
  ✅ Generates JSON report for sharing

EXECUTION:
  cd /path/to/dutchbay-epc-model
  python swimlane1_inspector.py

OUTPUT:
  • Console: Summary with ✅/❌ status
  • File: swimlane1_inspection_report.json (detailed results)

TIME: ~5-10 minutes
"""


# ============================================================================
# COMMAND 2: RUN INSPECTION + VIEW REPORT
# ============================================================================
"""
WHAT IT DOES:
  Runs inspection AND displays JSON report in terminal

EXECUTION (Linux/Mac):
  cd /path/to/dutchbay-epc-model && \
  python swimlane1_inspector.py && \
  cat swimlane1_inspection_report.json | python -m json.tool

EXECUTION (Windows PowerShell):
  cd C:\path\to\dutchbay-epc-model; `
  python swimlane1_inspector.py; `
  Get-Content swimlane1_inspection_report.json | ConvertFrom-Json | ConvertTo-Json

EXECUTION (Python):
  import json
  with open('swimlane1_inspection_report.json') as f:
      report = json.load(f)
      print(json.dumps(report, indent=2))
"""


# ============================================================================
# COMMAND 3: PROGRAMMATIC USAGE (for automation)
# ============================================================================
"""
WHAT IT DOES:
  Integrates inspector into your own Python scripts

CODE:
  from swimlane1_inspector import Swimlane1Inspector

  # Run inspection
  inspector = Swimlane1Inspector()
  report = inspector.run_full_inspection()

  # Access results programmatically
  wacc_fields = [f.name for f in report.wacc_contract.fields]
  equity_coverage = report.equity_test_coverage.coverage_percentage
  governance_ok = all(report.governance_checks.values())

  # Export
  inspector.export_report_json("my_report.json")

  # Make decisions
  if governance_ok and equity_coverage >= 80:
      print("✅ Ready for Phase 3 integration")
  else:
      print("⚠️  Address issues before Phase 3")
"""


# ============================================================================
# COMMAND 4: CHECK SPECIFIC MODULE ONLY
# ============================================================================
"""
WHAT IT DOES:
  Inspect only WACC or only Equity (for faster feedback)

CODE - WACC Only:
  from swimlane1_inspector import Swimlane1Inspector

  inspector = Swimlane1Inspector()
  inspector.inspect_wacc_engine()
  inspector.verify_governance()
  inspector.generate_recommendations()
  inspector.export_report_json("wacc_only_report.json")

CODE - Equity Only:
  from swimlane1_inspector import Swimlane1Inspector

  inspector = Swimlane1Inspector()
  inspector.inspect_equity_analytics()
  inspector.verify_governance()
  inspector.generate_recommendations()
  inspector.export_report_json("equity_only_report.json")
"""


# ============================================================================
# COMMAND 5: PARSE AND SUMMARIZE RESULTS
# ============================================================================
"""
WHAT IT DOES:
  Read the JSON report and print human-readable summary

PYTHON SCRIPT (save as summarize_report.py):
"""


def summarize_swimlane1_report(report_file: str = "swimlane1_inspection_report.json"):
    """Pretty-print Swimlane 1 inspection report."""

    if not Path(report_file).exists():
        print(f"❌ Report not found: {report_file}")
        print("   Run: python swimlane1_inspector.py")
        return

    with open(report_file) as f:
        report = json.load(f)

    print("\n" + "=" * 80)
    print("📊 SWIMLANE 1 INSPECTION SUMMARY")
    print("=" * 80 + "\n")

    # WACC Results
    print("🔹 SL-1.1: WACC ENGINE")
    print("-" * 80)
    if report.get("wacc_contract"):
        wacc = report["wacc_contract"]
        print(f"  Contract: {wacc['class_name']}")
        print(f"  Fields: {len(wacc['fields'])}")
        for field in wacc["fields"]:
            optional = " (optional)" if field["is_optional"] else ""
            print(f"    • {field['name']}: {field['type_annotation']}{optional}")
        print(f"  Frozen: {wacc['is_frozen']}")
    else:
        print("  ❌ Contract not found")

    if report.get("wacc_test_coverage"):
        tests = report["wacc_test_coverage"]
        pct = tests["coverage_percentage"]
        status = "✅" if pct >= 80 else "⚠️" if pct >= 60 else "❌"
        print(
            f"  Tests: {tests['passing_tests']}/{tests['total_tests']} passing {status}"
        )
        print(f"  Coverage: {pct:.1f}%")
        if tests["edge_case_test_names"]:
            print(f"  Edge Cases: {len(tests['edge_case_test_names'])} tests")

    if report.get("wacc_performance"):
        perf = report["wacc_performance"]
        sla = "✅" if perf["is_within_sla"] else "❌"
        print(
            f"  Performance: {perf['execution_time_ms']:.0f}ms (1000 scenarios) {sla}"
        )

    # Equity Results
    print("\n🔹 SL-1.2: EQUITY ANALYTICS")
    print("-" * 80)
    if report.get("equity_contract"):
        equity = report["equity_contract"]
        print(f"  Contract: {equity['class_name']}")
        print(f"  Fields: {len(equity['fields'])}")
        for field in equity["fields"]:
            optional = " (optional)" if field["is_optional"] else ""
            print(f"    • {field['name']}: {field['type_annotation']}{optional}")
        print(f"  Frozen: {equity['is_frozen']}")
    else:
        print("  ❌ Contract not found")

    if report.get("equity_test_coverage"):
        tests = report["equity_test_coverage"]
        pct = tests["coverage_percentage"]
        status = "✅" if pct >= 80 else "⚠️" if pct >= 60 else "❌"
        print(
            f"  Tests: {tests['passing_tests']}/{tests['total_tests']} passing {status}"
        )
        print(f"  Coverage: {pct:.1f}%")
        if tests["edge_case_test_names"]:
            print(f"  Edge Cases: {len(tests['edge_case_test_names'])} tests")

    if report.get("equity_performance"):
        perf = report["equity_performance"]
        sla = "✅" if perf["is_within_sla"] else "❌"
        print(
            f"  Performance: {perf['execution_time_ms']:.0f}ms (1000 scenarios) {sla}"
        )

    # Governance
    print("\n🛡️  GOVERNANCE COMPLIANCE")
    print("-" * 80)
    checks = report.get("governance_checks", {})
    for check, is_ok in checks.items():
        status = "✅" if is_ok else "❌"
        print(f"  {status} {check}")

    all_ok = all(checks.values())
    if all_ok:
        print("\n  ✅ ALL GOVERNANCE CHECKS PASSED")
    else:
        print("\n  ❌ GOVERNANCE ISSUES DETECTED (see below)")

    # Issues & Recommendations
    print("\n📋 ISSUES FOUND")
    print("-" * 80)
    issues = report.get("issues_found", [])
    if issues:
        for issue in issues:
            print(f"  ⚠️  {issue}")
    else:
        print("  ✅ No issues found")

    print("\n💡 RECOMMENDATIONS")
    print("-" * 80)
    recs = report.get("recommendations", [])
    if recs:
        for rec in recs:
            print(f"  📌 {rec}")
    else:
        print("  ✅ No recommendations (ready for Phase 3)")

    # Final Status
    print("\n" + "=" * 80)
    wacc_ok = (
        report.get("wacc_contract")
        and report.get("wacc_test_coverage", {}).get("coverage_percentage", 0) >= 80
    )
    equity_ok = (
        report.get("equity_contract")
        and report.get("equity_test_coverage", {}).get("coverage_percentage", 0) >= 80
    )

    if wacc_ok and equity_ok and all_ok and not issues:
        print("✅ READY FOR PHASE 3 INTEGRATION")
    elif wacc_ok and equity_ok and all_ok:
        print("⚠️  READY WITH MINOR ACTIONS (see recommendations)")
    else:
        print("❌ NOT READY - ADDRESS ISSUES BEFORE PHASE 3")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    summarize_swimlane1_report()


"""
USAGE:
  python summarize_report.py
"""


# ============================================================================
# COMMAND 6: INTEGRATION WITH CI/CD
# ============================================================================
"""
WHAT IT DOES:
  Add inspection to your CI/CD pipeline (GitHub Actions example)

GITHUB ACTIONS WORKFLOW (.github/workflows/swimlane1-check.yml):

  name: Swimlane 1 Inspection

  on:
    push:
      paths:
        - 'finance/wacc_v14.py'
        - 'finance/equity_v14.py'
        - 'tests/finance/test_wacc_*.py'
        - 'tests/finance/test_equity_*.py'

  jobs:
    inspect:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v3
        - uses: actions/setup-python@v4
          with:
            python-version: '3.11'
        - run: python swimlane1_inspector.py
        - run: python summarize_report.py
        - uses: actions/upload-artifact@v3
          with:
            name: inspection-report
            path: swimlane1_inspection_report.json
"""


# ============================================================================
# CHECKLIST: INTERPRETING RESULTS
# ============================================================================
"""
After running the inspector, check these boxes:

CONTRACT FIELDS:
  □ WaccResult has ≥ 6 required fields
  □ EquityResult has ≥ 4 required fields
  □ All fields properly typed (float, int, List[float], etc.)
  □ No Dict[str, Any] fields
  □ All frozen=True

TEST COVERAGE:
  □ WACC coverage ≥ 80%
  □ Equity coverage ≥ 80%
  □ Both have edge case tests
  □ Passing tests ≥ 95%

PERFORMANCE:
  □ WACC execution ≤ 5000ms for 1000 scenarios
  □ Equity execution ≤ 5000ms for 1000 scenarios
  □ Both is_within_sla = True

GOVERNANCE:
  □ CCCDIR:typed_contracts = True
  □ CCCDIR:no_dict_passthrough = True
  □ CCCDIR:dataclass_frozen = True
  □ CESSPIT:config_validation = True
  □ CESSPIT:schema_guard_calls = True
  □ CASPER:audit_trail = True
  □ GWTF:no_forbidden_imports = True
  □ GWTF:gateway_compliant = True

OVERALL DECISION:
  □ All checks above = True? → ✅ READY FOR PHASE 3
  □ Some warnings? → ⚠️ Review recommendations, address, re-run
  □ Any critical issues? → ❌ STOP, coordinate with Swimlane 1
"""


# ============================================================================
# TROUBLESHOOTING
# ============================================================================
"""
PROBLEM: "Module not found" or "FileNotFoundError"
SOLUTION: Run from repo root directory
  cd /path/to/dutchbay-epc-model
  python swimlane1_inspector.py

PROBLEM: "pytest command not found"
SOLUTION: Install pytest
  pip install pytest
  Then re-run: python swimlane1_inspector.py

PROBLEM: Tests failing / coverage low
SOLUTION: This is expected! That's why we inspect.
  • Review RECOMMENDATIONS section in JSON report
  • Share with Swimlane 1 team for fixes
  • Re-run after they address issues

PROBLEM: "WaccResult not found"
SOLUTION: Check if contract is named differently
  • Edit swimlane1_inspector.py line 245:
    "WaccResult" → actual class name
  • Or search codebase: grep -r "class.*Result" finance/

PROBLEM: Performance times very high
SOLUTION: Expected if running on slow hardware
  • Adjust SLA: modify sla_ms parameter
  • Or run with fewer scenarios for quick check
"""


# ============================================================================
# FINAL CHECKLIST
# ============================================================================
"""
✅ All Tasks to Get Swimlane 1 Ready:

1. IMMEDIATE (Now):
   □ cp swimlane1_inspector.py /path/to/dutchbay-epc-model
   □ cd /path/to/dutchbay-epc-model
   □ python swimlane1_inspector.py
   □ Review console output
   □ Open swimlane1_inspection_report.json

2. ANALYSIS (Next 30 minutes):
   □ Run summarize_report.py
   □ Fill out CHECKLIST section above
   □ Note any issues or warnings
   □ Calculate readiness score (0-10)

3. DECISION (Next 1 hour):
   □ If score ≥ 8: Proceed to Phase 3 (schedule kickoff)
   □ If score 5-7: Review recommendations (2-3 day fix)
   □ If score < 5: STOP, coordinate with Swimlane 1 team

4. SHARING (End of day):
   □ Share swimlane1_inspection_report.json with stakeholders
   □ Present findings in standup
   □ Get go/no-go decision for Phase 3
"""

print(__doc__)

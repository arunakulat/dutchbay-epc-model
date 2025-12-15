#!/usr/bin/env python
"""Test script to verify all Sprint 9 imports are working."""

import sys
from pathlib import Path

print("\n" + "=" * 60)
print("SPRINT 9 IMPORT VERIFICATION")
print("=" * 60 + "\n")

test_results = []

# Test 1: evaluation_v14_legacy
print("Test 1: evaluation_v14_legacy")
try:
    from analytics.evaluation_v14_legacy import evaluatewithoverrides

    print("✅ SUCCESS: evaluatewithoverrides imported\n")
    test_results.append(("evaluation_v14_legacy", True))
except Exception as e:
    print(f"❌ FAILED: {e}\n")
    test_results.append(("evaluation_v14_legacy", False))

# Test 2: exports
print("Test 2: exports")
try:
    from analytics.exports import build_executive_workbook

    print("✅ SUCCESS: build_executive_workbook imported\n")
    test_results.append(("exports", True))
except Exception as e:
    print(f"❌ FAILED: {e}\n")
    test_results.append(("exports", False))

# Test 3: scenario_loader
print("Test 3: scenario_loader")
try:
    from analytics.scenario_loader import load_scenario_config

    print("✅ SUCCESS: load_scenario_config imported\n")
    test_results.append(("scenario_loader", True))
except Exception as e:
    print(f"❌ FAILED: {e}\n")
    test_results.append(("scenario_loader", False))

# Test 4: evaluation_v14 (core)
print("Test 4: evaluation_v14 (core)")
try:
    from analytics import evaluation_v14

    print("✅ SUCCESS: evaluation_v14 module imported\n")
    test_results.append(("evaluation_v14", True))
except Exception as e:
    print(f"❌ FAILED: {e}\n")
    test_results.append(("evaluation_v14", False))

# Test 5: CASPER
print("Test 5: CASPER")
try:
    from analytics.casper import evaluate_with_casper_tail_risk_and_payload

    print("✅ SUCCESS: evaluate_with_casper_tail_risk_and_payload imported\n")
    test_results.append(("CASPER", True))
except Exception as e:
    print(f"❌ FAILED: {e}\n")
    test_results.append(("CASPER", False))

# Summary
print("=" * 60)
print("SUMMARY")
print("=" * 60)
passed = sum(1 for _, result in test_results if result)
total = len(test_results)

for name, result in test_results:
    status = "✅" if result else "❌"
    print(f"{status} {name}")

print(f"\nResult: {passed}/{total} tests passed")

if passed == total:
    print("\n🎉 ALL SPRINT 9 IMPORTS VERIFIED!")
    sys.exit(0)
else:
    print(f"\n⚠️  {total - passed} test(s) failed")
    sys.exit(1)

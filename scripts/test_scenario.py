#!/usr/bin/env python3
"""Test scenario configuration loading.

Run from project root:
    python test_scenarios.py
"""

from finance.irr_config import load_config
from finance.scenario_config import (get_scenario, get_scenario_irr_bounds,
                                     list_scenarios)


def main():
    print("=" * 70)
    print("SCENARIO CONFIGURATION TESTS")
    print("=" * 70)
    print()

    # Load config
    config = load_config()

    # List scenarios
    print("Available scenarios:")
    print("-" * 70)
    scenarios = list_scenarios(config)
    for i, s in enumerate(scenarios, 1):
        print(f"{i}. {s['name']}")
        print(f"   Title: {s['title']}")
        print(f"   Desc:  {s['description']}")
    print()

    # Test each scenario
    for scenario_name in [s["name"] for s in scenarios]:
        print("=" * 70)
        print(f"SCENARIO: {scenario_name}")
        print("=" * 70)

        scenario = get_scenario(config, scenario_name)

        print(f"Title:       {scenario.get('name')}")
        print(f"Description: {scenario.get('description')}")
        print(f"Resource:    {scenario.get('resource_assumption')}")
        print(f"Financing:   {scenario.get('financing_type')}")
        print()

        # Extract IRR bounds for each role
        for role in ["project", "equity", "debt", "xirr"]:
            lower, upper = get_scenario_irr_bounds(config, scenario_name, role)
            print(f"  {role.upper():8} IRR bounds: [{lower:6.2f}, {upper:6.2f}]")
        print()

    print("=" * 70)
    print("✅ All scenario tests passed!")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    exit(main())

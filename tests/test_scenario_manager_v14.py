from src.scenario_manager_v14 import (
    deep_merge,
    ScenarioDefinition,
    apply_scenario,
    list_scenarios,
    compare_scenarios,
)


def test_deep_merge_nested_dicts():
    base = {
        "Financing_Terms": {
            "interest_rate_nominal": 0.08,
            "min_dscr": 1.2,
        },
        "tax": {
            "corporate_tax_rate": 0.3,
        },
    }
    overlay = {
        "Financing_Terms": {
            "min_dscr": 1.3,
        },
        "tax": {
            "tax_holiday_years": 5,
        },
    }

    merged = deep_merge(base, overlay)

    assert merged["Financing_Terms"]["interest_rate_nominal"] == 0.08
    assert merged["Financing_Terms"]["min_dscr"] == 1.3
    assert merged["tax"]["corporate_tax_rate"] == 0.3
    assert merged["tax"]["tax_holiday_years"] == 5


def test_apply_scenario_and_list_scenarios():
    base = {
        "Financing_Terms": {"min_dscr": 1.2},
        "tax": {"tax_holiday_years": 0},
    }

    scenario = ScenarioDefinition(
        name="five_year_holiday",
        description="5-year tax holiday",
        overlay={"tax": {"tax_holiday_years": 5}},
    )

    applied = apply_scenario(base, scenario)

    assert applied["tax"]["tax_holiday_years"] == 5
    assert applied["Financing_Terms"]["min_dscr"] == 1.2

    listed = list_scenarios([scenario])
    assert listed == [
        {"name": "five_year_holiday", "description": "5-year tax holiday"}
    ]


def test_compare_scenarios_simple_path():
    base = {
        "Financing_Terms": {"min_dscr": 1.2},
        "tax": {"tax_holiday_years": 0},
    }

    scenarios = [
        ScenarioDefinition(
            name="holiday5",
            description="5-year holiday",
            overlay={"tax": {"tax_holiday_years": 5}},
        ),
        ScenarioDefinition(
            name="holiday7",
            description="7-year holiday",
            overlay={"tax": {"tax_holiday_years": 7}},
        ),
    ]

    comparison = compare_scenarios(
        base_config=base,
        scenarios=scenarios,
        key_path="tax.tax_holiday_years",
    )

    # First row = BASE
    assert comparison[0]["scenario"] == "BASE"
    assert comparison[0]["value"] == 0

    names = [row["scenario"] for row in comparison[1:]]
    values = [row["value"] for row in comparison[1:]]

    assert names == ["holiday5", "holiday7"]
    assert values == [5, 7]

    
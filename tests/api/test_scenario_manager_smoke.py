#!/usr/bin/env python3
"""
Smoke tests for the v14 ScenarioManager.

Goals:
- Prove that ScenarioManager discovers the expected scenario files
  in the repo-level 'scenarios/' directory.
- Prove that iter_scenarios() loads the lender-case config via
  analytics.scenario_loader.load_scenario_config and returns a
  well-structured dict.

We deliberately keep these as "shape" tests: no business logic,
just invariants around discovery and loading.
"""

from pathlib import Path

from dutchbay_v14chat.finance.v14.scenario_manager import ScenarioManager


def test_iter_config_paths_includes_canonical_scenarios():
    scenarios_dir = Path("scenarios")
    assert scenarios_dir.is_dir(), "Expected 'scenarios/' directory at repo root"

    manager = ScenarioManager(scenarios_dir=scenarios_dir)
    paths = manager._iter_config_paths()

    # There should be at least a handful of scenario configs.
    assert paths, "Expected at least one scenario config path from ScenarioManager"

    stems = {p.stem for p in paths}

    expected = {
        "edge_extreme_stress",
        "example_a",
        "example_a_old",
        "example_b",
        "dutchbay_lendercase_2025Q4",
    }
    missing = expected - stems
    assert not missing, f"ScenarioManager paths missing expected scenarios: {missing}"


def test_iter_scenarios_loads_lendercase_via_loader():
    """ScenarioManager.iter_scenarios should load the lender-case via the shared loader."""
    manager = ScenarioManager(scenarios_dir="scenarios")

    # Narrow to the canonical lender-case file to keep this test tight.
    pairs = list(manager.iter_scenarios(patterns=("dutchbay_lendercase_2025Q4.yaml",)))

    assert len(pairs) == 1, "Expected exactly one lender-case scenario from ScenarioManager"
    name, config = pairs[0]

    # Name and type checks
    assert name == "dutchbay_lendercase_2025Q4"
    assert isinstance(config, dict), "Loaded config should be a dict"

    # Basic structural invariants, aligned with the confirmed lender-case YAML.
    for key in ("project", "tariff", "Financing_Terms"):
        assert key in config, f"Expected key '{key}' in lender-case config"

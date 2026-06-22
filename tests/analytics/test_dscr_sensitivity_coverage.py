#!/usr/bin/env python
"""Coverage-focused tests for ``analytics.dscr_sensitivity``.

Targets the line ranges left uncovered by ``test_dscr_sensitivity.py``:
- The constraint-transition append branch (a binding constraint actually
  changes across the perturbation sweep).
- The defensive ``else`` fall-through for an unrecognised perturbed variable
  inside ``analyze_single_variable`` (normally guarded by ``_perturb_parameter``).
- The ``main`` CLI entry point: happy path, the usage-error exit, and the
  non-mapping config ``TypeError`` guard.

These exercise real behaviour and documented raises (no import-smoke). Network /
display side effects are absent in this module, so nothing needs mocking beyond
``sys.argv`` and ``OmegaConf.load`` for the CLI path.

Author: DutchBay V14 Team (coverage backfill)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest
from omegaconf import OmegaConf

import analytics.dscr_sensitivity as dscr_mod
from analytics.dscr_sensitivity import (
    SensitivityConfig,
    analyze_dscr_sensitivity,
    analyze_single_variable,
    main,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_SCENARIO = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


def _lendercase_overlay() -> OmegaConf:
    """Build a DictConfig in the structure ``analyze_dscr_sensitivity`` reads.

    The canonical lender-case YAML stores its inputs under a different schema
    (``capex.usd_total``, ``tariff.lkr_per_kwh``, ``Financing_Terms`` …) than the
    sensitivity entry point consumes (``project.capex_usd``, ``revenue``,
    ``financing`` …). We derive the sensitivity-shaped config from the real
    scenario file so the values are anchored to the canonical case while still
    matching the function's documented config contract.

    Returns:
        OmegaConf ``DictConfig`` with the project/wind_resource/revenue/
        operations/financing/sensitivity sections the analysis requires.
    """
    raw = OmegaConf.load(CANONICAL_SCENARIO)

    capex = float(raw.capex.usd_total)
    # Net P50 AEP from the canonical case (GWh -> MWh); P99 via the documented
    # downside factor in Financing_Terms.
    aep_p50_mwh = float(raw.resource.wind.aep_gwh) * 1_000.0
    downside = float(raw.Financing_Terms.dscr_p99_downside_factor)
    aep_p99_mwh = aep_p50_mwh * downside
    # LKR/kWh -> USD/MWh via the pinned FX vintage.
    tariff_usd_mwh = (
        float(raw.tariff.lkr_per_kwh) * 1_000.0 / float(raw.fx.start_lkr_per_usd)
    )
    opex_usd_year = float(raw.opex.usd_per_year)

    return OmegaConf.create(
        {
            "project": {
                "capex_usd": capex,
                "degradation": float(raw.project.degradation),
                "life_years": int(raw.project.life_years),
            },
            "wind_resource": {
                "aep_p50_mwh": aep_p50_mwh,
                "aep_p99_mwh": aep_p99_mwh,
            },
            "revenue": {"tariff_usd_mwh": tariff_usd_mwh},
            "operations": {"opex_usd_year": opex_usd_year},
            "financing": {
                "dscr_target_p50": float(raw.Financing_Terms.target_dscr),
                "dscr_target_p99": 1.00,
                "debt_ratio_max": float(raw.Financing_Terms.debt_ratio),
                "debt_rate": float(raw.Financing_Terms.interest_rate_nominal),
            },
            "sensitivity": {"perturbation_range_pct": 20.0, "n_steps": 5},
        }
    )


class TestCanonicalScenarioDriven:
    """Drive the sweep from the canonical lender case and assert structure."""

    def test_sweep_structure_from_canonical(self) -> None:
        """Full analysis over the canonical-derived config has full structure."""
        cfg = _lendercase_overlay()

        result = analyze_dscr_sensitivity(cfg, variables=["aep", "tariff", "capex"])

        assert set(result) >= {
            "sensitivity_config",
            "variables",
            "tornado_chart",
            "summary",
            "binding_constraint_analysis",
        }
        assert len(result["variables"]) == 3
        assert len(result["tornado_chart"]) == 3

        # Each variable result carries n_steps perturbation rows with full keys.
        for var_result in result["variables"]:
            perts = var_result["perturbations"]
            assert len(perts) == 5
            for row in perts:
                assert set(row) >= {
                    "perturbation_pct",
                    "perturbed_value",
                    "debt_sized",
                    "debt_p50",
                    "debt_p99",
                    "binding_constraint",
                    "delta_from_base_usd",
                    "delta_from_base_pct",
                    "min_dscr_p50",
                    "min_dscr_p99",
                }
                assert row["binding_constraint"] in {"P50", "P99", "RATIO_CAP"}

        # sensitivity_config echoes the canonical inputs.
        sc = result["sensitivity_config"]
        assert sc["base_capex"] == float(cfg.project.capex_usd)
        assert sc["n_steps"] == 5

        # Tornado is sorted by descending absolute impact.
        tornado = result["tornado_chart"]
        for i in range(1, len(tornado)):
            assert abs(tornado[i - 1]["impact_range"]) >= abs(
                tornado[i]["impact_range"]
            )

        # Summary points at the head of the sorted tornado.
        assert result["summary"]["most_sensitive_variable"] == tornado[0]["variable"]
        assert result["summary"]["variables_analyzed"] == 3

    def test_sensitivity_defaults_when_section_absent(self) -> None:
        """Omitting the ``sensitivity`` block falls back to the documented defaults."""
        cfg = _lendercase_overlay()
        # Drop the sensitivity overrides so the .get(...) defaults (20.0, 9) apply.
        del cfg["sensitivity"]

        result = analyze_dscr_sensitivity(cfg, variables=["tariff"])

        sc = result["sensitivity_config"]
        assert sc["perturbation_range_pct"] == 20.0
        assert sc["n_steps"] == 9
        assert len(result["variables"][0]["perturbations"]) == 9


class TestConstraintTransitionBranch:
    """Force a binding-constraint change so the transition append branch runs."""

    def test_transition_recorded_across_sweep(self) -> None:
        """Rising AEP pushes debt capacity into the gearing cap (P99->RATIO_CAP).

        With a deliberately small CAPEX the gearing cap (0.70 * 20M = 14M) is
        well below the cash-flow-implied capacity at the top of the AEP sweep, so
        the binding constraint flips from the P99 cash-flow constraint to the
        ratio cap partway through — exercising the transition-append branch.
        """
        config = SensitivityConfig(
            base_capex=20e6,
            base_aep_p50=100_000,
            base_aep_p99=70_000,
            base_tariff=50.0,
            base_opex=2.0e6,
            base_degradation=0.006,
            project_life=20,
            perturbation_range_pct=40.0,
            n_steps=13,
            dscr_target_p50=1.30,
            dscr_target_p99=1.00,
            debt_ratio_max=0.70,
            debt_rate=0.08,
        )

        result = analyze_single_variable(config, "aep")

        transitions = result["constraint_transitions"]
        assert len(transitions) >= 1, "Expected at least one binding-constraint change"
        for tr in transitions:
            assert set(tr) == {
                "at_perturbation_pct",
                "from_constraint",
                "to_constraint",
            }
            assert tr["from_constraint"] != tr["to_constraint"]

        # Cross-check: the recorded constraints actually differ in the sweep rows,
        # and the cap is reached at the high-AEP end.
        seen = {row["binding_constraint"] for row in result["perturbations"]}
        assert {"P99", "RATIO_CAP"} <= seen
        assert result["perturbations"][-1]["binding_constraint"] == "RATIO_CAP"


class TestUnknownVariableFallThrough:
    """Reach the defensive ``perturbed_value = 0.0`` else branch."""

    def test_unknown_variable_perturbed_value_zero(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unknown variable that slips past _perturb_parameter logs value 0.0.

        ``_perturb_parameter`` normally raises ``ValueError`` for an unknown
        variable, so the ``else`` fall-through in ``analyze_single_variable`` is
        otherwise dead. We stub the perturber to return a valid param set so the
        loop proceeds and exercises the defensive branch (perturbed_value -> 0.0)
        and the matching base_value -> 0.0 fall-through.
        """
        config = SensitivityConfig(
            base_capex=200e6,
            base_aep_p50=100_000,
            base_aep_p99=85_000,
            base_tariff=50.0,
            base_opex=2.5e6,
            base_degradation=0.006,
            project_life=20,
            perturbation_range_pct=10.0,
            n_steps=3,
            dscr_target_p50=1.30,
            dscr_target_p99=1.00,
            debt_ratio_max=0.70,
            debt_rate=0.08,
        )

        def _fake_perturb(
            cfg: SensitivityConfig, variable: str, pct: float
        ) -> Dict[str, float]:
            # Ignore the variable name; return an unperturbed, valid param set.
            return {
                "aep_p50": cfg.base_aep_p50,
                "aep_p99": cfg.base_aep_p99,
                "tariff": cfg.base_tariff,
                "opex": cfg.base_opex,
                "degradation": cfg.base_degradation,
                "capex": cfg.base_capex,
            }

        monkeypatch.setattr(dscr_mod, "_perturb_parameter", _fake_perturb)

        result = analyze_single_variable(config, "mystery_var")

        # Unknown variable -> perturbed_value defaults to 0.0 for every row,
        # and base_value also falls through to 0.0.
        assert result["variable"] == "mystery_var"
        assert result["base_value"] == 0.0
        assert all(row["perturbed_value"] == 0.0 for row in result["perturbations"])


class TestMainCli:
    """Exercise the ``main`` CLI entry point and its guards."""

    def test_main_happy_path_emits_json(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """main() loads a config, runs the analysis, and prints JSON results."""
        import sys as _sys

        cfg = _lendercase_overlay()

        # Stub OmegaConf.load (referenced as the module-level symbol) to return
        # our in-memory config rather than touching disk with the wrong schema.
        # main() does a local ``import sys``, which resolves to this same cached
        # module object, so patching argv here is seen inside main().
        monkeypatch.setattr(dscr_mod.OmegaConf, "load", lambda _path: cfg)
        monkeypatch.setattr(
            _sys,
            "argv",
            ["analytics.dscr_sensitivity", "scenarios/whatever.yaml"],
        )

        main()

        out = capsys.readouterr().out
        payload: Dict[str, Any] = json.loads(out)
        assert "tornado_chart" in payload
        assert "summary" in payload
        assert payload["summary"]["variables_analyzed"] == 5

    def test_main_usage_error_exits(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No config argument -> usage error and SystemExit(1)."""
        import sys as _sys

        monkeypatch.setattr(_sys, "argv", ["analytics.dscr_sensitivity"])

        with pytest.raises(SystemExit) as excinfo:
            main()

        assert excinfo.value.code == 1

    def test_main_non_mapping_config_raises_typeerror(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A list-rooted config is rejected with a TypeError (must be a mapping)."""
        import sys as _sys

        # OmegaConf.load on a sequence root yields a ListConfig (not DictConfig).
        monkeypatch.setattr(
            dscr_mod.OmegaConf, "load", lambda _path: OmegaConf.create([1, 2, 3])
        )
        monkeypatch.setattr(
            _sys, "argv", ["analytics.dscr_sensitivity", "list_root.yaml"]
        )

        with pytest.raises(TypeError, match="must be a mapping"):
            main()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

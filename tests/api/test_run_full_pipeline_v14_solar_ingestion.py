"""Solar frozen-export ingestion in the canonical CLI (#614).

Pins the W4 wiring that lets ``run_full_pipeline_v14.py`` consume a *frozen* solar
export via the pvlib-free ``solar_resource.cashflow_adapter.solar_export_to_scenario_patch``
— the photovoltaic analogue of the Sprint-19 wind ingestion path, with semantics matching
``app/services/pipeline_service.run_integrated_case``.

What is asserted:

* the helper applies a frozen solar export under each adapter mode
  (overwrite / fill_if_absent / validate_only);
* a P-level mismatch guard raises before finance;
* a per-tech drift beyond tolerance raises ``SolarAdapterDriftError``;
* the default-OFF path (``solar_assessment_json`` unset) is a pure no-op — the CLI
  hands the ORIGINAL config straight to the engine, byte-identically;
* both ingestion failure surfaces emit the documented structured error JSON
  (``phase='solar_resource_ingestion'`` / ``error_type='SolarAdapterDriftError'``)
  and exit 1 BEFORE the finance run;
* ``compute_solar_aep`` / ``pvlib`` are never imported by the finance path.

Framework:
- TEST-01: Golden behavior pin for the new opt-in surface
- CESSPIT: fail-loud, structured ingestion errors
- CASPER: frozen-export design preserved (no pvlib at finance time)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from omegaconf import OmegaConf

import run_full_pipeline_v14 as rfp
from solar_resource.cashflow_adapter import SolarAdapterDriftError

# ---------------------------------------------------------------------------
# Adapter-mechanics constants (decoupled from the committed scenario), reused from
# tests/solar/test_cashflow_adapter.py so the numbers stay coherent.
# ---------------------------------------------------------------------------
_WIND_MW, _WIND_CF = 159.6, 0.332
_SOLAR_MW = 50.0
_SOLAR_CF_MODELLED = 0.17901
_SOLAR_AEP_MODELLED = 78.41  # 50 * 8760 * 0.17901 / 1000
_PROJECT_MW = 209.6


@pytest.fixture()
def p50_export() -> dict[str, Any]:
    """Frozen P50 solar export in the SolarCashflowExport contract shape."""
    return {
        "scenario": "P50",
        "technology": "solar",
        "annual_energy_gwh": _SOLAR_AEP_MODELLED,
        "capacity_factor": _SOLAR_CF_MODELLED,
        "dc_capacity_mw": _SOLAR_MW,
        "specific_yield_kwh_per_kwp": 1568.2,
    }


@pytest.fixture()
def hybrid_scenario() -> dict[str, Any]:
    """v14 hybrid fragment carrying a DECLARED (pre-overwrite) solar CF of 0.20."""
    return {
        "project": {"capacity_mw": _PROJECT_MW, "capacity_factor": 0.300584},
        "generation": {
            "technologies": {
                "wind": {
                    "capacity_mw": _WIND_MW,
                    "capacity_factor": _WIND_CF,
                    "aep_gwh": 464.3,
                },
                "solar": {
                    "capacity_mw": _SOLAR_MW,
                    "capacity_factor": 0.20,
                    "aep_gwh": 87.6,
                },
            }
        },
    }


def _write_json(path: Path, payload: Any) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_yaml(path: Path, payload: Any) -> Path:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


# ===========================================================================
# 1. Loader — contract vs wrapped shapes (symmetry with _load_wind_export)
# ===========================================================================


class TestLoadSolarExport:
    def test_bare_contract_shape(self, tmp_path, p50_export) -> None:
        p = _write_json(tmp_path / "solar.json", p50_export)
        assert rfp._load_solar_export(p) == p50_export

    def test_cashflow_export_wrapper(self, tmp_path, p50_export) -> None:
        p = _write_json(tmp_path / "solar.json", {"cashflow_export": p50_export})
        assert rfp._load_solar_export(p) == p50_export

    def test_solar_export_wrapper(self, tmp_path, p50_export) -> None:
        p = _write_json(tmp_path / "solar.json", {"solar_export": p50_export})
        assert rfp._load_solar_export(p) == p50_export

    def test_non_dict_rejected(self, tmp_path) -> None:
        p = _write_json(tmp_path / "solar.json", [1, 2, 3])
        with pytest.raises(ValueError, match="did not parse to a dict"):
            rfp._load_solar_export(p)


# ===========================================================================
# 2. _apply_solar_to_scenario — the three adapter modes + guards
# ===========================================================================


class TestApplySolarToScenario:
    def _patched(self, tmp_path, scenario, export, **kw) -> dict[str, Any]:
        scen_path = _write_yaml(tmp_path / "scenario.yaml", scenario)
        exp_path = _write_json(tmp_path / "solar.json", export)
        out = rfp._apply_solar_to_scenario(
            scenario_path=scen_path,
            solar_export_path=exp_path,
            adapter_mode=kw.get("adapter_mode", "fill_if_absent"),
            tolerance_pct=kw.get("tolerance_pct", 0.5),
            scenario_name=kw.get("scenario_name", "P50"),
            technology=kw.get("technology", "solar"),
        )
        try:
            return yaml.safe_load(out.read_text(encoding="utf-8"))
        finally:
            out.unlink(missing_ok=True)

    def test_overwrite_replaces_declared_cf_and_reblends(
        self, tmp_path, hybrid_scenario, p50_export
    ) -> None:
        patched = self._patched(
            tmp_path, hybrid_scenario, p50_export, adapter_mode="overwrite"
        )
        solar = patched["generation"]["technologies"]["solar"]
        assert solar["capacity_factor"] == pytest.approx(_SOLAR_CF_MODELLED)
        # Wind is untouched; the project headline re-blends.
        assert patched["generation"]["technologies"]["wind"]["capacity_factor"] == (
            _WIND_CF
        )
        expected_blend = (
            _WIND_MW * _WIND_CF + _SOLAR_MW * _SOLAR_CF_MODELLED
        ) / _PROJECT_MW
        assert patched["project"]["capacity_factor"] == pytest.approx(expected_blend)
        # Provenance metadata is stamped.
        assert patched["solar_resource"]["source"] == "frozen_export"

    def test_fill_if_absent_writes_missing_cf(self, tmp_path, p50_export) -> None:
        # A scenario whose solar slot has capacity_mw but NO capacity_factor.
        scenario = {
            "project": {"capacity_mw": _SOLAR_MW, "capacity_factor": 0.0},
            "generation": {
                "technologies": {"solar": {"capacity_mw": _SOLAR_MW}},
            },
        }
        patched = self._patched(
            tmp_path, scenario, p50_export, adapter_mode="fill_if_absent"
        )
        solar = patched["generation"]["technologies"]["solar"]
        assert solar["capacity_factor"] == pytest.approx(_SOLAR_CF_MODELLED)

    def test_validate_only_agreeing_scenario_is_noop_on_economics(
        self, tmp_path, p50_export
    ) -> None:
        scenario = {
            "project": {
                "capacity_mw": _SOLAR_MW,
                "capacity_factor": _SOLAR_CF_MODELLED,
            },
            "generation": {
                "technologies": {
                    "solar": {
                        "capacity_mw": _SOLAR_MW,
                        "capacity_factor": _SOLAR_CF_MODELLED,
                        "aep_gwh": _SOLAR_AEP_MODELLED,
                    }
                }
            },
        }
        patched = self._patched(
            tmp_path, scenario, p50_export, adapter_mode="validate_only"
        )
        # Economics unchanged; only provenance metadata added.
        assert patched["generation"]["technologies"]["solar"]["capacity_factor"] == (
            pytest.approx(_SOLAR_CF_MODELLED)
        )
        assert patched["solar_resource"]["adapter_mode"] == "validate_only"

    def test_p_level_mismatch_raises(self, tmp_path, hybrid_scenario, p50_export):
        with pytest.raises(ValueError, match="refusing to mix P-levels"):
            self._patched(
                tmp_path,
                hybrid_scenario,
                p50_export,
                adapter_mode="fill_if_absent",
                scenario_name="P75",
            )

    def test_drift_beyond_tolerance_raises(self, tmp_path, hybrid_scenario, p50_export):
        # hybrid declares solar CF=0.20; export is 0.17901 -> ~11.7% drift >> 0.5%.
        with pytest.raises(SolarAdapterDriftError):
            self._patched(
                tmp_path,
                hybrid_scenario,
                p50_export,
                adapter_mode="fill_if_absent",
                tolerance_pct=0.5,
            )


# ===========================================================================
# 3. cli() end-to-end — default-off no-op + structured error surfaces.
#    The engine is monkeypatched so these run fast and assert the WIRING,
#    not the finance math (that is covered by the KPI oracle).
# ===========================================================================


def _run_cli(cfg_overrides: dict[str, Any]) -> None:
    """Invoke the Hydra-decorated cli() with a plain OmegaConf config."""
    base = {
        "config": cfg_overrides.pop("config", ""),
        "validation_mode": "off",
        "validation_modules": None,
        "export_dir": cfg_overrides.pop("export_dir", "_out/test"),
        "write_artifacts": False,
        "wind_assessment_json": None,
        "wind_auto_orchestrate": False,
        "adapter_mode": "fill_if_absent",
        "wind_tolerance_pct": 0.5,
        "wind_export_scenario": "P75",
        "solar_assessment_json": None,
        "solar_adapter_mode": "fill_if_absent",
        "solar_tolerance_pct": 0.5,
        "solar_export_scenario": "P50",
        "solar_technology": "solar",
    }
    base.update(cfg_overrides)
    # __wrapped__ is the undecorated function (bypass Hydra's config composition).
    rfp.cli.__wrapped__(OmegaConf.create(base))


class TestCliSolarWiring:
    def test_default_off_passes_original_config_untouched(
        self, tmp_path, hybrid_scenario, monkeypatch, capsys
    ) -> None:
        scen_path = _write_yaml(tmp_path / "scenario.yaml", hybrid_scenario)
        seen: dict[str, Any] = {}

        def _fake_engine(*, config, validation_mode, validation_modules):
            seen["config"] = config
            return {"status": "success", "kpis": {}, "run_manifest": {"x": 1}}

        monkeypatch.setattr(rfp, "run_v14_pipeline", _fake_engine)
        _run_cli({"config": str(scen_path)})

        # Default OFF: the ORIGINAL config path flows through unchanged (no temp file).
        assert seen["config"] == str(scen_path)
        out = json.loads(capsys.readouterr().out)
        assert out["status"] == "success"

    def test_solar_export_patches_config_before_engine(
        self, tmp_path, hybrid_scenario, p50_export, monkeypatch, capsys
    ) -> None:
        scen_path = _write_yaml(tmp_path / "scenario.yaml", hybrid_scenario)
        exp_path = _write_json(tmp_path / "solar.json", p50_export)
        seen: dict[str, Any] = {}

        def _fake_engine(*, config, validation_mode, validation_modules):
            # The engine receives a PATCHED temp file, not the original scenario.
            seen["config"] = config
            seen["patched"] = yaml.safe_load(Path(config).read_text(encoding="utf-8"))
            return {"status": "success", "kpis": {}, "run_manifest": {"x": 1}}

        monkeypatch.setattr(rfp, "run_v14_pipeline", _fake_engine)
        _run_cli(
            {
                "config": str(scen_path),
                "solar_assessment_json": str(exp_path),
                "solar_adapter_mode": "overwrite",
                "solar_export_scenario": "P50",
            }
        )
        assert seen["config"] != str(scen_path)  # a temp patched file
        solar = seen["patched"]["generation"]["technologies"]["solar"]
        assert solar["capacity_factor"] == pytest.approx(_SOLAR_CF_MODELLED)
        # Temp patched file is cleaned up afterwards.
        assert not Path(seen["config"]).exists()

    def test_missing_solar_json_emits_structured_error_and_exits(
        self, tmp_path, hybrid_scenario, monkeypatch, capsys
    ) -> None:
        scen_path = _write_yaml(tmp_path / "scenario.yaml", hybrid_scenario)

        def _must_not_run(**_kw):  # pragma: no cover - engine must not be reached
            raise AssertionError("finance engine reached despite ingestion failure")

        monkeypatch.setattr(rfp, "run_v14_pipeline", _must_not_run)
        with pytest.raises(SystemExit) as exc:
            _run_cli(
                {
                    "config": str(scen_path),
                    "solar_assessment_json": str(tmp_path / "nope.json"),
                }
            )
        assert exc.value.code == 1
        err = json.loads(capsys.readouterr().out)
        assert err["status"] == "error"
        assert err["phase"] == "solar_resource_ingestion"
        assert err["error_type"] == "FileNotFoundError"

    def test_drift_failure_emits_structured_drift_error_and_exits(
        self, tmp_path, hybrid_scenario, p50_export, monkeypatch, capsys
    ) -> None:
        scen_path = _write_yaml(tmp_path / "scenario.yaml", hybrid_scenario)
        # hybrid solar CF=0.20 vs export 0.17901 -> drift >> 0.5% under fill_if_absent.
        exp_path = _write_json(tmp_path / "solar.json", p50_export)

        def _must_not_run(**_kw):  # pragma: no cover - engine must not be reached
            raise AssertionError("finance engine reached despite drift failure")

        monkeypatch.setattr(rfp, "run_v14_pipeline", _must_not_run)
        with pytest.raises(SystemExit) as exc:
            _run_cli(
                {
                    "config": str(scen_path),
                    "solar_assessment_json": str(exp_path),
                    "solar_adapter_mode": "fill_if_absent",
                    "solar_tolerance_pct": 0.5,
                }
            )
        assert exc.value.code == 1
        err = json.loads(capsys.readouterr().out)
        assert err["status"] == "error"
        assert err["error_type"] == "SolarAdapterDriftError"
        # The solar-specific detail field (not wind_value).
        assert "solar_value" in err
        assert err["field"].endswith("capacity_factor")

    def test_finance_path_never_imports_pvlib(
        self, tmp_path, hybrid_scenario, p50_export
    ) -> None:
        # CASPER: ingesting a frozen solar export must not pull pvlib into the process.
        # Run the ingestion in a CLEAN subprocess interpreter so the check is
        # order-independent (a sibling test elsewhere in the suite may have already
        # imported pvlib into THIS process's sys.modules — asserting on the shared
        # sys.modules would be flaky). The subprocess imports the CLI module and drives
        # the solar adapter exactly as cli() does, then reports whether pvlib loaded.
        scen_path = _write_yaml(tmp_path / "scenario.yaml", hybrid_scenario)
        exp_path = _write_json(tmp_path / "solar.json", p50_export)
        repo_root = Path(rfp.__file__).resolve().parent
        probe = (
            "import sys\n"
            "import run_full_pipeline_v14 as rfp\n"
            "out = rfp._apply_solar_to_scenario(\n"
            f"    scenario_path={str(scen_path)!r},\n"
            f"    solar_export_path={str(exp_path)!r},\n"
            "    adapter_mode='overwrite',\n"
            "    tolerance_pct=0.5,\n"
            "    scenario_name='P50',\n"
            "    technology='solar',\n"
            ")\n"
            "import os\n"
            "os.unlink(out)\n"
            "assert 'pvlib' not in sys.modules, 'frozen-export path imported pvlib'\n"
            "print('OK')\n"
        )
        env = dict(os.environ, PYTHONPATH=str(repo_root))
        proc = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        assert proc.returncode == 0, (
            f"pvlib-free probe failed (rc={proc.returncode}):\n"
            f"stdout={proc.stdout}\nstderr={proc.stderr}"
        )
        assert "OK" in proc.stdout

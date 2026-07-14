"""Integration tests for ``scripts/run_fx_sensitivity.py`` (#659).

Smoke tests for the thin FX-sensitivity CLI that wraps
``analytics.fx_sensitivity_real.FXSensitivityAnalyzer.analyze_fx_sensitivity`` — the
FX analogue of ``tests/integration/test_tornado_cli.py``. They pin (1) that the module
imports, (2) the JSON contract (a single object with the three point series + the six
summary sensitivities + the base block) on the committed lender scenario, (3) the
fx_rate IRR/NPV slope SIGN (negative — weaker LKR erodes USD returns, the core
bankability risk), and (4) clean fail-loud behaviour on a bad grid / bad scenario.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_CONFIG = _REPO / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


def _load_cli():
    """Import the script as a module (it lives in scripts/, not an installed pkg)."""
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    spec = importlib.util.spec_from_file_location(
        "run_fx_sensitivity", _REPO / "scripts" / "run_fx_sensitivity.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_module_imports_without_error():
    cli = _load_cli()
    for name in ("result_to_payload", "main", "parse_args"):
        assert hasattr(cli, name)


def test_fx_sensitivity_cli_emits_expected_json(tmp_path: Path):
    """The CLI writes one JSON object with the three point series + summary sensitivities.

    Uses small step counts to keep the real-engine sweep cheap; asserts the exact top-
    level key contract and that the swept series are populated.
    """
    assert _CONFIG.exists(), f"committed lendercase scenario missing: {_CONFIG}"
    cli = _load_cli()
    out = tmp_path / "fx.json"
    rc = cli.main(
        [
            "--config",
            str(_CONFIG),
            "--fx-steps",
            "3",
            "--spread-steps",
            "3",
            "--output",
            str(out),
        ]
    )
    assert rc == 0
    payload = json.loads(out.read_text())

    assert set(payload) == {
        "base",
        "fx_rate_points",
        "hedge_ratio_points",
        "spread_points",
        "summary_sensitivities",
    }
    # Point series are populated (fx/spread honour the requested step counts).
    assert len(payload["fx_rate_points"]) == 3
    assert len(payload["spread_points"]) == 3
    assert len(payload["hedge_ratio_points"]) >= 2
    # Each point carries the swept lever + the KPIs.
    pt = payload["fx_rate_points"][0]
    for key in ("fx_rate", "hedge_ratio", "spread_bps", "project_irr", "project_npv"):
        assert key in pt
    # The six engine-driven summary sensitivities are present.
    assert set(payload["summary_sensitivities"]) == {
        "fx_rate_irr",
        "fx_rate_npv",
        "hedge_ratio_irr",
        "hedge_ratio_npv",
        "spread_irr",
        "spread_npv",
    }


def test_fx_sensitivity_cli_fx_rate_slope_is_negative(tmp_path: Path):
    """fx_rate IRR and NPV slopes are NEGATIVE on the lender case.

    A weaker LKR (higher LKR-per-USD) erodes USD-denominated returns — the core flat-LKR
    bankability risk this surface exists to quantify. This is the FX analogue of the
    tornado smoke test's impact-direction assertion.
    """
    assert _CONFIG.exists(), f"committed lendercase scenario missing: {_CONFIG}"
    cli = _load_cli()
    out = tmp_path / "fx.json"
    rc = cli.main(
        [
            "--config",
            str(_CONFIG),
            "--fx-steps",
            "3",
            "--spread-steps",
            "3",
            "--output",
            str(out),
        ]
    )
    assert rc == 0
    summary = json.loads(out.read_text())["summary_sensitivities"]
    assert summary["fx_rate_irr"] < 0.0
    assert summary["fx_rate_npv"] < 0.0


def test_fx_sensitivity_cli_streams_json_to_stdout(capsys):
    """With no --output the CLI streams a single valid JSON object to stdout."""
    assert _CONFIG.exists(), f"committed lendercase scenario missing: {_CONFIG}"
    cli = _load_cli()
    rc = cli.main(["--config", str(_CONFIG), "--fx-steps", "3", "--spread-steps", "3"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "fx_rate_points" in payload
    assert "summary_sensitivities" in payload


def test_fx_sensitivity_cli_rejects_degenerate_step_count(capsys):
    """--fx-steps / --spread-steps < 2 fails loud (exit 2), never a degenerate sweep."""
    cli = _load_cli()
    rc = cli.main(["--config", str(_CONFIG), "--fx-steps", "1"])
    assert rc == 2
    assert "ERROR" in capsys.readouterr().err


def test_fx_sensitivity_cli_rejects_negative_spread_band(capsys):
    """A negative --spread-variation-bps fails loud through the analyzer's named guard."""
    assert _CONFIG.exists(), f"committed lendercase scenario missing: {_CONFIG}"
    cli = _load_cli()
    rc = cli.main(
        [
            "--config",
            str(_CONFIG),
            "--fx-steps",
            "3",
            "--spread-steps",
            "3",
            "--spread-variation-bps",
            "-50",
        ]
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert "ERROR" in err
    assert "spread_variation_bps" in err


def test_fx_sensitivity_cli_missing_config_fails_loud(capsys):
    """A nonexistent scenario path fails loud (exit 2), not an uncaught traceback."""
    cli = _load_cli()
    rc = cli.main(
        [
            "--config",
            "scenarios/__does_not_exist__.yaml",
            "--fx-steps",
            "3",
            "--spread-steps",
            "3",
        ]
    )
    assert rc == 2
    assert "ERROR" in capsys.readouterr().err


def test_fx_sensitivity_cli_invalid_scenario_fails_loud(capsys):
    """An INVALID scenario (missing required `fx` section) fails loud (exit 2).

    Regression guard: the evaluation gateway raises PipelineValidationError (a bare
    Exception, NOT a ValueError), which an over-narrow `except (ValueError, ...)` would
    let escape as a raw traceback. The CLI must catch it and exit 2 cleanly (CESSPIT).
    """
    cli = _load_cli()
    invalid = _REPO / "scenarios" / "kolonnawa_epc_100mw.yaml"
    assert invalid.exists(), f"committed invalid-fx scenario fixture missing: {invalid}"
    rc = cli.main(["--config", str(invalid), "--fx-steps", "3", "--spread-steps", "3"])
    assert rc == 2
    assert "ERROR" in capsys.readouterr().err

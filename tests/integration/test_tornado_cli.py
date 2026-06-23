"""Integration tests for ``scripts/run_tornado_from_cli.py``.

Regression guard for the breakage where the CLI imported six symbols from the
retired ``analytics.sensitivity_v14`` star-import shim (``SensitivityRequest``,
``run``, ``run_multi_metric_tornado``, ``load_parameters_from_yaml``,
``tornado_suite_to_dataframe``, ``multi_metric_suite_to_dataframe``) — none of
which the shim exported, so ``python scripts/run_tornado_from_cli.py`` raised
``ImportError`` on import. The CLI is now repointed to the live
``analytics.core.sensitivity_runner`` API; these tests pin (1) that the module
imports, (2) the YAML parameter loader, (3) the tornado->CSV flatten/column
contract, and (4) clean multi-metric and error behaviour.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_CONFIG = _REPO / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"

pd = pytest.importorskip("pandas")


def _load_cli():
    """Import the script as a module (it lives in scripts/, not an installed pkg)."""
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    spec = importlib.util.spec_from_file_location(
        "run_tornado_from_cli", _REPO / "scripts" / "run_tornado_from_cli.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # would raise ImportError under the old breakage
    return mod


def test_module_imports_without_error():
    cli = _load_cli()
    for name in ("load_parameters_from_yaml", "tornado_suite_to_dataframe", "main"):
        assert hasattr(cli, name)


def _write_params(tmp_path: Path, *, nested: bool = True) -> Path:
    body = (
        "parameters:\n" if nested else ""
    ) + (
        "  - variable_name: capex.usd_total\n"
        "    base_value: 159600000.0\n"
        "    low_pct: -10.0\n"
        "    high_pct: 10.0\n"
        "  - variable_name: tariff.lkr_per_kwh\n"
        "    base_value: 20.3\n"
        "    low_pct: -10.0\n"
        "    high_pct: 10.0\n"
    )
    if not nested:
        # top-level list form (dedent the two items)
        body = body.replace("  - ", "- ").replace("    ", "  ")
    p = tmp_path / "params.yaml"
    p.write_text(body)
    return p


def test_load_parameters_from_yaml_nested_and_list(tmp_path: Path):
    cli = _load_cli()
    for nested in (True, False):
        params = cli.load_parameters_from_yaml(_write_params(tmp_path, nested=nested))
        assert [p.variable_name for p in params] == ["capex.usd_total", "tariff.lkr_per_kwh"]
        assert params[0].base_value == pytest.approx(159_600_000.0)


def test_load_parameters_rejects_unknown_keys(tmp_path: Path):
    cli = _load_cli()
    bad = tmp_path / "bad.yaml"
    bad.write_text("parameters:\n  - variable_name: x\n    base_value: 1.0\n    bogus_key: 5\n")
    with pytest.raises(ValueError, match="unknown keys"):
        cli.load_parameters_from_yaml(bad)


@pytest.mark.skipif(not _CONFIG.exists(), reason="lendercase scenario not present")
def test_single_metric_tornado_csv(tmp_path: Path):
    cli = _load_cli()
    out = tmp_path / "tornado.csv"
    rc = cli.main([
        "--config", str(_CONFIG),
        "--parameters", str(_write_params(tmp_path)),
        "--metric", "project_irr",
        "--output", str(out),
    ])
    assert rc == 0
    df = pd.read_csv(out)
    assert list(df.columns) == [
        "metric", "variable_name", "label", "base_case", "low_case", "high_case", "impact_abs",
    ]
    assert set(df["variable_name"]) == {"capex.usd_total", "tariff.lkr_per_kwh"}
    assert (df["metric"] == "project_irr").all()
    # base_case is the unlevered project IRR (a finite fraction), identical across rows.
    assert df["base_case"].nunique() == 1
    assert df["base_case"].iloc[0] == pytest.approx(0.0505, abs=0.02)
    # tornado convention: rows sorted by descending |impact|.
    assert df["impact_abs"].is_monotonic_decreasing


@pytest.mark.skipif(not _CONFIG.exists(), reason="lendercase scenario not present")
def test_multi_metric_tags_each_metric(tmp_path: Path):
    cli = _load_cli()
    out = tmp_path / "multi.csv"
    rc = cli.main([
        "--config", str(_CONFIG),
        "--parameters", str(_write_params(tmp_path)),
        "--metric", "project_irr",
        "--metric", "min_dscr",
        "--output", str(out),
    ])
    assert rc == 0
    df = pd.read_csv(out)
    assert set(df["metric"]) == {"project_irr", "min_dscr"}


@pytest.mark.skipif(not _CONFIG.exists(), reason="lendercase scenario not present")
def test_unresolvable_parameter_path_exits_clean(tmp_path: Path, capsys):
    cli = _load_cli()
    bad = tmp_path / "unresolvable.yaml"
    bad.write_text(
        "parameters:\n  - variable_name: finance.does_not_exist\n"
        "    base_value: 1.0\n    low_pct: -10.0\n    high_pct: 10.0\n"
    )
    rc = cli.main([
        "--config", str(_CONFIG),
        "--parameters", str(bad),
        "--metric", "project_irr",
    ])
    assert rc == 2  # clean non-zero exit, not an uncaught traceback
    assert "ERROR" in capsys.readouterr().err

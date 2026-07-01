"""Integration tests for ``scripts/run_multi_tech_tornado.py`` (Epic 6.1).

Pins the CLI contract: it imports, flattens the per-technology tornado to a tagged
CSV (sorted by |impact| within each metric), defaults to the full metric set, and
exits cleanly (code 2) on a non-multi-tech scenario or a bad shock band — rather than
emitting an empty CSV or an uncaught traceback.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_HYBRID = _REPO / "scenarios" / "dutchbay_hybrid_windsolar_2025Q4.yaml"
_WIND_ONLY = _REPO / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"
_CEB_BESS = _REPO / "scenarios" / "ceb_bess_10mw_capacity_charge.yaml"

pd = pytest.importorskip("pandas")
yaml = pytest.importorskip("yaml")


def _load_cli():
    """Import the script as a module (it lives in scripts/, not an installed pkg)."""
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    spec = importlib.util.spec_from_file_location(
        "run_multi_tech_tornado", _REPO / "scripts" / "run_multi_tech_tornado.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_module_imports_without_error():
    cli = _load_cli()
    for name in ("main", "bars_to_dataframe", "parse_args"):
        assert hasattr(cli, name)


@pytest.mark.skipif(not _HYBRID.exists(), reason="hybrid scenario not present")
def test_csv_columns_tags_and_sorting(tmp_path: Path):
    cli = _load_cli()
    out = tmp_path / "mtt.csv"
    rc = cli.main(
        [
            "--config",
            str(_HYBRID),
            "--metric",
            "project_irr",
            "--metric",
            "balloon_pct",
            "--output",
            str(out),
        ]
    )
    assert rc == 0
    df = pd.read_csv(out)
    assert list(df.columns) == [
        "metric",
        "technology",
        "driver",
        "label",
        "base_case",
        "low_case",
        "high_case",
        "impact_abs",
        "shock_pct",
    ]
    assert set(df["technology"]) == {"wind", "solar"}
    assert set(df["driver"]) == {"capex_usd", "capacity_factor", "degradation_pct"}
    assert set(df["metric"]) == {"project_irr", "balloon_pct"}
    # tornado convention: |impact| descending within each metric group.
    for metric in ("project_irr", "balloon_pct"):
        impacts = df[df["metric"] == metric]["impact_abs"].tolist()
        assert impacts == sorted(impacts, reverse=True)
    # the lender finding is visible in the data: wind's top bar beats solar's top bar.
    irr = df[df["metric"] == "project_irr"]
    wind_top = irr[irr["technology"] == "wind"]["impact_abs"].max()
    solar_top = irr[irr["technology"] == "solar"]["impact_abs"].max()
    assert wind_top > solar_top


@pytest.mark.skipif(not _HYBRID.exists(), reason="hybrid scenario not present")
def test_default_metrics_when_unspecified(tmp_path: Path):
    cli = _load_cli()
    out = tmp_path / "default.csv"
    rc = cli.main(["--config", str(_HYBRID), "--output", str(out)])
    assert rc == 0
    df = pd.read_csv(out)
    assert set(df["metric"]) == {"project_irr", "equity_irr", "min_dscr", "balloon_pct"}


@pytest.mark.skipif(not _HYBRID.exists(), reason="hybrid scenario not present")
def test_summary_reports_wind_leader_and_flat_dscr(tmp_path: Path, capsys):
    cli = _load_cli()
    rc = cli.main(["--config", str(_HYBRID), "--output", str(tmp_path / "s.csv")])
    assert rc == 0
    err = capsys.readouterr().err
    assert "wind drives project_irr volatility" in err
    assert "min_dscr is structurally flat" in err


@pytest.mark.skipif(not _HYBRID.exists(), reason="hybrid scenario not present")
def test_storage_block_reported_not_swept(tmp_path: Path, capsys):
    """wind + solar + BESS: the CSV sweeps only the generation techs, and stderr
    names the storage block as present-but-not-swept (no silent drop)."""
    raw = yaml.safe_load(_HYBRID.read_text())
    raw["generation"]["technologies"]["battery"] = {"power_mw": 50, "energy_mwh": 200}
    scenario = tmp_path / "hybrid_with_bess.yaml"
    scenario.write_text(yaml.safe_dump(raw))

    cli = _load_cli()
    out = tmp_path / "mtt.csv"
    rc = cli.main(
        ["--config", str(scenario), "--metric", "project_irr", "--output", str(out)]
    )
    assert rc == 0
    assert set(pd.read_csv(out)["technology"]) == {"wind", "solar"}
    err = capsys.readouterr().err
    assert "battery" in err
    assert "NOT swept" in err


@pytest.mark.skipif(not _CEB_BESS.exists(), reason="CEB BESS scenario not present")
def test_standalone_bess_scenario_is_swept(tmp_path: Path, capsys):
    """A standalone storage-only scenario is now swept on its capacity-charge driver."""
    cli = _load_cli()
    out = tmp_path / "bess.csv"
    rc = cli.main(
        ["--config", str(_CEB_BESS), "--metric", "project_irr", "--output", str(out)]
    )
    assert rc == 0
    df = pd.read_csv(out)
    assert set(df["technology"]) == {"bess_unit"}
    assert (df["driver"] == "capacity_charge_lkr_per_mw_month").all()
    assert "storage/BESS: bess_unit" in capsys.readouterr().err


@pytest.mark.skipif(not _WIND_ONLY.exists(), reason="wind-only scenario not present")
def test_non_multitech_scenario_exits_clean(capsys):
    """A wind-only scenario has no generation.technologies -> clean exit 2, no CSV."""
    cli = _load_cli()
    rc = cli.main(["--config", str(_WIND_ONLY)])
    assert rc == 2
    assert "no sweepable technologies" in capsys.readouterr().err


@pytest.mark.skipif(not _HYBRID.exists(), reason="hybrid scenario not present")
def test_bad_shock_pct_exits_clean(capsys):
    cli = _load_cli()
    rc = cli.main(["--config", str(_HYBRID), "--shock-pct", "1.5"])
    assert rc == 2
    assert "ERROR" in capsys.readouterr().err

"""Tests for the report presentation config loader (CCCDIR surface)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from app.reports.report_config import (
    DEFAULT_CONFIG_PATH,
    ReportConfig,
    load_report_config,
)


def test_default_config_loads_and_validates() -> None:
    cfg = load_report_config()
    assert isinstance(cfg, ReportConfig)
    assert cfg.report.title
    assert cfg.report.organization
    # Covenant thresholds are the documented lender defaults.
    assert cfg.covenants.min_dscr_floor == pytest.approx(1.20)
    assert cfg.covenants.min_dscr_target == pytest.approx(1.30)
    assert cfg.covenants.max_balloon_pct == pytest.approx(0.40)


def test_default_path_points_at_committed_yaml() -> None:
    assert DEFAULT_CONFIG_PATH.name == "report_defaults.yaml"
    assert DEFAULT_CONFIG_PATH.exists()


def test_kpi_table_has_core_indicators() -> None:
    cfg = load_report_config()
    keys = {row.key for row in cfg.kpi_table}
    assert {"project_irr", "equity_irr", "min_dscr", "discount_rate_used"} <= keys
    # Every spec carries a renderable kind.
    assert all(row.kind in {"pct", "multiple", "usd"} for row in cfg.kpi_table)


def test_unknown_key_is_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        textwrap.dedent(
            """
            report:
              title: t
              subtitle: s
              organization: o
              version: "1.0"
              confidentiality: c
              disclaimer: d
            covenants:
              min_dscr_floor: 1.2
              min_dscr_target: 1.3
              max_balloon_pct: 0.4
            kpi_table: []
            surprise: 1
            """
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):  # pydantic ValidationError (extra=forbid)
        load_report_config(bad)

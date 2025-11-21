"""
Helpers to normalise KPI columns for v14 analytics/export layer.

Goals:
- Ensure both summary_df and timeseries_df have 'scenario_name'.
- Ensure canonical KPI names exist:
  - summary_df: project_irr
  - timeseries_df: dscr
"""

from __future__ import annotations

from typing import Optional, Tuple
import logging

import pandas as pd

logger = logging.getLogger(__name__)


def _ensure_scenario_name(
    summary_df: pd.DataFrame,
    timeseries_df: pd.DataFrame,
    scenario_id: Optional[str] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Ensure both frames have a 'scenario_name' column.

    Strategy:
    - If 'scenario_name' already exists in both: do nothing.
    - Else, try to rename a known scenario-like column.
    - If still missing, attach a default:
      - use provided scenario_id if not None, else 'default_scenario'.
    """
    if "scenario_name" in summary_df.columns and "scenario_name" in timeseries_df.columns:
        return summary_df, timeseries_df

    # Try to detect an existing scenario key to rename.
    candidates = ["scenario", "config_name", "scenario_id"]
    for col in candidates:
        if col in summary_df.columns and "scenario_name" not in summary_df.columns:
            logger.info("Renaming '%s' -> 'scenario_name' in summary_df", col)
            summary_df = summary_df.rename(columns={col: "scenario_name"})
        if col in timeseries_df.columns and "scenario_name" not in timeseries_df.columns:
            logger.info("Renaming '%s' -> 'scenario_name' in timeseries_df", col)
            timeseries_df = timeseries_df.rename(columns={col: "scenario_name"})

    # If still missing, attach a default – do NOT depend on scenario_id being non-None.
    default_name = scenario_id or "default_scenario"

    if "scenario_name" not in summary_df.columns:
        logger.warning(
            "summary_df has no 'scenario_name'; attaching default scenario_name=%r",
            default_name,
        )
        summary_df = summary_df.copy()
        summary_df["scenario_name"] = default_name

    if "scenario_name" not in timeseries_df.columns:
        logger.warning(
            "timeseries_df has no 'scenario_name'; attaching default scenario_name=%r",
            default_name,
        )
        timeseries_df = timeseries_df.copy()
        timeseries_df["scenario_name"] = default_name

    return summary_df, timeseries_df


def _ensure_project_irr(summary_df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure summary_df has a 'project_irr' column.

    If another IRR-like column exists (e.g. 'irr', 'irr_project'), alias it.
    """
    if "project_irr" in summary_df.columns:
        return summary_df

    irr_candidates = [c for c in summary_df.columns if "irr" in c.lower()]
    if irr_candidates:
        chosen = irr_candidates[0]
        logger.warning(
            "Canonical 'project_irr' missing; using %r as source column", chosen
        )
        summary_df = summary_df.copy()
        summary_df["project_irr"] = summary_df[chosen]
    else:
        logger.warning(
            "No IRR-like column found; 'project_irr' will remain absent in summary_df"
        )

    return summary_df


def _ensure_dscr(timeseries_df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure timeseries_df has a 'dscr' column.

    If another DSCR-like column exists (e.g. 'dscr_period', 'annual_dscr'),
    alias it.
    """
    if "dscr" in timeseries_df.columns:
        return timeseries_df

    dscr_candidates = [c for c in timeseries_df.columns if "dscr" in c.lower()]
    if dscr_candidates:
        chosen = dscr_candidates[0]
        logger.warning(
            "Canonical 'dscr' missing; using %r as source column", chosen
        )
        timeseries_df = timeseries_df.copy()
        timeseries_df["dscr"] = timeseries_df[chosen]
    else:
        logger.warning(
            "No DSCR-like column found; 'dscr' will remain absent in timeseries_df"
        )

    return timeseries_df


def normalise_kpis_for_export(
    summary_df: pd.DataFrame,
    timeseries_df: pd.DataFrame,
    scenario_id: Optional[str] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Apply all normalisations needed by ExcelExporter + ChartExporter.

    - Ensure 'scenario_name' in both frames.
    - Ensure summary_df has 'project_irr' (alias from another IRR column if needed).
    - Ensure timeseries_df has 'dscr' (alias from another DSCR column if needed).
    """
    summary_df, timeseries_df = _ensure_scenario_name(
        summary_df, timeseries_df, scenario_id=scenario_id
    )
    summary_df = _ensure_project_irr(summary_df)
    timeseries_df = _ensure_dscr(timeseries_df)
    return summary_df, timeseries_df

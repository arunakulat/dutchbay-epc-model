"""
Universal scenario configuration loader for v13/v14 compatibility.

Responsibilities:
- Load YAML / JSON config files.
- Perform light structural checks only (no over-eager schema enforcement).
- Provide a strict FX resolver used by tests and higher layers.

Deliberate design:
- We DO NOT require v14-only sections like 'debt' or 'generation' here.
  Those rules live with the financial core / validators.
- We DO enforce that explicit FX configs are well-formed when _resolve_fx()
  is used, and we do NOT silently invent FX when the caller asks for it.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

import yaml

logger = logging.getLogger(__name__)


class ScenarioConfigError(ValueError):
    """Configuration-level error for scenario loading."""


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def _try_config_paths(base_path: Path) -> Path:
    """
    Attempt to find a config file by trying common extensions.

    If base_path exists as-is, return it immediately.
    Otherwise, try .yaml, .yml, .json suffixes in order.

    Args:
        base_path: The path provided by the user (may or may not have extension)

    Returns:
        The first existing path found

    Raises:
        FileNotFoundError: If no variant exists
    """
    # Fast path: exact match
    if base_path.exists():
        return base_path

    # If user provided extension, don't try alternatives
    if base_path.suffix:
        raise FileNotFoundError(f"Scenario config not found: {base_path}")

    # Try common extensions in priority order
    candidates = [
        base_path.with_suffix(".yaml"),
        base_path.with_suffix(".yml"),
        base_path.with_suffix(".json"),
    ]

    for candidate in candidates:
        if candidate.exists():
            logger.debug(f"Inferred config path: {candidate} (from {base_path})")
            return candidate

    # Nothing found
    tried = ", ".join(str(c) for c in candidates)
    raise FileNotFoundError(
        f"Scenario config not found: {base_path} "
        f"(tried: {tried})"
    )


def _load_raw_config(path: Path) -> Dict[str, Any]:
    """
    Load a raw scenario configuration from YAML or JSON.

    This function is intentionally dumb about schema – it only cares that
    the top level is a mapping.
    """
    # Use suffix inference helper
    resolved_path = _try_config_paths(path)

    suffix = resolved_path.suffix.lower()
    with resolved_path.open("r", encoding="utf-8") as f:
        if suffix in (".yml", ".yaml"):
            data = yaml.safe_load(f)
        elif suffix == ".json":
            data = json.load(f)
        else:
            raise ScenarioConfigError(
                f"Unsupported scenario config extension '{suffix}' for {resolved_path}"
            )

    if data is None:
        raise ScenarioConfigError(f"Empty configuration in file: {resolved_path}")

    if not isinstance(data, dict):
        raise ScenarioConfigError(
            f"Expected a mapping at top level of {resolved_path}, "
            f"got {type(data).__name__}"
        )

    return data


def _ensure_meta_source(cfg: Dict[str, Any], path: Path) -> None:
    """
    Attach a lightweight 'meta.source_path' breadcrumb, if not already present.

    This is helpful for diagnostics and does not interfere with the financial
    pipeline.
    """
    meta = cfg.setdefault("meta", {})
    meta.setdefault("source_path", str(path))


# ---------------------------------------------------------------------------
# FX handling
# ---------------------------------------------------------------------------


def _resolve_fx(config: Dict[str, Any]) -> Dict[str, float]:
    """
    Resolve FX configuration into a normalised mapping.

    Contract (as enforced by tests/test_fx_config_strictness.py):

    - If 'fx' is missing entirely  -> ValueError.
    - If 'fx' is a scalar number   -> ValueError with a clear message.
    - If 'fx' is a mapping, it MUST contain 'start_lkr_per_usd'.
    - 'annual_depr' is optional and defaults to 0.0.
    - Returns a dict with keys:
        - 'start_lkr_per_usd' (float)
        - 'annual_depr'      (float)
    """
    if "fx" not in config:
        raise ValueError(
            "FX configuration missing; expected 'fx.start_lkr_per_usd' mapping"
        )

    fx_cfg = config["fx"]

    # Reject bare scalar FX – the codebase now expects a structured mapping.
    if isinstance(fx_cfg, (int, float)):
        raise ValueError(
            "Scalar 'fx' not supported; use mapping with "
            "'start_lkr_per_usd' and 'annual_depr'"
        )

    if not isinstance(fx_cfg, dict):
        raise ValueError(
            "FX configuration must be a mapping with "
            "'start_lkr_per_usd' and optional 'annual_depr'"
        )

    if "start_lkr_per_usd" not in fx_cfg:
        raise ValueError(
            "FX configuration missing; expected 'fx.start_lkr_per_usd' mapping"
        )

    try:
        start = float(fx_cfg["start_lkr_per_usd"])
    except (TypeError, ValueError) as exc:
        raise ValueError("fx.start_lkr_per_usd must be a valid number") from exc

    annual_raw = fx_cfg.get("annual_depr", 0.0)
    try:
        annual = float(annual_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("fx.annual_depr must be a valid number if provided") from exc

    result = {
        "start_lkr_per_usd": start,
        "annual_depr": annual,
    }

    logger.debug(
        "Resolved FX config: start_lkr_per_usd=%s, annual_depr=%s",
        result["start_lkr_per_usd"],
        result["annual_depr"],
    )
    return result


# ---------------------------------------------------------------------------
# Public loader
# ---------------------------------------------------------------------------


def load_scenario_config(path: str | Path) -> Dict[str, Any]:
    """
    Load and lightly normalise a scenario configuration.

    Behaviour:
    - Loads YAML/JSON and ensures a top-level mapping.
    - Attaches meta.source_path for traceability.
    - Does NOT enforce v14-only sections like 'debt' or 'generation'.
      That logic lives with the financial core / validators.
    - Does NOT require FX unless callers explicitly ask for it via _resolve_fx.
      However, if FX *is* present and is a bare scalar, we reject it to enforce
      the "no scalar fx" policy baked into the tests.

    UX Enhancement (Sprint 18, Issue #1):
    - Supports suffix inference: 'scenarios/base' will try .yaml, .yml, .json
    - Maintains backward compatibility: exact paths still work as before
    - User-friendly for CLI and notebooks
    """
    p = Path(path)
    cfg = _load_raw_config(p)
    _ensure_meta_source(cfg, p)

    # Enforce "no scalar fx" rule at load time for any config that
    # chooses to specify FX.
    fx_cfg = cfg.get("fx", None)
    if isinstance(fx_cfg, (int, float)):
        raise ValueError(
            "Invalid FX configuration: scalar 'fx' not supported; "
            "expected mapping with 'start_lkr_per_usd' and 'annual_depr'"
        )

    # We deliberately do NOT call _resolve_fx() unconditionally here.
    # Some configs (e.g. legacy or tests that omit FX) may rely on
    # downstream defaults. Tests that care about FX call _resolve_fx()
    # directly.
    return cfg


__all__ = [
    "ScenarioConfigError",
    "load_scenario_config",
    "_resolve_fx",
]

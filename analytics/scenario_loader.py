"""Universal scenario configuration loader for v13/v14 compatibility.

Responsibilities:
- Load YAML and JSON config files.
- Perform light structural checks only; no over-eager schema enforcement.
- Provide a strict FX resolver used by tests and higher layers.

Deliberate design:
- This loader does not require v14-only sections such as ``debt`` or
  ``generation``. Those rules live with the financial core and validators.
- Explicit FX configs are validated when ``_resolve_fx`` is used.
- The loader does not silently invent FX when the caller asks for it.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml

from analytics.aep_reconciliation import reconcile_capacity_factor_with_bankable_aep

logger = logging.getLogger(__name__)


class ScenarioConfigError(ValueError):
    """Configuration-level error for scenario loading."""


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def _try_config_paths(base_path: Path) -> Path:
    """Return an existing config path, trying common suffixes when omitted.

    If ``base_path`` exists as-is, it is returned immediately. Otherwise, when
    the user did not provide a suffix, ``.yaml``, ``.yml``, and ``.json`` are
    tried in that order.
    """
    if base_path.exists():
        return base_path

    if base_path.suffix:
        raise FileNotFoundError(f"Scenario config not found: {base_path}")

    candidates = [
        base_path.with_suffix(".yaml"),
        base_path.with_suffix(".yml"),
        base_path.with_suffix(".json"),
    ]

    for candidate in candidates:
        if candidate.exists():
            logger.debug("Inferred config path: %s from %s", candidate, base_path)
            return candidate

    tried = ", ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(
        f"Scenario config not found: {base_path} "
        f"(tried: {tried})"
    )


def _load_raw_config(path: Path) -> dict[str, Any]:
    """Load a raw scenario configuration from YAML or JSON."""
    resolved_path = _try_config_paths(path)
    suffix = resolved_path.suffix.lower()

    with resolved_path.open("r", encoding="utf-8") as file_obj:
        if suffix in {".yml", ".yaml"}:
            data = yaml.safe_load(file_obj)
        elif suffix == ".json":
            data = json.load(file_obj)
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


def _ensure_meta_source(cfg: dict[str, Any], path: Path) -> None:
    """Attach a lightweight ``meta.source_path`` breadcrumb when absent."""
    meta = cfg.setdefault("meta", {})
    if not isinstance(meta, dict):
        raise ScenarioConfigError("Expected 'meta' to be a mapping when provided")
    meta.setdefault("source_path", str(path))


# ---------------------------------------------------------------------------
# FX handling
# ---------------------------------------------------------------------------


def _resolve_fx(config: dict[str, Any]) -> dict[str, float]:
    """Resolve FX configuration into a normalized mapping.

    Contract enforced by tests:
    - missing ``fx`` raises ``ValueError``;
    - scalar ``fx`` raises ``ValueError``;
    - mapping ``fx`` must contain ``start_lkr_per_usd``;
    - ``annual_depr`` is optional and defaults to 0.0.
    """
    if "fx" not in config:
        raise ValueError(
            "FX configuration missing; expected 'fx.start_lkr_per_usd' mapping"
        )

    fx_cfg = config["fx"]

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

    try:
        annual = float(fx_cfg.get("annual_depr", 0.0))
    except (TypeError, ValueError) as exc:
        raise ValueError("fx.annual_depr must be a valid number if provided") from exc

    # When an explicit config-driven FX source block is present, validate it through
    # the FX routine: this enforces the mode contract and the cross-assert that
    # fx.start_lkr_per_usd == fx.source.pinned_rate (single source of truth, no drift
    # between the two). Scenarios without a source block keep the legacy contract.
    if isinstance(fx_cfg.get("source"), dict):
        from analytics.fx.fx_fetch import FXRequestConfig

        FXRequestConfig.from_scenario(config)

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


def load_scenario_config(path: str | Path) -> dict[str, Any]:
    """Load and lightly normalize a scenario configuration.

    Behavior:
    - loads YAML or JSON and ensures a top-level mapping;
    - attaches ``meta.source_path`` for traceability;
    - does not enforce v14-only sections such as ``debt`` or ``generation``;
    - does not require FX unless callers explicitly ask via ``_resolve_fx``;
    - rejects scalar ``fx`` when present, preserving the no-scalar-FX policy.
    """
    config_path = Path(path)
    cfg = _load_raw_config(config_path)
    _ensure_meta_source(cfg, config_path)

    fx_cfg = cfg.get("fx")
    if isinstance(fx_cfg, (int, float)):
        raise ValueError(
            "Invalid FX configuration: scalar 'fx' not supported; "
            "expected mapping with 'start_lkr_per_usd' and 'annual_depr'"
        )

    # An AUTHORED scenario's capacity_mw × capacity_factor (the engine's revenue basis)
    # must reconcile with any bankable net AEP it also declares — caught here at load
    # time, NOT on every derived run, so deliberate sensitivity/Monte-Carlo perturbations
    # of capacity_factor (which pass in-memory dicts, never re-loaded) are unaffected.
    reconcile_capacity_factor_with_bankable_aep(cfg, str(config_path))

    return cfg


__all__ = [
    "ScenarioConfigError",
    "load_scenario_config",
    "_resolve_fx",
]

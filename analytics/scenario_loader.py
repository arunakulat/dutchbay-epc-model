"""Universal scenario configuration loader for V13/V14 compatibility."""

import json
import logging
from pathlib import Path
from typing import Any, Dict

import yaml

from constants import DEFAULT_FX_USD_TO_LKR
from finance.utils import get_nested, as_float

logger = logging.getLogger(__name__)

FIELD_ALIASES = {
    "capex": ["capex", "total_capex", "project_cost"],
    "opex": ["opex", "annual_opex", "operating_expense"],
    "tariff": ["tariff", "tariff_config", "ppa_tariff"],
}


def load_scenario_config(filepath: str) -> Dict[str, Any]:
    """Load and normalize scenario config from YAML or JSON.

    Handles V13 (master config) and V14 (per-scenario) formats.
    Auto-populates missing currency fields using FX rate.

    Args:
        filepath: Path to YAML or JSON config file

    Returns:
        Normalized configuration dictionary

    Raises:
        ValueError: If required fields are missing
        FileNotFoundError: If file doesn't exist
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {filepath}")

    with path.open("r", encoding="utf-8") as f:
        if path.suffix.lower() == ".json":
            config = json.load(f)
        else:
            config = yaml.safe_load(f)

    if not config:
        raise ValueError(f"Empty config file: {filepath}")

    config = _normalize_keys(config)
    config = _populate_currency_fields(config)
    _validate_required_fields(config)

    logger.info("Loaded scenario config from: %s", filepath)
    return config


def _normalize_keys(config: Dict[str, Any]) -> Dict[str, Any]:
    """Map alias keys to canonical names at the top level."""
    for canon, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            if alias in config and canon not in config:
                config[canon] = config.pop(alias)
                logger.debug("Remapped %r → %r", alias, canon)
    return config


def _resolve_fx(config: Dict[str, Any]) -> float:
    """Resolve FX rate from config or fall back to project default."""
    # Try direct numeric field first
    fx_direct = as_float(config.get("fx"))
    if fx_direct is not None:
        return fx_direct

    # Try nested structure: fx: { start_lkr_per_usd: ... }
    fx_nested = as_float(get_nested(config, ("fx", "start_lkr_per_usd")))
    if fx_nested is not None:
        return fx_nested

    # Fall back to project-wide default
    return DEFAULT_FX_USD_TO_LKR


def _populate_currency_fields(config: Dict[str, Any]) -> Dict[str, Any]:
    """Auto-populate missing USD/LKR fields using FX rate."""
    fx = _resolve_fx(config)

    # Ensure config['fx'] is a simple numeric scalar for downstream code
    if not isinstance(config.get("fx"), (int, float)):
        logger.warning("Using FX rate: %s (default or inferred)", fx)
        config["fx"] = fx

    # Normalize CAPEX
    capex = config.get("capex") or {}
    if capex:
        usd = as_float(capex.get("usd_total"))
        lkr = as_float(capex.get("lkr_total"))

        if usd is not None and lkr is None:
            capex["lkr_total"] = usd * fx
            logger.debug("Computed CAPEX LKR: %s", capex["lkr_total"])
        elif lkr is not None and usd is None:
            capex["usd_total"] = lkr / fx
            logger.debug("Computed CAPEX USD: %s", capex["usd_total"])
        elif usd is None and lkr is None:
            raise ValueError("CAPEX must have either usd_total or lkr_total")

        config["capex"] = capex

    # Normalize OPEX
    opex = config.get("opex") or {}
    if opex:
        usd = as_float(opex.get("usd_per_year"))
        lkr = as_float(opex.get("lkr_per_year"))

        if usd is not None and lkr is None:
            opex["lkr_per_year"] = usd * fx
            logger.debug("Computed OPEX LKR: %s", opex["lkr_per_year"])
        elif lkr is not None and usd is None:
            opex["usd_per_year"] = lkr / fx
            logger.debug("Computed OPEX USD: %s", opex["usd_per_year"])
        elif usd is None and lkr is None:
            raise ValueError("OPEX must have either usd_per_year or lkr_per_year")

        config["opex"] = opex

    return config


def _validate_required_fields(config: Dict[str, Any]) -> None:
    """Validate minimum required fields are present and consistent."""
    required = ["capex", "opex", "tariff"]
    missing = [f for f in required if f not in config]

    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    capex = config.get("capex") or {}
    if not any(k in capex for k in ("usd_total", "lkr_total")):
        raise ValueError("CAPEX must have usd_total or lkr_total")

    opex = config.get("opex") or {}
    if not any(k in opex for k in ("usd_per_year", "lkr_per_year")):
        raise ValueError("OPEX must have usd_per_year or lkr_per_year")

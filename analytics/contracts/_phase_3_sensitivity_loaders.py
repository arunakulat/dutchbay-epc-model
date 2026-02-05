"""OmegaConf loaders for Phase 3 sensitivity contracts.

This module provides OmegaConf-aware loaders for ShockSpec and related
Phase 3 sensitivity contracts, enabling type-safe configuration loading.

Architecture Compliance
-----------------------
CASPER:  Contract-first with Pydantic/OmegaConf validation
CESSPIT: Fail-fast validation at load time
GWTF:    Full type annotations for mypy strict
CCCDIR:  Comprehensive docstrings with usage examples

Public API
----------
- load_shock_specs_from_yaml(path) -> list[ShockSpec]
- load_shock_specs_from_omegaconf(cfg) -> list[ShockSpec]
- build_shock_spec_from_dict(data) -> ShockSpec

Usage Example
-------------
```yaml
# scenarios/sensitivity_shocks.yaml
shocks:
  - variable_name: "capex_total"
    low_value: 180000000.0
    high_value: 220000000.0
    label: "CAPEX ±10%"

  - variable_name: "opex_annual"
    low_value: 4500000.0
    high_value: 5500000.0
    label: "OPEX ±10%"
```

```python
from analytics.contracts import load_shock_specs_from_yaml

shocks = load_shock_specs_from_yaml("scenarios/sensitivity_shocks.yaml")
assert len(shocks) == 2
assert shocks[0].variable_name == "capex_total"
```
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

from omegaconf import DictConfig, ListConfig, OmegaConf

from analytics.contracts._phase_3_sensitivity import ShockSpec

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Type Aliases
# ═══════════════════════════════════════════════════════════════════════════

ShockConfigDict = Dict[str, Any]
ShockConfigList = List[ShockConfigDict]


# ═══════════════════════════════════════════════════════════════════════════
# Core Loaders
# ═══════════════════════════════════════════════════════════════════════════


def load_shock_specs_from_yaml(path: str | Path) -> List[ShockSpec]:
    """Load ShockSpec list from YAML file.

    Parameters
    ----------
    path : str | Path
        Path to YAML file containing shock specifications.

    Returns
    -------
    List[ShockSpec]
        List of validated ShockSpec instances.

    Raises
    ------
    FileNotFoundError
        If YAML file does not exist.
    ValueError
        If YAML structure is invalid or shock validation fails.

    Examples
    --------
    >>> shocks = load_shock_specs_from_yaml("scenarios/shocks.yaml")
    >>> assert all(isinstance(s, ShockSpec) for s in shocks)
    """
    yaml_path = Path(path)

    if not yaml_path.exists():
        raise FileNotFoundError(f"Shock config YAML not found: {yaml_path}")

    logger.debug("Loading shock specs from YAML: %s", yaml_path)

    cfg = OmegaConf.load(yaml_path)

    if not isinstance(cfg, DictConfig):
        raise ValueError(
            f"Expected YAML to load as DictConfig, got {type(cfg).__name__}"
        )

    return load_shock_specs_from_omegaconf(cfg)


def load_shock_specs_from_omegaconf(
    cfg: DictConfig | Dict[str, Any],
) -> List[ShockSpec]:
    """Load ShockSpec list from OmegaConf DictConfig.

    Parameters
    ----------
    cfg : DictConfig | Dict[str, Any]
        OmegaConf configuration containing 'shocks' key.

    Returns
    -------
    List[ShockSpec]
        List of validated ShockSpec instances.

    Raises
    ------
    ValueError
        If 'shocks' key missing or shock validation fails.

    Expected Structure
    ------------------
    ```yaml
    shocks:
      - variable_name: "capex"
        low_value: 180e6
        high_value: 220e6
        label: "CAPEX ±10%"  # optional
    ```

    Examples
    --------
    >>> from omegaconf import OmegaConf
    >>> cfg = OmegaConf.create({"shocks": [{...}]})
    >>> shocks = load_shock_specs_from_omegaconf(cfg)
    """
    if isinstance(cfg, dict):
        cfg = OmegaConf.create(cfg)

    if "shocks" not in cfg:
        raise ValueError(
            "OmegaConf config missing 'shocks' key. "
            "Expected structure: {shocks: [...]}"
        )

    shocks_cfg = cfg.shocks

    if not isinstance(shocks_cfg, (ListConfig, list)):
        raise ValueError(
            f"Expected 'shocks' to be a list, got {type(shocks_cfg).__name__}"
        )

    shock_specs: List[ShockSpec] = []

    for idx, shock_dict in enumerate(shocks_cfg):
        try:
            shock = build_shock_spec_from_dict(shock_dict)
            shock_specs.append(shock)
            logger.debug(
                "Loaded shock[%d]: %s (low=%s, high=%s)",
                idx,
                shock.variable_name,
                shock.low_value,
                shock.high_value,
            )
        except Exception as exc:
            logger.error(
                "Failed to load shock[%d]: %s",
                idx,
                exc,
                exc_info=True,
            )
            raise ValueError(
                f"Invalid shock specification at index {idx}: {exc}"
            ) from exc

    if not shock_specs:
        raise ValueError(
            "No valid shock specifications loaded. "
            "Check YAML structure and validation errors."
        )

    logger.info(
        "Loaded %d shock specification(s) from OmegaConf",
        len(shock_specs),
    )

    return shock_specs


def build_shock_spec_from_dict(data: Dict[str, Any] | DictConfig) -> ShockSpec:
    """Build ShockSpec from dictionary.

    Parameters
    ----------
    data : Dict[str, Any] | DictConfig
        Dictionary containing shock specification fields.

    Returns
    -------
    ShockSpec
        Validated ShockSpec instance.

    Raises
    ------
    ValueError
        If required fields missing or validation fails.
    TypeError
        If field types are incorrect.

    Required Fields
    ---------------
    - variable_name (str): Variable to shock
    - low_value (float): Low shock value
    - high_value (float): High shock value

    Optional Fields
    ---------------
    - label (str): Display label for shock

    Examples
    --------
    >>> shock = build_shock_spec_from_dict({
    ...     "variable_name": "capex",
    ...     "low_value": 180e6,
    ...     "high_value": 220e6,
    ...     "label": "CAPEX ±10%",
    ... })
    >>> assert shock.variable_name == "capex"
    """
    if isinstance(data, DictConfig):
        data = OmegaConf.to_container(data, resolve=True)

    if not isinstance(data, dict):
        raise TypeError(f"Expected dict or DictConfig, got {type(data).__name__}")

    # Validate required fields
    required_fields = {"variable_name", "low_value", "high_value"}
    missing_fields = required_fields - set(data.keys())

    if missing_fields:
        raise ValueError(
            f"Missing required shock fields: {missing_fields}. "
            f"Available keys: {list(data.keys())}"
        )

    # Extract fields with type coercion
    try:
        variable_name = str(data["variable_name"])
        low_value = float(data["low_value"])
        high_value = float(data["high_value"])
        label = str(data.get("label")) if "label" in data else None
    except (TypeError, ValueError) as exc:
        raise TypeError(
            f"Field type conversion failed: {exc}. "
            f"Ensure numeric fields are numbers."
        ) from exc

    # ShockSpec.__post_init__ will validate constraints
    return ShockSpec(
        variable_name=variable_name,
        low_value=low_value,
        high_value=high_value,
        label=label,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Validation Helpers
# ═══════════════════════════════════════════════════════════════════════════


def validate_shock_config_structure(cfg: DictConfig) -> bool:
    """Validate OmegaConf shock configuration structure.

    Parameters
    ----------
    cfg : DictConfig
        OmegaConf configuration to validate.

    Returns
    -------
    bool
        True if structure is valid.

    Raises
    ------
    ValueError
        If structure is invalid with specific error message.

    Examples
    --------
    >>> from omegaconf import OmegaConf
    >>> cfg = OmegaConf.create({"shocks": [{...}]})
    >>> assert validate_shock_config_structure(cfg)
    """
    if not isinstance(cfg, DictConfig):
        raise ValueError(f"Expected DictConfig, got {type(cfg).__name__}")

    if "shocks" not in cfg:
        raise ValueError("Missing 'shocks' key in config. " "Expected: {shocks: [...]}")

    if not isinstance(cfg.shocks, (ListConfig, list)):
        raise ValueError(f"'shocks' must be a list, got {type(cfg.shocks).__name__}")

    if len(cfg.shocks) == 0:
        raise ValueError("'shocks' list is empty. At least one shock required.")

    # Validate first shock has required fields
    first_shock = cfg.shocks[0]
    required = {"variable_name", "low_value", "high_value"}
    missing = required - set(first_shock.keys())

    if missing:
        raise ValueError(f"First shock missing required fields: {missing}")

    logger.debug(
        "Shock config structure validated: %d shock(s)",
        len(cfg.shocks),
    )

    return True


# ═══════════════════════════════════════════════════════════════════════════
# Convenience Functions
# ═══════════════════════════════════════════════════════════════════════════


def load_shocks_from_yaml(path: str | Path) -> List[ShockSpec]:
    """Alias for load_shock_specs_from_yaml().

    Shorter name for convenience.
    """
    return load_shock_specs_from_yaml(path)


__all__ = [
    "load_shock_specs_from_yaml",
    "load_shock_specs_from_omegaconf",
    "build_shock_spec_from_dict",
    "validate_shock_config_structure",
    "load_shocks_from_yaml",
]

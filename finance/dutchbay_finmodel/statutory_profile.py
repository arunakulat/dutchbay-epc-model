"""Statutory Profile: SSCL, env surcharge, success fee, etc. (YAML-driven)

Framework Compliance: CASPER/CESSPIT/GWTF/CCCDIR
- Contract-explicit: Frozen dataclass with type annotations
- Evidence-based: YAML-driven configuration
- Scenario-stable: Immutable configuration
- Schema-explicit: All fields strongly typed
- Pure functions: No I/O, no side effects
- Fail-fast: Validation in __post_init__
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping

SSCLBase = Literal["gross_revenue", "net_revenue_after_grid_loss"]


def _req(section: Mapping[str, Any], key: str, ctx: str) -> Any:
    """
    Return a required key from a section or raise with context.

    Type Safety
    -----------
    Returns Any because YAML values are untyped. Caller must cast explicitly.
    """
    if key not in section:
        raise KeyError(f"Missing required YAML key: {ctx}.{key}")
    return section[key]


def _req_section(cfg: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    """
    Return a named subsection or raise if missing.

    Type Safety
    -----------
    Validates that section exists and is a Mapping through isinstance check.
    Type ignore is required because mypy cannot track dict value types through
    the isinstance check, but the check guarantees the return type at runtime.

    Returns
    -------
    Mapping[str, Any]
        Validated configuration section.

    Raises
    ------
    KeyError
        If section missing or not a Mapping.
    """
    if name not in cfg or not isinstance(cfg[name], Mapping):
        raise KeyError(f"Missing required YAML section: {name}")
    return cfg[name]  # type: ignore[no-any-return]


@dataclass(frozen=True)
class StatutoryProfile:
    """
    Immutable statutory levy configuration (YAML-driven).

    Framework Compliance
    --------------------
    - CESSPIT: Immutable dataclass with frozen=True
    - CASPER: Pure configuration, no I/O
    - CCCDIR: Contract-explicit with all fields typed
    - GWTF: Fail-fast validation in __post_init__

    Backwards Compatibility
    -----------------------
    Older scenario YAMLs may omit statutory.grid_loss_pct.
    When missing, falls back to project.grid_loss_pct if present, else 0.0.

    Attributes
    ----------
    env_surcharge_pct : float
        Environmental surcharge rate (decimal 0.0-1.0).
    grid_loss_pct : float
        Grid transmission loss rate (decimal 0.0-1.0).
    success_fee_pct : float
        Success fee rate (decimal 0.0-1.0).
    social_services_levy_pct : float
        Social services contribution levy (SSCL) rate (decimal 0.0-1.0).
    sscl_enabled : bool
        Whether SSCL is enabled.
    sscl_pct : float
        SSCL rate (decimal 0.0-1.0).
    sscl_base : SSCLBase
        Base for SSCL calculation ("gross_revenue" or "net_revenue_after_grid_loss").
    """

    env_surcharge_pct: float
    grid_loss_pct: float
    success_fee_pct: float
    social_services_levy_pct: float
    sscl_enabled: bool
    sscl_pct: float
    sscl_base: SSCLBase

    @classmethod
    def from_yaml(cls, cfg: Mapping[str, Any]) -> "StatutoryProfile":
        """
        Build StatutoryProfile from scenario YAML configuration.

        Type Safety Strategy
        --------------------
        Converts untyped YAML dict to strongly-typed StatutoryProfile through:
        1. Explicit type casts (float(), bool())
        2. Runtime validation in __post_init__()
        3. Fail-fast on missing or invalid keys

        Parameters
        ----------
        cfg : Mapping[str, Any]
            Full scenario configuration dict with 'statutory' section.

        Returns
        -------
        StatutoryProfile
            Validated, frozen statutory configuration.

        Raises
        ------
        KeyError
            If required YAML keys are missing.
        ValueError
            If values are outside valid ranges (validated in __post_init__).
        """
        s = _req_section(cfg, "statutory")

        # Backwards compatibility: prefer statutory.grid_loss_pct, else fall back
        proj = cfg.get("project")
        proj_grid_loss = None
        if isinstance(proj, Mapping) and "grid_loss_pct" in proj:
            proj_grid_loss = proj["grid_loss_pct"]

        grid_loss_raw = s.get(
            "grid_loss_pct", proj_grid_loss if proj_grid_loss is not None else 0.0
        )

        # Explicit type casts for all config parameters
        return cls(
            env_surcharge_pct=float(_req(s, "env_surcharge_pct", "statutory")),
            grid_loss_pct=float(grid_loss_raw),
            success_fee_pct=float(_req(s, "success_fee_pct", "statutory")),
            social_services_levy_pct=float(
                _req(s, "social_services_levy_pct", "statutory")
            ),
            sscl_enabled=bool(_req(s, "sscl_enabled", "statutory")),
            sscl_pct=float(_req(s, "sscl_pct", "statutory")),
            sscl_base=_req(s, "sscl_base", "statutory"),
        )

    def __post_init__(self) -> None:
        """
        Validate statutory configuration ranges.

        Type Safety
        -----------
        Runtime validation ensures all percentage values are within expected ranges,
        providing additional type safety beyond static type hints.

        Raises
        ------
        ValueError
            If any percentage field is outside [0.0, 1.0] range or sscl_base is invalid.
        """
        # Validate all percentage fields are in [0,1]
        for k in (
            "env_surcharge_pct",
            "grid_loss_pct",
            "success_fee_pct",
            "social_services_levy_pct",
            "sscl_pct",
        ):
            v = getattr(self, k)
            if not (0.0 <= v <= 1.0):
                raise ValueError(f"{k} must be in [0,1], got {v}")

        # Validate sscl_base literal
        if self.sscl_base not in ("gross_revenue", "net_revenue_after_grid_loss"):
            raise ValueError(f"statutory.sscl_base invalid: {self.sscl_base}")


__all__ = ["StatutoryProfile", "SSCLBase"]

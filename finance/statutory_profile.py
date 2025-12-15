"""Statutory Profile: SSCL, env surcharge, success fee, etc. (YAML-driven)"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping

SSCLBase = Literal["gross_revenue", "net_revenue_after_grid_loss"]


def _req(section: Mapping[str, Any], key: str, ctx: str) -> Any:
    if key not in section:
        raise KeyError(f"Missing required YAML key: {ctx}.{key}")
    return section[key]


def _req_section(cfg: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    if name not in cfg or not isinstance(cfg[name], Mapping):
        raise KeyError(f"Missing required YAML section: {name}")
    return cfg[name]


@dataclass(frozen=True)
class StatutoryProfile:
    """Immutable statutory levy configuration (YAML-driven)."""

    env_surcharge_pct: float
    grid_loss_pct: float
    success_fee_pct: float
    social_services_levy_pct: float
    sscl_enabled: bool
    sscl_pct: float
    sscl_base: SSCLBase

    @classmethod
    def from_yaml(cls, cfg: Mapping[str, Any]) -> "StatutoryProfile":
        s = _req_section(cfg, "statutory")
        return cls(
            env_surcharge_pct=float(_req(s, "env_surcharge_pct", "statutory")),
            grid_loss_pct=float(_req(s, "grid_loss_pct", "statutory")),
            success_fee_pct=float(_req(s, "success_fee_pct", "statutory")),
            social_services_levy_pct=float(
                _req(s, "social_services_levy_pct", "statutory")
            ),
            sscl_enabled=bool(_req(s, "sscl_enabled", "statutory")),
            sscl_pct=float(_req(s, "sscl_pct", "statutory")),
            sscl_base=_req(s, "sscl_base", "statutory"),
        )

    def __post_init__(self) -> None:
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
        if self.sscl_base not in ("gross_revenue", "net_revenue_after_grid_loss"):
            raise ValueError(f"statutory.sscl_base invalid: {self.sscl_base}")

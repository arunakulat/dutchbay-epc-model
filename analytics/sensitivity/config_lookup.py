from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


def _flatten_dict(
    d: Mapping[str, Any], parent_key: str = "", sep: str = "."
) -> dict[str, Any]:
    """Flatten a nested mapping using dot-separated keys.

    Example:
    {"tariff": {"lkr_per_kwh": 20.3}} -> {"tariff.lkr_per_kwh": 20.3}
    """
    items: dict[str, Any] = {}
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, Mapping):
            items.update(_flatten_dict(v, new_key, sep=sep))
        else:
            items[new_key] = v
    return items


@dataclass
class _ConfigLookup:
    flat: dict[str, Any]

    @classmethod
    def from_mapping(cls, cfg: Mapping[str, Any]) -> "_ConfigLookup":
        return cls(flat=_flatten_dict(cfg))

    def get(self, dotted: str) -> Any:
        # First try exact key.
        if dotted in self.flat:
            return self.flat[dotted]

        # Backwards-compat bridge for renamed tariff field.
        if dotted == "tariff.tariff_lkr_per_kwh" and "tariff.lkr_per_kwh" in self.flat:
            return self.flat["tariff.lkr_per_kwh"]

        # Otherwise, raise a clear KeyError.
        short = dotted.split(".")[-1]
        raise KeyError(f"Variable '{dotted}' not found in config at part '{short}'")

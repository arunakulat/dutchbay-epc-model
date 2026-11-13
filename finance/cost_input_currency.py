"""Refuse project-cost currency keys that the USD input contract cannot consume.

This guard does not convert money. Native LKR costs need a shared conversion
contract before debt, tax and cashflow can consume them consistently. Explicit
``tax.depreciable_capex_lkr`` and ``tax.dep_base_lkr`` remain tax-only inputs.
"""

from __future__ import annotations

from collections.abc import Mapping


def _lkr_keys(block: object) -> tuple[str, ...]:
    """Return native-LKR keys, including misspellings of unsupported amounts."""
    if not isinstance(block, Mapping):
        return ()
    return tuple(
        sorted(
            key
            for key in block
            if isinstance(key, str) and "lkr" in key.lower().split("_")
        )
    )


def opex_currency_is_supported(block: object) -> bool:
    """Check the opex block for native-LKR keys that would otherwise be ignored.

    The supported LKR escalation settings live inside ``opex.currency_split``;
    its component amounts are still USD equivalents and are validated separately.
    """
    return not _lkr_keys(block)


def capex_currency_is_supported(block: object) -> bool:
    """Check strict project-cost inputs; native-LKR tax bases belong under tax."""
    return not _lkr_keys(block)


def _section(raw: Mapping[str, object], name: str) -> Mapping[str, object]:
    """Read a section with the debt extractor's case-insensitive convention."""
    for key, value in raw.items():
        if key.lower() == name and isinstance(value, Mapping):
            return value
    return {}


def _has_usd_capex(raw: Mapping[str, object]) -> bool:
    """Detect a stated USD project cost across supported and legacy paths."""
    sections = (
        (
            "capex",
            (
                "usd_total",
                "epc_usd",
                "capex_total_usd",
                "total_capex_usd",
                "total_capex",
            ),
        ),
        ("finance", ("capex_total_usd", "capex_usd")),
        ("costs", ("capex_total_usd", "capex_usd", "total_capex_usd", "total_capex")),
    )
    for name, aliases in sections:
        block = {key.lower(): value for key, value in _section(raw, name).items()}
        if any(block.get(key) is not None for key in aliases):
            return True
        if name == "capex" and block.get("derive_from_breakdown"):
            return True
    roots = ("capex_usd_total", "capex_total_usd", "total_capex_usd")
    return any(key.lower() in roots and value is not None for key, value in raw.items())


def validate_cost_input_currencies(raw: Mapping[str, object]) -> None:
    """Reject ignored LKR opex and a tax-only LKR total beside USD project costs.

    Args:
        raw: Scenario configuration, before monetary amounts are resolved.

    Raises:
        ValueError: A native-LKR cost key is unsupported or ambiguous. The legacy
            direct-cashflow ``capex.lkr_total`` tax fallback is allowed only when
            no USD project cost is stated; strict preflight still requires USD.
    """
    opex_keys = _lkr_keys(_section(raw, "opex"))
    if opex_keys:
        paths = ", ".join(f"opex.{key}" for key in opex_keys)
        raise ValueError(
            f"{paths}: native-LKR opex amounts are unsupported; convert at an "
            "explicitly documented FX rate and provide opex.usd_per_year. "
            "Retain the original amount, currency, price date and FX source."
        )
    capex_keys = _lkr_keys(_section(raw, "capex"))
    if not capex_keys:
        return
    if all(key.lower() == "lkr_total" for key in capex_keys) and not _has_usd_capex(
        raw
    ):
        return
    paths = ", ".join(f"capex.{key}" for key in capex_keys)
    raise ValueError(
        f"{paths}: native-LKR project costs cannot be combined with the USD "
        "capex contract. Provide USD-equivalent project costs at documented FX; "
        "for an intentionally different tax-only basis use "
        "tax.depreciable_capex_lkr or tax.dep_base_lkr."
    )

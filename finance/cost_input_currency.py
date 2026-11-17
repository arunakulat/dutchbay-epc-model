"""Refuse project-cost currency keys that the USD input contract cannot consume.

This guard does not convert money. Native LKR costs need a shared conversion
contract before debt, tax and cashflow can consume them consistently. Explicit
``tax.depreciable_capex_lkr`` and ``tax.dep_base_lkr`` remain tax-only inputs.

A key is read as native LKR when ``lkr`` is one of its words, whether the words
are joined by underscores, hyphens, spaces or camelCase (``lkr_per_year``,
``lkr-per-year``, ``lkrPerYear``). The line items under ``capex.breakdown`` are
checked as well, because the debt engine sums them as USD when
``capex.derive_from_breakdown`` is set (#1745).
"""

from __future__ import annotations

import re
from collections.abc import Mapping

_COST_SECTIONS = ("capex", "opex")
_LOWER_THEN_UPPER = re.compile(r"([a-z0-9])([A-Z])")
_ACRONYM_THEN_WORD = re.compile(r"([A-Z]+)([A-Z][a-z])")
_SEPARATORS = re.compile(r"[^a-z0-9]+")


def _words(key: str) -> tuple[str, ...]:
    """Split a key into lower-case words across ``_``, ``-``, spaces and camelCase."""
    split = _ACRONYM_THEN_WORD.sub(r"\1_\2", _LOWER_THEN_UPPER.sub(r"\1_\2", key))
    return tuple(word for word in _SEPARATORS.split(split.lower()) if word)


def _is_lkr_key(key: object) -> bool:
    """Return true when ``lkr`` is one of the key's words."""
    return isinstance(key, str) and "lkr" in _words(key)


def _lkr_keys(block: object) -> tuple[str, ...]:
    """Return native-LKR keys, including misspellings of unsupported amounts."""
    if not isinstance(block, Mapping):
        return ()
    return tuple(sorted(key for key in block if _is_lkr_key(key)))


def _breakdown_lkr_paths(block: object, prefix: str) -> list[str]:
    """Return native-LKR line items at any depth under a ``breakdown`` mapping."""
    if not isinstance(block, Mapping):
        return []
    paths: list[str] = []
    for key, value in block.items():
        if not isinstance(key, str):
            continue
        path = f"{prefix}.{key}"
        if _is_lkr_key(key):
            paths.append(path)
        paths.extend(_breakdown_lkr_paths(value, path))
    return paths


def _capex_lkr_paths(block: object, prefix: str) -> list[str]:
    """Return a capex block's native-LKR keys and its native-LKR breakdown items."""
    if not isinstance(block, Mapping):
        return []
    paths = [f"{prefix}.{key}" for key in _lkr_keys(block)]
    for key, value in block.items():
        if isinstance(key, str) and key.lower() == "breakdown":
            paths.extend(_breakdown_lkr_paths(value, f"{prefix}.{key}"))
    return paths


def opex_currency_is_supported(block: object) -> bool:
    """Check the opex block for native-LKR keys that would otherwise be ignored.

    The supported LKR escalation settings live inside ``opex.currency_split``;
    its component amounts are still USD equivalents and are validated separately.
    """
    return not _lkr_keys(block)


def capex_currency_is_supported(block: object) -> bool:
    """Check strict project-cost inputs; native-LKR tax bases belong under tax."""
    return not _capex_lkr_paths(block, "capex")


def _sections(
    raw: Mapping[str, object], name: str
) -> tuple[tuple[str, Mapping[str, object]], ...]:
    """Inspect every case alias so an unused block cannot hide a cost input."""
    return tuple(
        (key, value)
        for key, value in raw.items()
        if isinstance(key, str) and key.lower() == name and isinstance(value, Mapping)
    )


def _non_mapping_sections(raw: Mapping[str, object]) -> list[str]:
    """Return cost sections, in any spelling, that hold something other than a block.

    A list or scalar under ``CAPEX`` or ``opex`` cannot be read by any resolver, so
    its amounts would be dropped without a word. An empty (null) section is absent.
    """
    return [
        f"{key} ({type(value).__name__})"
        for key, value in raw.items()
        if isinstance(key, str)
        and key.lower() in _COST_SECTIONS
        and value is not None
        and not isinstance(value, Mapping)
    ]


def has_usd_capex(raw: Mapping[str, object]) -> bool:
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
        for _, block in _sections(raw, name):
            for key, value in block.items():
                if isinstance(key, str) and value is not None:
                    if key.lower() in aliases:
                        return True
                    if (
                        name == "capex"
                        and key.lower() == "derive_from_breakdown"
                        and value
                    ):
                        return True
    roots = ("capex_usd_total", "capex_total_usd", "total_capex_usd")
    return any(
        isinstance(key, str) and key.lower() in roots and value is not None
        for key, value in raw.items()
    )


def validate_cost_input_currencies(raw: Mapping[str, object]) -> None:
    """Reject ignored LKR costs, unreadable cost sections and mixed capex currencies.

    Args:
        raw: Scenario configuration, before monetary amounts are resolved.

    Raises:
        ValueError: A cost section is not a mapping, or a native-LKR cost key is
            unsupported or ambiguous. That includes an LKR line item under
            ``capex.breakdown``, which the debt engine would sum as USD. The legacy
            direct-cashflow ``capex.lkr_total`` tax fallback is allowed only when
            no USD project cost is stated; strict preflight still requires USD.
    """
    unreadable = _non_mapping_sections(raw)
    if unreadable:
        raise ValueError(
            f"{', '.join(unreadable)}: a cost section must be a mapping of named "
            "amounts; no resolver reads a list or a scalar here, so its costs would "
            "be dropped. State the amounts under named keys such as capex.usd_total "
            "or opex.usd_per_year."
        )
    opex_paths = [
        f"{name}.{key}"
        for name, block in _sections(raw, "opex")
        for key in _lkr_keys(block)
    ]
    if opex_paths:
        paths = ", ".join(opex_paths)
        raise ValueError(
            f"{paths}: native-LKR opex amounts are unsupported; convert at an "
            "explicitly documented FX rate and provide opex.usd_per_year. "
            "Retain the original amount, currency, price date and FX source."
        )
    capex_sections = _sections(raw, "capex")
    capex_paths = [
        path for name, block in capex_sections for path in _capex_lkr_paths(block, name)
    ]
    if not capex_paths:
        return
    if (
        len(capex_sections) == 1
        and capex_paths == ["capex.lkr_total"]
        and not has_usd_capex(raw)
    ):
        return
    paths = ", ".join(capex_paths)
    raise ValueError(
        f"{paths}: native-LKR project costs cannot be combined with the USD "
        "capex contract. Provide USD-equivalent project costs at documented FX "
        "(a capex.breakdown line item is summed as USD); for an intentionally "
        "different tax-only basis use tax.depreciable_capex_lkr or tax.dep_base_lkr."
    )

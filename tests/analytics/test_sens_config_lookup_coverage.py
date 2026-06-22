#!/usr/bin/env python3
"""Coverage tests for analytics.sensitivity.config_lookup.

The module is a tiny, dependency-free config path-lookup layer:

- ``_flatten_dict`` collapses a nested mapping into dot-separated keys,
  recursing into sub-mappings and copying leaves verbatim.
- ``_ConfigLookup`` wraps the flattened dict and resolves dotted paths,
  with an exact-match branch, a backwards-compat bridge for the renamed
  ``tariff.tariff_lkr_per_kwh`` field, and a ``KeyError`` for unknown paths.

These tests exercise every branch with in-memory mappings; there is no
network, config-file, or matplotlib dependency to mock.
"""

from __future__ import annotations

from typing import Any

import pytest

from analytics.sensitivity.config_lookup import _ConfigLookup, _flatten_dict


def test_flatten_dict_flat_mapping_passthrough() -> None:
    """A flat mapping is returned key-for-key (no parent prefix)."""
    out = _flatten_dict({"a": 1, "b": "x"})
    assert out == {"a": 1, "b": "x"}


def test_flatten_dict_nested_uses_dotted_keys() -> None:
    """Nested mappings recurse into dot-separated keys (docstring example)."""
    out = _flatten_dict({"tariff": {"lkr_per_kwh": 20.3}})
    assert out == {"tariff.lkr_per_kwh": 20.3}


def test_flatten_dict_deeply_nested_and_mixed_leaves() -> None:
    """Multi-level nesting and non-mapping leaf values (list/None) are kept."""
    cfg: dict[str, Any] = {
        "top": 1,
        "a": {"b": {"c": 2}, "d": [1, 2, 3]},
        "e": None,
    }
    out = _flatten_dict(cfg)
    assert out == {
        "top": 1,
        "a.b.c": 2,
        "a.d": [1, 2, 3],
        "e": None,
    }


def test_flatten_dict_custom_separator() -> None:
    """The ``sep`` argument controls the joining character."""
    out = _flatten_dict({"a": {"b": 1}}, sep="/")
    assert out == {"a/b": 1}


def test_flatten_dict_with_parent_key_prefix() -> None:
    """A non-empty ``parent_key`` is prepended to every produced key."""
    out = _flatten_dict({"b": 1, "c": {"d": 2}}, parent_key="root")
    assert out == {"root.b": 1, "root.c.d": 2}


def test_flatten_dict_empty_mapping() -> None:
    """An empty mapping flattens to an empty dict."""
    assert _flatten_dict({}) == {}


def test_config_lookup_from_mapping_builds_flat() -> None:
    """``from_mapping`` stores the flattened representation."""
    lookup = _ConfigLookup.from_mapping({"tariff": {"lkr_per_kwh": 20.3}})
    assert lookup.flat == {"tariff.lkr_per_kwh": 20.3}


def test_config_lookup_get_exact_key() -> None:
    """An exact dotted key is returned directly."""
    lookup = _ConfigLookup.from_mapping({"tariff": {"lkr_per_kwh": 20.3}})
    assert lookup.get("tariff.lkr_per_kwh") == 20.3


def test_config_lookup_get_backwards_compat_bridge() -> None:
    """The renamed ``tariff.tariff_lkr_per_kwh`` resolves to ``tariff.lkr_per_kwh``."""
    lookup = _ConfigLookup.from_mapping({"tariff": {"lkr_per_kwh": 18.5}})
    assert lookup.get("tariff.tariff_lkr_per_kwh") == 18.5


def test_config_lookup_bridge_inactive_when_source_absent() -> None:
    """Without ``tariff.lkr_per_kwh`` present, the bridge key raises KeyError."""
    lookup = _ConfigLookup.from_mapping({"tariff": {"other": 1}})
    with pytest.raises(KeyError):
        lookup.get("tariff.tariff_lkr_per_kwh")


def test_config_lookup_get_missing_raises_keyerror_with_short_part() -> None:
    """An unknown dotted path raises KeyError naming the leaf part."""
    lookup = _ConfigLookup.from_mapping({"tariff": {"lkr_per_kwh": 20.3}})
    with pytest.raises(KeyError) as exc:
        lookup.get("debt.gearing_pct")
    msg = str(exc.value)
    assert "debt.gearing_pct" in msg
    assert "gearing_pct" in msg


def test_config_lookup_get_missing_single_segment_key() -> None:
    """A dotless unknown key reports itself as the short part."""
    lookup = _ConfigLookup.from_mapping({"a": 1})
    with pytest.raises(KeyError) as exc:
        lookup.get("nope")
    assert "nope" in str(exc.value)

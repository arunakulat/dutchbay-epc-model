#!/usr/bin/env python
"""Tests for the coastal/complex-terrain siting METADATA resolver (issue #742).

Diagnostics/provenance only — the terrain class is a self-declared metadata
label that applies NO AEP correction and feeds no billed quantity. These tests
pin: absent -> None (unset default), recognised class -> AEP-neutral block, and
fail-loud on an unknown class.
"""

from __future__ import annotations

import pytest

from analytics.wind.siting_metadata import (
    SITING_METADATA_NOTE,
    TERRAIN_CLASSES,
    resolve_siting_metadata,
)


def test_absent_siting_returns_none() -> None:
    """No resource.siting -> None (the metadata field defaults to UNSET)."""
    assert resolve_siting_metadata({}) is None
    assert resolve_siting_metadata({"siting": {}}) is None
    assert resolve_siting_metadata({"siting": {"terrain_class": None}}) is None


def test_recognised_class_returns_neutral_block() -> None:
    """A recognised class returns a block that NEVER applies an AEP correction."""
    block = resolve_siting_metadata({"siting": {"terrain_class": "coastal"}})
    assert block is not None
    assert block["terrain_class"] == "coastal"
    assert block["applies_aep_correction"] is False
    assert block["note"] == SITING_METADATA_NOTE
    assert "NO AEP correction" in block["note"]


def test_class_is_case_and_space_normalised() -> None:
    block = resolve_siting_metadata({"siting": {"terrain_class": "  Complex  "}})
    assert block is not None
    assert block["terrain_class"] == "complex"


def test_terrain_notes_passthrough() -> None:
    block = resolve_siting_metadata(
        {"siting": {"terrain_class": "coastal", "terrain_notes": "Kalpitiya spit"}}
    )
    assert block is not None
    assert block["terrain_notes"] == "Kalpitiya spit"


def test_all_recognised_classes_accepted() -> None:
    for cls in TERRAIN_CLASSES:
        block = resolve_siting_metadata({"siting": {"terrain_class": cls}})
        assert block is not None
        assert block["terrain_class"] == cls
        assert block["applies_aep_correction"] is False


def test_unknown_class_fails_loud() -> None:
    with pytest.raises(ValueError, match="not recognised"):
        resolve_siting_metadata({"siting": {"terrain_class": "mountainous"}})


def test_non_mapping_siting_fails_loud() -> None:
    with pytest.raises(ValueError, match="must be a mapping"):
        resolve_siting_metadata({"siting": ["coastal"]})

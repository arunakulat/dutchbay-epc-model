"""Import-safe identity projection for the accepted engine manifest.

``VERSION`` and ``analytics/run_manifest.py`` remain the authored sources.  This
generated leaf lets pure consumers recheck the exact D3B engine identity without
calling ``engine_version()``, which reads the filesystem.  Contract tests bind the
source paths, hashes and values back to those sources so drift fails closed.
"""

from __future__ import annotations

from typing import Final

ENGINE_VERSION_SOURCE_PATH: Final = "VERSION"
ENGINE_VERSION_SOURCE_SHA256: Final = (
    "03a2f5053a85e0c3557d022d98bf9bd043bf2b1b3b6a6db5339b1fc0ad6b86ba"
)
ENGINE_VERSION_IDENTITY: Final = "15.28.0"

MANIFEST_SCHEMA_SOURCE_PATH: Final = "analytics/run_manifest.py"
MANIFEST_SCHEMA_SOURCE_SHA256: Final = (
    "12f46ad04b8a5d17f5f5ff132308939b03e0a1ec776ea7e82eb591023b7ee6d7"
)
MANIFEST_SCHEMA_VERSION_IDENTITY: Final = "1.0"

__all__ = (
    "ENGINE_VERSION_IDENTITY",
    "ENGINE_VERSION_SOURCE_PATH",
    "ENGINE_VERSION_SOURCE_SHA256",
    "MANIFEST_SCHEMA_SOURCE_PATH",
    "MANIFEST_SCHEMA_SOURCE_SHA256",
    "MANIFEST_SCHEMA_VERSION_IDENTITY",
)

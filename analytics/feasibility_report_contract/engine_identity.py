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
    "959e72b86645360fe0e50d549fbd14d1ad9eca6d9cc6ec321fdd1d3967a8a2c3"
)
ENGINE_VERSION_IDENTITY: Final = "15.4.0"

MANIFEST_SCHEMA_SOURCE_PATH: Final = "analytics/run_manifest.py"
MANIFEST_SCHEMA_SOURCE_SHA256: Final = (
    "42cd5101682b77dc0111ccc5a7e8af58134b7c4c7d851fa90a6ced7a9bf3d09a"
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

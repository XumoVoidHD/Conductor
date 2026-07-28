"""Build and parse strategy artifact locations (local / S3 / GCS)."""
from __future__ import annotations

from shared.artifacts.store import ArtifactStoreError
from shared.artifacts.store import materialize
from shared.artifacts.store import materialize_to_temp
from shared.artifacts.store import read_text
from shared.artifacts.uri import ArtifactLocation
from shared.artifacts.uri import SUPPORTED_SCHEMES

__all__ = [
    "ArtifactLocation",
    "ArtifactStoreError",
    "SUPPORTED_SCHEMES",
    "materialize",
    "materialize_to_temp",
    "read_text",
]

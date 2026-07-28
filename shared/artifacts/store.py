"""Fetch strategy artifacts from local disk, S3, or GCS to a local path."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from shared.artifacts.uri import ArtifactLocation
from shared.env import REPO_ROOT

# Cache downloads under repo data/ (Conductor + backend can share in subprocess mode)
ARTIFACT_CACHE_DIR = Path(
    os.getenv("CONDUCTOR_ARTIFACT_CACHE", str(REPO_ROOT / "data" / "artifact_cache")),
)


class ArtifactStoreError(Exception):
    """Failed to resolve or download an artifact."""


def materialize(location: ArtifactLocation, *, dest_dir: Path | None = None) -> Path:
    """
    Resolve ``location`` to a local file path (download if needed).

    Returns path to the primary ``.py`` file (or extracted package entry).
    """
    if location.scheme == "local":
        return _materialize_local(location)
    if location.scheme == "s3":
        return _materialize_s3(location, dest_dir=dest_dir)
    if location.scheme == "gs":
        return _materialize_gcs(location, dest_dir=dest_dir)
    raise ArtifactStoreError(f"Unsupported scheme: {location.scheme}")


def read_text(location: ArtifactLocation) -> str:
    """Read artifact source as UTF-8 text (materializes cloud objects first)."""
    path = materialize(location)
    return path.read_text(encoding="utf-8")


def _materialize_local(location: ArtifactLocation) -> Path:
    root = location.local_root_key
    base = REPO_ROOT / root
    path = (base / location.source_path).resolve()
    try:
        path.relative_to(base.resolve())
    except ValueError as exc:
        raise ArtifactStoreError(
            f"Local path escapes strategies root: {location.source_path}",
        ) from exc
    if not path.is_file():
        raise ArtifactStoreError(
            f"Local strategy file not found: {path} "
            f"(source_url={location.source_url}, source_path={location.source_path})",
        )
    return path


def _cache_path(location: ArtifactLocation, dest_dir: Path | None) -> Path:
    if dest_dir is not None:
        dest_dir.mkdir(parents=True, exist_ok=True)
        return dest_dir / Path(location.source_path).name

    safe = location.uri.replace("://", "_").replace("/", "_")
    target = ARTIFACT_CACHE_DIR / location.scheme / safe
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _materialize_s3(location: ArtifactLocation, *, dest_dir: Path | None) -> Path:
    bucket = location.bucket
    if not bucket:
        raise ArtifactStoreError(f"s3 source_url missing bucket: {location.source_url}")
    key = location.source_path
    dest = _cache_path(location, dest_dir)

    if dest.is_file() and dest.stat().st_size > 0:
        return dest

    try:
        import boto3
        from botocore.exceptions import BotoCoreError
        from botocore.exceptions import ClientError
    except ImportError as exc:
        raise ArtifactStoreError(
            "boto3 is required for s3:// artifacts. pip install boto3",
        ) from exc

    try:
        client = boto3.client("s3")
        client.download_file(bucket, key, str(dest))
    except (BotoCoreError, ClientError, OSError) as exc:
        raise ArtifactStoreError(
            f"Failed to download s3://{bucket}/{key}: {exc}",
        ) from exc

    if not dest.is_file():
        raise ArtifactStoreError(f"S3 download produced no file: {dest}")
    return dest


def _materialize_gcs(location: ArtifactLocation, *, dest_dir: Path | None) -> Path:
    bucket_name = location.bucket
    if not bucket_name:
        raise ArtifactStoreError(f"gs source_url missing bucket: {location.source_url}")
    blob_name = location.source_path
    dest = _cache_path(location, dest_dir)

    if dest.is_file() and dest.stat().st_size > 0:
        return dest

    try:
        from google.cloud import storage
        from google.cloud.exceptions import GoogleCloudError
    except ImportError as exc:
        raise ArtifactStoreError(
            "google-cloud-storage is required for gs:// artifacts. "
            "pip install google-cloud-storage",
        ) from exc

    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(str(dest))
    except (GoogleCloudError, OSError) as exc:
        raise ArtifactStoreError(
            f"Failed to download gs://{bucket_name}/{blob_name}: {exc}",
        ) from exc

    if not dest.is_file():
        raise ArtifactStoreError(f"GCS download produced no file: {dest}")
    return dest


def materialize_to_temp(location: ArtifactLocation) -> Path:
    """Download into a fresh temp directory (caller may clean up)."""
    tmp = Path(tempfile.mkdtemp(prefix="conductor-artifact-"))
    return materialize(location, dest_dir=tmp)

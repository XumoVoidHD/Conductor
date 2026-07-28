"""Build and parse strategy artifact locations (local / S3 / GCS)."""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


SUPPORTED_SCHEMES = frozenset({"local", "s3", "gs", "gcs"})


@dataclass(frozen=True)
class ArtifactLocation:
    """
    Location of a strategy artifact.

    DB stores ``source_url`` (base) and ``source_path`` (object/path) separately.
    Full URI is always derived via :meth:`uri`.

    Examples
    --------
    source_url=local://strategies, source_path=running_ping.py
      → local://strategies/running_ping.py

    source_url=s3://my-bucket, source_path=users/alice/ema_cross.py
      → s3://my-bucket/users/alice/ema_cross.py

    source_url=gs://my-bucket, source_path=vault/foo.py
      → gs://my-bucket/vault/foo.py
    """

    source_url: str
    source_path: str

    def __post_init__(self) -> None:
        url = self.source_url.strip().rstrip("/")
        path = self.source_path.strip().lstrip("/")
        if not url:
            raise ValueError("source_url is required")
        if not path:
            raise ValueError("source_path is required")
        object.__setattr__(self, "source_url", url)
        object.__setattr__(self, "source_path", path)

        parsed = urlparse(url)
        scheme = (parsed.scheme or "").lower()
        if scheme == "gcs":
            scheme = "gs"
        if scheme not in SUPPORTED_SCHEMES:
            raise ValueError(
                f"Unsupported source_url scheme '{parsed.scheme}'. "
                f"Use local://, s3://, or gs:// (GCP).",
            )

    @property
    def scheme(self) -> str:
        scheme = (urlparse(self.source_url).scheme or "").lower()
        return "gs" if scheme == "gcs" else scheme

    @property
    def uri(self) -> str:
        """Full locator built from source_url + source_path."""
        return f"{self.source_url}/{self.source_path}"

    @property
    def bucket(self) -> str | None:
        """Bucket name for s3/gs; None for local."""
        if self.scheme == "local":
            return None
        return urlparse(self.source_url).netloc or None

    @property
    def local_root_key(self) -> str:
        """For local://strategies the root folder name under the repo."""
        if self.scheme != "local":
            return ""
        parsed = urlparse(self.source_url)
        root = (parsed.netloc or parsed.path or "").strip("/")
        return root or "strategies"

    @classmethod
    def local_strategies(cls, filename: str) -> ArtifactLocation:
        name = filename.strip().replace("\\", "/").split("/")[-1]
        if not name.endswith(".py"):
            name = f"{name}.py"
        return cls(source_url="local://strategies", source_path=name)

    @classmethod
    def from_parts(cls, source_url: str, source_path: str) -> ArtifactLocation:
        return cls(source_url=source_url, source_path=source_path)

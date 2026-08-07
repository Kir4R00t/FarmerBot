"""Read consolidated exchange snapshots from Cloudflare R2.

The reader intentionally exposes a synchronous API because boto3 is synchronous.
Discord callers should run its network methods with ``asyncio.to_thread``.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
import re
import threading
import time
from typing import Any, Iterable, Mapping, Protocol


SNAPSHOT_FILENAME = "exchange-snapshot.json"
PARTITION_PATTERN = re.compile(
    r"(?:^|/)dt=(?P<date>\d{4}-\d{2}-\d{2})/hour=(?P<hour>\d{2})(?:/|$)"
)


class SnapshotReaderError(RuntimeError):
    """Base exception for snapshot-reader failures."""


class SnapshotConfigurationError(SnapshotReaderError):
    """The R2 client cannot be configured from the supplied settings."""


class SnapshotNotFoundError(SnapshotReaderError):
    """No matching consolidated snapshot exists."""


class InvalidSnapshotError(SnapshotReaderError):
    """An object exists but is not a valid exchange snapshot."""


class SnapshotStorageError(SnapshotReaderError):
    """R2 rejected or failed a storage operation."""


class S3Client(Protocol):
    """The small portion of the boto3 S3 client used by this class."""

    def list_objects_v2(self, **kwargs: Any) -> Mapping[str, Any]: ...

    def get_object(self, **kwargs: Any) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class SnapshotReference:
    """Metadata available without downloading a snapshot object."""

    key: str
    partition_time: datetime | None
    last_modified: datetime | None
    size: int | None


@dataclass(frozen=True, slots=True)
class ExchangeSnapshot:
    """A parsed, validated consolidated exchange snapshot."""

    key: str
    snapshot_id: str
    captured_at: datetime
    records: tuple[dict[str, Any], ...]

    @property
    def record_count(self) -> int:
        return len(self.records)


class R2SnapshotReader:
    """Generic, cache-aware reader for consolidated JSON snapshots in R2."""

    def __init__(
        self,
        *,
        client: S3Client,
        bucket: str,
        prefix: str = "",
        cache_ttl_seconds: float = 300,
        max_cached_snapshots: int = 8,
    ) -> None:
        bucket = bucket.strip()
        if not bucket:
            raise SnapshotConfigurationError("R2 bucket name cannot be empty.")
        if cache_ttl_seconds < 0:
            raise ValueError("cache_ttl_seconds cannot be negative")
        if max_cached_snapshots < 1:
            raise ValueError("max_cached_snapshots must be at least 1")

        self._client = client
        self.bucket = bucket
        self.prefix = prefix.strip().strip("/")
        if self.prefix:
            self.prefix += "/"

        self.cache_ttl_seconds = float(cache_ttl_seconds)
        self.max_cached_snapshots = max_cached_snapshots
        self._references_cache: tuple[SnapshotReference, ...] | None = None
        self._references_cached_at = 0.0
        self._snapshot_cache: OrderedDict[str, ExchangeSnapshot] = OrderedDict()
        self._lock = threading.RLock()

    @classmethod
    def from_env(
        cls,
        *,
        environ: Mapping[str, str] | None = None,
        cache_ttl_seconds: float = 300,
        max_cached_snapshots: int = 8,
    ) -> "R2SnapshotReader":
        """Build a reader from the R2 variables already loaded into the process.

        ``bot.main`` loads ``.env`` before constructing command modules, so this
        method does not silently read a file. Tests and scripts can pass an
        explicit mapping through ``environ``.
        """

        values = os.environ if environ is None else environ
        endpoint = (values.get("R2_ENDPOINT") or "").strip()
        access_key = (values.get("R2_ACCESS_KEY_ID") or "").strip()
        secret_key = (values.get("R2_SECRET_ACCESS_KEY") or "").strip()
        bucket = (
            values.get("R2_BUCKET")
            or values.get("R2_BUCKET_ID")
            or ""
        ).strip()
        prefix = (values.get("R2_SNAPSHOT_PREFIX") or "").strip()
        region = (values.get("R2_REGION") or "auto").strip()

        missing = [
            name
            for name, value in (
                ("R2_ENDPOINT", endpoint),
                ("R2_ACCESS_KEY_ID", access_key),
                ("R2_SECRET_ACCESS_KEY", secret_key),
                ("R2_BUCKET or R2_BUCKET_ID", bucket),
            )
            if not value
        ]
        if missing:
            raise SnapshotConfigurationError(
                "Missing R2 configuration: " + ", ".join(missing)
            )

        try:
            import boto3  # type: ignore
            from botocore.config import Config  # type: ignore
        except ImportError as exc:
            raise SnapshotConfigurationError(
                "boto3 is required for live R2 access. Install it in the bot "
                "environment and rebuild the container."
            ) from exc

        try:
            client = boto3.client(
                "s3",
                endpoint_url=endpoint,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region,
                config=Config(
                    signature_version="s3v4",
                    s3={"addressing_style": "path"},
                ),
            )
        except Exception as exc:
            raise SnapshotConfigurationError(
                "Could not create the R2 S3 client."
            ) from exc

        return cls(
            client=client,
            bucket=bucket,
            prefix=prefix,
            cache_ttl_seconds=cache_ttl_seconds,
            max_cached_snapshots=max_cached_snapshots,
        )

    def clear_cache(self) -> None:
        """Forget cached listings and downloaded snapshot contents."""

        with self._lock:
            self._references_cache = None
            self._references_cached_at = 0.0
            self._snapshot_cache.clear()

    def list_snapshot_references(
        self,
        *,
        force_refresh: bool = False,
    ) -> tuple[SnapshotReference, ...]:
        """List every consolidated snapshot below the configured prefix."""

        now = time.monotonic()
        with self._lock:
            cache_is_fresh = (
                self._references_cache is not None
                and now - self._references_cached_at < self.cache_ttl_seconds
            )
            if not force_refresh and cache_is_fresh:
                return self._references_cache or ()

        references: list[SnapshotReference] = []
        continuation_token: str | None = None

        try:
            while True:
                request: dict[str, Any] = {
                    "Bucket": self.bucket,
                    "Prefix": self.prefix,
                }
                if continuation_token:
                    request["ContinuationToken"] = continuation_token

                response = self._client.list_objects_v2(**request)
                for item in response.get("Contents", ()) or ():
                    key = str(item.get("Key") or "")
                    if not self._is_snapshot_key(key):
                        continue
                    references.append(
                        SnapshotReference(
                            key=key,
                            partition_time=self._partition_time_from_key(key),
                            last_modified=self._normalise_optional_datetime(
                                item.get("LastModified")
                            ),
                            size=self._normalise_optional_int(item.get("Size")),
                        )
                    )

                if not response.get("IsTruncated"):
                    break
                next_token = response.get("NextContinuationToken")
                if not next_token or next_token == continuation_token:
                    raise SnapshotStorageError(
                        "R2 returned a truncated listing without a new "
                        "continuation token."
                    )
                continuation_token = str(next_token)
        except SnapshotReaderError:
            raise
        except Exception as exc:
            raise SnapshotStorageError(
                f"Could not list snapshots in R2 bucket {self.bucket!r}."
            ) from exc

        result = tuple(references)
        with self._lock:
            self._references_cache = result
            self._references_cached_at = time.monotonic()
        return result

    def list_snapshot_keys(
        self,
        *,
        force_refresh: bool = False,
    ) -> tuple[str, ...]:
        """Return consolidated snapshot object keys."""

        return tuple(
            reference.key
            for reference in self.list_snapshot_references(
                force_refresh=force_refresh
            )
        )

    def load_snapshot(
        self,
        key: str,
        *,
        force_refresh: bool = False,
    ) -> ExchangeSnapshot:
        """Download and validate one snapshot by its exact R2 object key."""

        key = key.strip()
        if not key:
            raise ValueError("snapshot key cannot be empty")

        with self._lock:
            if not force_refresh and key in self._snapshot_cache:
                cached = self._snapshot_cache[key]
                self._snapshot_cache.move_to_end(key)
                return cached

        try:
            response = self._client.get_object(Bucket=self.bucket, Key=key)
            body = response.get("Body")
            if body is None:
                raise SnapshotStorageError(
                    f"R2 returned no body for snapshot {key!r}."
                )
            try:
                payload = body.read()
            finally:
                close = getattr(body, "close", None)
                if callable(close):
                    close()
        except SnapshotReaderError:
            raise
        except Exception as exc:
            raise SnapshotStorageError(
                f"Could not download R2 snapshot {key!r}."
            ) from exc

        snapshot = self._parse_snapshot(key, payload)
        with self._lock:
            self._snapshot_cache[key] = snapshot
            self._snapshot_cache.move_to_end(key)
            while len(self._snapshot_cache) > self.max_cached_snapshots:
                self._snapshot_cache.popitem(last=False)
        return snapshot

    def load_snapshots(
        self,
        keys: Iterable[str],
        *,
        force_refresh: bool = False,
    ) -> tuple[ExchangeSnapshot, ...]:
        """Load several exact keys in the order supplied by the caller."""

        return tuple(
            self.load_snapshot(key, force_refresh=force_refresh)
            for key in keys
        )

    def load_latest_snapshot(
        self,
        *,
        force_refresh: bool = False,
    ) -> ExchangeSnapshot:
        """Load the single newest snapshot."""

        return self.load_latest_snapshots(
            1,
            require_count=True,
            force_refresh=force_refresh,
        )[0]

    def get_latest_snapshot(
        self,
        *,
        force_refresh: bool = False,
    ) -> ExchangeSnapshot:
        """Compatibility alias for ``load_latest_snapshot``."""

        return self.load_latest_snapshot(force_refresh=force_refresh)

    def load_latest_snapshots(
        self,
        limit: int = 1,
        *,
        require_count: bool = False,
        force_refresh: bool = False,
    ) -> tuple[ExchangeSnapshot, ...]:
        """Load up to ``limit`` snapshots, ordered newest first.

        The ``dt=YYYY-MM-DD/hour=HH`` key partition written by NiFi is the
        efficient chronological index. Embedded ``captured_at`` values validate
        those selected partitions and order multiple snapshots within one hour.
        Re-uploading an old object therefore cannot make it the newest snapshot.

        Exact unpartitioned keys remain available through ``load_snapshot``, but
        they are not eligible for latest-N lookup because finding their true
        order would require downloading the entire historical data lake.
        """

        if limit < 1:
            raise ValueError("limit must be at least 1")

        references = self.list_snapshot_references(
            force_refresh=force_refresh
        )
        if not references:
            raise SnapshotNotFoundError(
                f"No {SNAPSHOT_FILENAME!r} objects were found below "
                f"{self.prefix!r}."
            )

        candidates = self._select_candidate_references(references, limit)
        snapshots = self.load_snapshots(
            (reference.key for reference in candidates),
            force_refresh=force_refresh,
        )
        for reference, snapshot in zip(candidates, snapshots):
            expected_partition = reference.partition_time
            actual_partition = snapshot.captured_at.replace(
                minute=0,
                second=0,
                microsecond=0,
            )
            if expected_partition != actual_partition:
                raise InvalidSnapshotError(
                    f"Snapshot {snapshot.key!r} was captured at "
                    f"{snapshot.captured_at.isoformat()}, but its key is in "
                    f"partition {expected_partition!s}."
                )
        newest_first = tuple(
            sorted(
                snapshots,
                key=lambda snapshot: (snapshot.captured_at, snapshot.key),
                reverse=True,
            )[:limit]
        )

        if require_count and len(newest_first) < limit:
            raise SnapshotNotFoundError(
                f"Requested {limit} snapshots, but only "
                f"{len(newest_first)} were available."
            )
        return newest_first

    def _select_candidate_references(
        self,
        references: tuple[SnapshotReference, ...],
        limit: int,
    ) -> tuple[SnapshotReference, ...]:
        partitioned = [
            reference
            for reference in references
            if reference.partition_time is not None
        ]
        if not partitioned:
            raise SnapshotNotFoundError(
                "Latest-snapshot lookup requires object keys partitioned as "
                "dt=YYYY-MM-DD/hour=HH. Use load_snapshot(key) for an exact "
                "unpartitioned object."
            )

        selected: list[SnapshotReference] = []
        partitioned.sort(key=self._reference_sort_key, reverse=True)
        for partition_time in sorted(
            {reference.partition_time for reference in partitioned},
            reverse=True,
        ):
            selected.extend(
                reference
                for reference in partitioned
                if reference.partition_time == partition_time
            )
            if len(selected) >= limit:
                break

        return tuple(selected)

    def _parse_snapshot(self, key: str, payload: Any) -> ExchangeSnapshot:
        try:
            if isinstance(payload, bytes):
                text = payload.decode("utf-8-sig")
            elif isinstance(payload, str):
                text = payload
            else:
                raise TypeError(
                    f"Expected bytes or str, got {type(payload).__name__}"
                )
            root = json.loads(text)
        except (UnicodeError, TypeError, json.JSONDecodeError) as exc:
            raise InvalidSnapshotError(
                f"Snapshot {key!r} is not valid UTF-8 JSON."
            ) from exc

        if not isinstance(root, list) or not root:
            raise InvalidSnapshotError(
                f"Snapshot {key!r} must contain a non-empty JSON array."
            )

        first = root[0]
        if not isinstance(first, dict):
            raise InvalidSnapshotError(
                f"Snapshot {key!r} contains a non-object record."
            )

        snapshot_id = str(first.get("snapshot_id") or "").strip()
        captured_raw = str(first.get("captured_at") or "").strip()
        if not snapshot_id or not captured_raw:
            raise InvalidSnapshotError(
                f"Snapshot {key!r} is missing snapshot_id or captured_at."
            )
        captured_at = self._parse_utc_timestamp(captured_raw, key)

        records: list[dict[str, Any]] = []
        for index, record in enumerate(root):
            if not isinstance(record, dict):
                raise InvalidSnapshotError(
                    f"Snapshot {key!r} record {index} is not an object."
                )
            record_snapshot_id = str(record.get("snapshot_id") or "").strip()
            record_captured_raw = str(record.get("captured_at") or "").strip()
            if record_snapshot_id != snapshot_id:
                raise InvalidSnapshotError(
                    f"Snapshot {key!r} contains inconsistent snapshot IDs."
                )
            if not record_captured_raw:
                raise InvalidSnapshotError(
                    f"Snapshot {key!r} record {index} has no captured_at."
                )
            record_captured_at = self._parse_utc_timestamp(
                record_captured_raw,
                key,
            )
            if record_captured_at != captured_at:
                raise InvalidSnapshotError(
                    f"Snapshot {key!r} contains inconsistent capture times."
                )

            normalised = dict(record)
            normalised["snapshot_id"] = snapshot_id
            normalised["captured_at"] = captured_raw
            records.append(normalised)

        return ExchangeSnapshot(
            key=key,
            snapshot_id=snapshot_id,
            captured_at=captured_at,
            records=tuple(records),
        )

    def _is_snapshot_key(self, key: str) -> bool:
        return (
            key == SNAPSHOT_FILENAME
            or key.endswith("/" + SNAPSHOT_FILENAME)
        )

    @staticmethod
    def _partition_time_from_key(key: str) -> datetime | None:
        match = PARTITION_PATTERN.search(key)
        if not match:
            return None
        try:
            return datetime.strptime(
                f"{match.group('date')} {match.group('hour')}",
                "%Y-%m-%d %H",
            ).replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    @staticmethod
    def _parse_utc_timestamp(value: str, key: str) -> datetime:
        normalised = value.strip()
        if normalised.endswith(("Z", "z")):
            normalised = normalised[:-1] + "+00:00"
        try:
            result = datetime.fromisoformat(normalised)
        except ValueError as exc:
            raise InvalidSnapshotError(
                f"Snapshot {key!r} has invalid timestamp {value!r}."
            ) from exc
        if result.tzinfo is None:
            raise InvalidSnapshotError(
                f"Snapshot {key!r} timestamp {value!r} has no timezone."
            )
        return result.astimezone(timezone.utc)

    @staticmethod
    def _normalise_optional_datetime(value: Any) -> datetime | None:
        if not isinstance(value, datetime):
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _normalise_optional_int(value: Any) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _reference_sort_key(
        reference: SnapshotReference,
    ) -> tuple[datetime, datetime, str]:
        oldest = datetime.min.replace(tzinfo=timezone.utc)
        return (
            reference.partition_time or oldest,
            reference.last_modified or oldest,
            reference.key,
        )


__all__ = [
    "ExchangeSnapshot",
    "InvalidSnapshotError",
    "R2SnapshotReader",
    "SnapshotConfigurationError",
    "SnapshotNotFoundError",
    "SnapshotReaderError",
    "SnapshotReference",
    "SnapshotStorageError",
]

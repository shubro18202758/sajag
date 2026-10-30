"""The local fetch cache: raw source bytes on the edge box, so ``parse()`` runs offline from it.

Layout (one directory per connector)::

    <cache_dir>/<connector>/<UTC stamp>.<ext>          the raw bytes of one fetch (untrusted data)
    <cache_dir>/<connector>/<UTC stamp>.meta.json      its metadata: captured_at, origin, sha256, size, blobs
    <cache_dir>/<connector>/latest.json                the newest entry's metadata
    <cache_dir>/<connector>/blobs/<name>               bytes an entry references by name (the GDELT export zip
                                                       that lastupdate.txt names, SACHET CAP details, WARC records)
    <cache_dir>/_outbox/<run_id>-<n>.json              redacted signal batches waiting for the oracle (publish)

Rules:

* The cache holds raw untrusted data on this box only: it is never committed, logged or served (no route of the
  service reads it, and nothing here logs a byte of it). Files are created ``0600`` in ``0700`` directories, the
  cache root included when the cache creates it (an existing root, such as a mounted volume, keeps the mode its
  operator gave it), and every name that comes from a remote document (a blob name) is checked against a strict
  pattern first.
* ``captured_at`` is when the bytes were fetched (live) or captured (``import-poc``: the capture file's mtime). It
  becomes the signals' ``fetched_at``, so their staleness is honest and derivable (``now - fetched_at``).
* Offline mode (and a live fetch that failed) reads :meth:`Cache.latest`, the newest entry, as ``cached-sample``.
* Retention: entries, blobs and outbox batches older than 72 h, and then the oldest files while the cache exceeds
  200 MB, are removed, whichever comes first, but never the newest entry of a connector nor the blobs it
  references (offline mode always has something honest to read).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

__all__ = [
    "Cache",
    "CacheEntry",
    "CacheError",
    "PruneReport",
    "STAMP_RE",
    "parse_stamp",
    "stamp_of",
]

STAMP_FMT = "%Y%m%dT%H%M%S%fZ"
STAMP_RE = re.compile(r"^\d{8}T\d{12}Z$")
_CONNECTOR_RE = re.compile(r"^[a-z][a-z0-9_]{1,40}$")
_EXT_RE = re.compile(r"^[a-z0-9]{1,8}$")
_BLOB_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_OUTBOX = "_outbox"
_DIR_MODE = 0o700
_FILE_MODE = 0o600

Origin = Literal["live", "import-poc"]
FetchMode = Literal["live", "cached-sample"]


class CacheError(Exception):
    """A cache name or entry that fails validation (never contains cached bytes)."""


def stamp_of(when: datetime) -> str:
    """``2026-10-24T14:15:30.123456Z`` → ``20261024T141530123456Z`` (sortable, unique per microsecond)."""
    return when.astimezone(UTC).strftime(STAMP_FMT)


def parse_stamp(stamp: str) -> datetime:
    if not STAMP_RE.match(stamp):
        raise CacheError("not a cache stamp")
    return datetime.strptime(stamp, STAMP_FMT).replace(tzinfo=UTC)


def _check(pattern: re.Pattern[str], value: str, what: str) -> str:
    if not isinstance(value, str) or not pattern.match(value) or ".." in value:
        raise CacheError(f"invalid {what} name")
    return value


def _write_atomic(path: Path, data: bytes) -> None:
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}-{secrets.token_hex(4)}")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, _FILE_MODE)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


@dataclass(frozen=True)
class CacheEntry:
    """One cached fetch. ``fetch_mode`` is ``live`` only for the entry a fetch just wrote in this cycle."""

    connector: str
    stamp: str
    path: Path
    captured_at: datetime
    fetch_mode: FetchMode
    origin: Origin
    sha256: str
    size: int
    blobs: tuple[str, ...] = ()
    #: written by hand for tests and sandbox seeding (``import-poc`` of a capture its README marks synthetic): the
    #: signals parsed from it are labelled ``SIMULATED`` (F-HONEST OSINT-5), never a real outlet's report
    synthetic: bool = False

    def read_bytes(self, max_bytes: int = 64 * 1024 * 1024) -> bytes:
        size = self.path.stat().st_size
        if size > max_bytes:
            raise CacheError(f"cache entry larger than {max_bytes} bytes")
        return self.path.read_bytes()

    def age_sec(self, now: datetime | None = None) -> float:
        now = now or datetime.now(UTC)
        return max(0.0, (now - self.captured_at).total_seconds())

    def as_cached(self) -> CacheEntry:
        return replace(self, fetch_mode="cached-sample")

    def blob_path(self, name: str) -> Path | None:
        """A blob of this entry's connector (``<connector>/blobs/<name>``), when present and validly named."""
        try:
            path = self.path.parent / "blobs" / _check(_BLOB_RE, name, "blob")
        except CacheError:
            return None
        return path if path.is_file() else None

    def meta(self) -> dict[str, object]:
        return {
            "connector": self.connector,
            "stamp": self.stamp,
            "file": self.path.name,
            "captured_at": self.captured_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "origin": self.origin,
            "sha256": self.sha256,
            "bytes": self.size,
            "blobs": list(self.blobs),
            **({"synthetic": True} if self.synthetic else {}),
        }


@dataclass(frozen=True)
class PruneReport:
    removed_files: int
    freed_bytes: int
    total_bytes: int


class Cache:
    """The fetch cache rooted at ``root`` (created on first write)."""

    def __init__(self, root: Path | str, *, retention_hours: float = 72.0, max_bytes: int = 200 * 1024 * 1024):
        self.root = Path(root)
        self.retention_sec = float(retention_hours) * 3600.0
        self.max_bytes = int(max_bytes)

    # ── paths ─────────────────────────────────────────────────────────────────────────────────────────────────

    def _ensure_root(self) -> None:
        """Create the root ``0700`` when it is missing. ``mkdir(parents=True)`` on a deeper path would give the
        root the umask's default mode (``0775`` here), so the root is created on its own and chmod-ed, which no
        umask can widen. Directories above the root are not the cache's and are left alone."""
        try:
            self.root.mkdir(mode=_DIR_MODE, parents=True)
        except FileExistsError:
            return
        os.chmod(self.root, _DIR_MODE)

    def _mkdir(self, path: Path) -> Path:
        self._ensure_root()
        path.mkdir(mode=_DIR_MODE, parents=True, exist_ok=True)
        return path

    def connector_dir(self, connector: str, *, create: bool = False) -> Path:
        d = self.root / _check(_CONNECTOR_RE, connector, "connector")
        return self._mkdir(d) if create else d

    def _blob_dir(self, connector: str, *, create: bool = False) -> Path:
        d = self.connector_dir(connector, create=create) / "blobs"
        return self._mkdir(d) if create else d

    # ── entries ───────────────────────────────────────────────────────────────────────────────────────────────

    def put(
        self,
        connector: str,
        data: bytes,
        ext: str,
        *,
        captured_at: datetime | None = None,
        origin: Origin = "live",
        blobs: Iterable[str] = (),
        now: datetime | None = None,
        synthetic: bool = False,
    ) -> CacheEntry:
        """Write one fetch as the connector's newest entry (``fetch_mode`` ``live``) and update ``latest.json``."""
        _check(_EXT_RE, ext, "extension")
        blob_names = tuple(_check(_BLOB_RE, b, "blob") for b in blobs)
        d = self.connector_dir(connector, create=True)
        when = (now or datetime.now(UTC)).astimezone(UTC)
        stamp = stamp_of(when)
        latest = self.latest(connector)
        if latest is not None and stamp <= latest.stamp:
            # strictly increasing stamps (a clock step back, or two writes in one microsecond): newest is last
            when = parse_stamp(latest.stamp) + timedelta(microseconds=1)
            stamp = stamp_of(when)
        while (d / f"{stamp}.{ext}").exists() or (d / f"{stamp}.meta.json").exists():
            when = when + timedelta(microseconds=1)
            stamp = stamp_of(when)
        path = d / f"{stamp}.{ext}"
        _write_atomic(path, data)
        entry = CacheEntry(
            connector=connector,
            stamp=stamp,
            path=path,
            captured_at=(captured_at or when).astimezone(UTC),
            fetch_mode="live",
            origin=origin,
            sha256=hashlib.sha256(data).hexdigest(),
            size=len(data),
            blobs=blob_names,
            synthetic=bool(synthetic),
        )
        meta = json.dumps(entry.meta(), sort_keys=True).encode()
        _write_atomic(d / f"{stamp}.meta.json", meta)
        _write_atomic(d / "latest.json", meta)
        return entry

    def _entry_from_meta(self, connector: str, meta: dict[str, object]) -> CacheEntry | None:
        try:
            stamp = str(meta["stamp"])
            parse_stamp(stamp)
            name = str(meta["file"])
            if not name.startswith(stamp + ".") or "/" in name or ".." in name:
                return None
            _check(_EXT_RE, name[len(stamp) + 1 :], "extension")
            path = self.connector_dir(connector) / name
            if not path.is_file():
                return None
            captured = datetime.fromisoformat(str(meta["captured_at"]).replace("Z", "+00:00")).astimezone(UTC)
            origin = str(meta.get("origin", "live"))
            blobs = tuple(_check(_BLOB_RE, str(b), "blob") for b in meta.get("blobs", []) or [])  # type: ignore[union-attr]
            return CacheEntry(
                connector=connector,
                stamp=stamp,
                path=path,
                captured_at=captured,
                fetch_mode="cached-sample",
                origin="import-poc" if origin == "import-poc" else "live",
                sha256=str(meta.get("sha256", "")),
                size=int(meta.get("bytes", path.stat().st_size)),  # type: ignore[arg-type]
                blobs=blobs,
                synthetic=meta.get("synthetic") is True,
            )
        except (KeyError, ValueError, TypeError, CacheError, OSError):
            return None

    def _read_meta(self, path: Path) -> dict[str, object] | None:
        try:
            if path.stat().st_size > 64 * 1024:
                return None
            doc = json.loads(path.read_text(encoding="utf-8"))
            return doc if isinstance(doc, dict) else None
        except (OSError, ValueError):
            return None

    def entries(self, connector: str) -> list[CacheEntry]:
        """Every valid entry of ``connector``, oldest first (each as ``cached-sample``)."""
        d = self.connector_dir(connector)
        if not d.is_dir():
            return []
        out: list[CacheEntry] = []
        for meta_path in sorted(d.glob("*.meta.json")):
            meta = self._read_meta(meta_path)
            entry = self._entry_from_meta(connector, meta) if meta else None
            if entry is not None:
                out.append(entry)
        return out

    def latest(self, connector: str) -> CacheEntry | None:
        """The newest entry (``latest.json``, else a directory scan), as ``cached-sample``; ``None`` when empty."""
        d = self.connector_dir(connector)
        if not d.is_dir():
            return None
        meta = self._read_meta(d / "latest.json")
        entry = self._entry_from_meta(connector, meta) if meta else None
        if entry is not None:
            return entry
        found = self.entries(connector)
        return found[-1] if found else None

    # ── blobs ─────────────────────────────────────────────────────────────────────────────────────────────────

    def put_blob(self, connector: str, name: str, data: bytes) -> Path:
        path = self._blob_dir(connector, create=True) / _check(_BLOB_RE, name, "blob")
        _write_atomic(path, data)
        return path

    def blob_path(self, connector: str, name: str) -> Path | None:
        try:
            path = self._blob_dir(connector) / _check(_BLOB_RE, name, "blob")
        except CacheError:
            return None
        return path if path.is_file() else None

    def read_blob(self, connector: str, name: str, max_bytes: int = 64 * 1024 * 1024) -> bytes | None:
        path = self.blob_path(connector, name)
        if path is None or path.stat().st_size > max_bytes:
            return None
        return path.read_bytes()

    # ── outbox (redacted signal batches awaiting the oracle) ──────────────────────────────────────────────────

    def outbox_dir(self, *, create: bool = False) -> Path:
        d = self.root / _OUTBOX
        return self._mkdir(d) if create else d

    def outbox_put(self, name: str, payload: bytes) -> Path:
        path = self.outbox_dir(create=True) / (_check(_BLOB_RE, name, "outbox") + ".json")
        _write_atomic(path, payload)
        return path

    def outbox_pending(self) -> list[Path]:
        d = self.outbox_dir()
        return sorted(p for p in d.glob("*.json") if p.is_file()) if d.is_dir() else []

    # ── retention ─────────────────────────────────────────────────────────────────────────────────────────────

    def _connectors(self) -> Iterator[str]:
        if not self.root.is_dir():
            return
        for d in sorted(self.root.iterdir()):
            if d.is_dir() and _CONNECTOR_RE.match(d.name):
                yield d.name

    def prune(self, now: datetime | None = None) -> PruneReport:
        """Apply retention (module docstring). Returns what was removed; never removes a newest entry."""
        now = (now or datetime.now(UTC)).astimezone(UTC)
        cutoff = now.timestamp() - self.retention_sec
        protected: set[Path] = set()
        candidates: list[tuple[float, list[Path]]] = []  # (age key, files removed together)
        for connector in self._connectors():
            d = self.connector_dir(connector)
            entries = self.entries(connector)
            newest = self.latest(connector)
            if newest is not None:
                protected.update({newest.path, d / f"{newest.stamp}.meta.json", d / "latest.json"})
                for b in newest.blobs:
                    protected.add(self._blob_dir(connector) / b)
            listed: set[Path] = set()
            for e in entries:
                group = [e.path, d / f"{e.stamp}.meta.json"]
                listed.update(group)
                if e.path not in protected:
                    candidates.append((parse_stamp(e.stamp).timestamp(), group))
            # leftovers: orphan payloads or metas (a crash between two writes), temp files
            for p in d.iterdir():
                if p.is_file() and p not in listed and p not in protected and p.name != "latest.json":
                    candidates.append((p.stat().st_mtime, [p]))
            bd = self._blob_dir(connector)
            if bd.is_dir():
                for p in bd.iterdir():
                    if p.is_file() and p not in protected:
                        candidates.append((p.stat().st_mtime, [p]))
        ob = self.outbox_dir()
        if ob.is_dir():
            for p in ob.iterdir():
                if p.is_file():
                    candidates.append((p.stat().st_mtime, [p]))

        removed = 0
        freed = 0

        def _remove(files: list[Path]) -> None:
            nonlocal removed, freed
            for f in files:
                try:
                    size = f.stat().st_size
                    f.unlink()
                except OSError:
                    continue
                removed += 1
                freed += size

        candidates.sort(key=lambda c: c[0])
        keep: list[tuple[float, list[Path]]] = []
        for key, files in candidates:
            if key < cutoff:
                _remove(files)
            else:
                keep.append((key, files))
        total = self.total_bytes()
        for _key, files in keep:  # oldest first
            if total <= self.max_bytes:
                break
            before = sum(f.stat().st_size for f in files if f.exists())
            _remove(files)
            total -= before
        return PruneReport(removed_files=removed, freed_bytes=freed, total_bytes=max(0, self.total_bytes()))

    def total_bytes(self) -> int:
        if not self.root.is_dir():
            return 0
        total = 0
        for p in self.root.rglob("*"):
            try:
                if p.is_file():
                    total += p.stat().st_size
            except OSError:
                continue
        return total

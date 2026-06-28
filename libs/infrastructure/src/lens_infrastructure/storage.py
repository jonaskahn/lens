"""Blob storage adapter: local filesystem with gzip compression.

The S3/MinIO backend (boto3) is not yet implemented; only the local
backend is supported today. An S3 backend can be added behind the same
:class:`BlobStoragePort` interface.
"""

from __future__ import annotations

import gzip
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

__all__ = [
    "AsyncLocalFileBlobStorage",
    "BlobStoragePort",
    "LocalFileBlobStorage",
]


class BlobStoragePort(Protocol):
    """Read/write/stream gzipped blobs from a key-addressable store."""

    def put(self, key: str, data: bytes) -> str: ...

    def get(self, key: str) -> bytes: ...

    @contextmanager
    def open_read(self, key: str) -> Iterator[bytes]: ...

    def delete(self, key: str) -> None: ...


@dataclass(frozen=True)
class LocalFileBlobStorage:
    """A local-filesystem implementation of :class:`BlobStoragePort`.

    Keys are relative paths under ``root``; content is gzip-compressed on
    write and decompressed on read.
    """

    root: Path

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        if not key or ".." in key:
            raise ValueError(f"invalid blob key: {key!r}")
        return self.root / key

    def put(self, key: str, data: bytes) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(path, "wb") as fh:
            fh.write(data)
        return key

    def get(self, key: str) -> bytes:
        path = self._path(key)
        with gzip.open(path, "rb") as fh:
            return fh.read()

    @contextmanager
    def open_read(self, key: str) -> Iterator[bytes]:
        yield self.get(key)

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()


@dataclass(frozen=True)
class AsyncLocalFileBlobStorage:
    """An async-friendly :class:`lens_application.pipeline.BlobStoragePort`.

    Wraps the sync :class:`LocalFileBlobStorage` and exposes ``async``
    methods so application use cases can ``await`` blob I/O without
    blocking. Suitable for the worker; production may swap in an
    S3/MinIO backend behind the same async interface.
    """

    inner: LocalFileBlobStorage

    async def put(self, key: str, data: bytes) -> str:
        return self.inner.put(key, data)

    async def get(self, key: str) -> bytes:
        return self.inner.get(key)

    async def delete(self, key: str) -> None:
        self.inner.delete(key)

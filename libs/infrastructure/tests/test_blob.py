"""Local-filesystem blob storage round-trip and edge cases."""

from __future__ import annotations

from pathlib import Path

import pytest

from lens_infrastructure.storage import LocalFileBlobStorage


def test_given_blob_when_put_then_gzipped_file_written(tmp_path: Path) -> None:
    storage = LocalFileBlobStorage(root=tmp_path)
    storage.put("snapshots/abc.html", b"<html>hello</html>")

    written = list(tmp_path.rglob("abc.html"))
    assert len(written) == 1
    assert written[0].is_file()


def test_given_blob_when_get_then_returns_original(tmp_path: Path) -> None:
    storage = LocalFileBlobStorage(root=tmp_path)
    payload = b"binary \x00\x01\x02 payload"
    storage.put("snapshots/x", payload)

    assert storage.get("snapshots/x") == payload


def test_given_blob_when_open_read_then_yields_bytes(tmp_path: Path) -> None:
    storage = LocalFileBlobStorage(root=tmp_path)
    storage.put("snapshots/y", b"data")
    with storage.open_read("snapshots/y") as chunk:
        assert chunk == b"data"


def test_given_blob_when_delete_then_file_gone(tmp_path: Path) -> None:
    storage = LocalFileBlobStorage(root=tmp_path)
    storage.put("snapshots/z", b"data")
    storage.delete("snapshots/z")
    assert not (tmp_path / "snapshots" / "z").exists()


def test_given_invalid_key_when_put_then_raises(tmp_path: Path) -> None:
    storage = LocalFileBlobStorage(root=tmp_path)
    with pytest.raises(ValueError):
        storage.put("../escape", b"data")
    with pytest.raises(ValueError):
        storage.put("", b"data")

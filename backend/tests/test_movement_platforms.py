"""Safe failure at the movement boundary when platform capabilities are absent."""
import ctypes
import errno
from types import SimpleNamespace

import pytest

from backend import movement


def test_unsupported_platform_retains_source_and_existing_destination(tmp_path, monkeypatch):
    source = tmp_path / "new.txt"
    source.write_bytes(b"source bytes")
    folder = tmp_path / "Work"
    folder.mkdir()
    destination = folder / source.name
    destination.write_bytes(b"existing bytes")
    info = tmp_path.stat()
    monkeypatch.setattr(movement.sys, "platform", "win32")
    with pytest.raises(OSError, match="macOS or Linux.*suggestions-only"):
        movement.move_document(tmp_path, (info.st_dev, info.st_ino), source.name,
                               movement.signature(source.stat()), "Work")
    assert source.read_bytes() == b"source bytes"
    assert destination.read_bytes() == b"existing bytes"


@pytest.mark.parametrize("platform", ["darwin", "linux"])
def test_missing_safe_rename_retains_source_and_destination(tmp_path, monkeypatch, platform):
    source = tmp_path / "new.txt"
    source.write_bytes(b"source bytes")
    folder = tmp_path / "Work"
    folder.mkdir()
    destination = folder / source.name
    destination.write_bytes(b"existing bytes")
    info = tmp_path.stat()
    monkeypatch.setattr(movement.sys, "platform", platform)
    monkeypatch.setattr(movement.ctypes, "CDLL", lambda *args, **kwargs: SimpleNamespace())
    with pytest.raises(OSError, match="safe rename.*unavailable.*suggestions-only"):
        movement.move_document(tmp_path, (info.st_dev, info.st_ino), source.name,
                               movement.signature(source.stat()), "Work")
    assert source.read_bytes() == b"source bytes"
    assert destination.read_bytes() == b"existing bytes"


@pytest.mark.parametrize("platform", ["darwin", "linux"])
@pytest.mark.parametrize("error", [errno.ENOSYS, errno.EINVAL, errno.EOPNOTSUPP])
def test_unsupported_safe_rename_retains_source_and_destination(tmp_path, monkeypatch, platform, error):
    source = tmp_path / "new.txt"
    source.write_bytes(b"source bytes")
    folder = tmp_path / "Work"
    folder.mkdir()
    destination = folder / source.name
    destination.write_bytes(b"existing bytes")
    info = tmp_path.stat()

    def unavailable(*args):
        ctypes.set_errno(error)
        return -1

    library = SimpleNamespace(renameatx_np=unavailable, renameat2=unavailable)
    monkeypatch.setattr(movement.sys, "platform", platform)
    monkeypatch.setattr(movement.ctypes, "CDLL", lambda *args, **kwargs: library)
    with pytest.raises(OSError, match="safe rename.*kernel or filesystem.*suggestions-only") as raised:
        movement.move_document(tmp_path, (info.st_dev, info.st_ino), source.name,
                               movement.signature(source.stat()), "Work")
    assert raised.value.errno == error
    assert source.read_bytes() == b"source bytes"
    assert destination.read_bytes() == b"existing bytes"

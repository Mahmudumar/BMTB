"""Update-check and download tests with all HTTP calls mocked."""
from contextlib import contextmanager
from pathlib import Path

import pytest

pytest.importorskip("PyQt5")
pytest.importorskip("requests")
pytest.importorskip("packaging")

import scripts.auto_updater as updater_module
from scripts.auto_updater import AutoUpdater


class FakeSignal:
    def __init__(self):
        self.values = []

    def emit(self, *args):
        self.values.append(args)


class FakeSignals:
    def __init__(self):
        self.progress = FakeSignal()
        self.update_percent = FakeSignal()
        self.finished = FakeSignal()


class FakeResponse:
    def __init__(self, payload=None, chunks=(), headers=None):
        self.payload = payload or {}
        self.chunks = chunks
        self.headers = headers or {}

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload

    def iter_content(self, chunk_size):
        yield from self.chunks

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeParent:
    def close(self):
        self.closed = True


@pytest.fixture
def updater(tmp_path, monkeypatch):
    monkeypatch.setattr(updater_module, "UPDATE_DOWNLOAD_FOLDER", tmp_path)
    return AutoUpdater(FakeParent())


def test_check_reports_newer_version(updater, monkeypatch):
    monkeypatch.setattr(
        updater_module.requests,
        "post",
        lambda *a, **k: FakeResponse({
            "latest_version": "99.0.0",
            "url": "https://example.invalid/update.exe",
            "notes": "Test release",
        }),
    )
    signals = FakeSignals()
    assert updater._check(signals) is True
    assert updater.get_update_available() is True
    assert updater.notes == "Test release"
    assert len(signals.finished.values) == 1


def test_check_reports_current_version(updater, monkeypatch):
    monkeypatch.setattr(
        updater_module.requests,
        "post",
        lambda *a, **k: FakeResponse({
            "latest_version": updater_module.APP_VERSION,
            "url": "https://example.invalid/update.exe",
        }),
    )
    assert updater._check(FakeSignals()) is False


def test_check_handles_server_failure(updater, monkeypatch):
    def fail(*args, **kwargs):
        raise updater_module.requests.ConnectionError("offline")
    monkeypatch.setattr(updater_module.requests, "post", fail)
    signals = FakeSignals()
    assert updater._check(signals) is None
    assert updater.get_update_available() is None
    assert len(signals.finished.values) == 1


def test_check_rejects_incomplete_server_response(updater, monkeypatch):
    monkeypatch.setattr(
        updater_module.requests,
        "post",
        lambda *a, **k: FakeResponse({"latest_version": "99.0.0"}),
    )
    assert updater._check(FakeSignals()) is False


def test_download_writes_chunks_and_reports_progress(updater, monkeypatch):
    updater.download_url = "https://example.invalid/package.exe"
    monkeypatch.setattr(
        updater_module.requests,
        "get",
        lambda *a, **k: FakeResponse(
            chunks=[b"first", b"", b"second"],
            headers={"content-length": "11"},
        ),
    )
    signals = FakeSignals()
    result = updater.download_update(signals)

    assert Path(result).read_bytes() == b"firstsecond"
    assert signals.progress.values == [("Started",)]
    assert signals.update_percent.values == [(45,), (100,)]
    assert len(signals.finished.values) == 1


def test_download_without_url_fails(updater):
    with pytest.raises(RuntimeError, match="No update URL"):
        updater.download_update(FakeSignals())


def test_failed_download_removes_partial_installer(updater, monkeypatch):
    updater.download_url = "https://example.invalid/broken.exe"

    class BrokenResponse(FakeResponse):
        def iter_content(self, chunk_size):
            yield b"partial"
            raise updater_module.requests.ConnectionError("interrupted")

    monkeypatch.setattr(
        updater_module.requests, "get", lambda *a, **k: BrokenResponse()
    )
    with pytest.raises(updater_module.requests.ConnectionError):
        updater.download_update(FakeSignals())
    assert not updater.installer_path.exists()

"""Local utility tests; no real network or Windows registry is touched."""
import hashlib
import sys
import types

import pytest


@pytest.fixture
def utils_module(tmp_path, monkeypatch):
    fake_winreg = types.ModuleType("winreg")
    for name, value in {
        "HKEY_CURRENT_USER": object(),
        "KEY_SET_VALUE": 2,
        "REG_SZ": 1,
    }.items():
        setattr(fake_winreg, name, value)
    fake_winreg.OpenKey = lambda *args: object()
    fake_winreg.SetValueEx = lambda *args: None
    fake_winreg.CloseKey = lambda *args: None
    monkeypatch.setitem(sys.modules, "winreg", fake_winreg)

    import scripts.utils as utils
    monkeypatch.setattr(utils, "RECOVERY_FILE", tmp_path / "recovery.key")
    return utils


def test_word_count_handles_empty_punctuation_and_words(utils_module):
    assert utils_module.count_words_in_string("") == 0
    assert utils_module.count_words_in_string("Hello, world!") == 2
    assert utils_module.count_words_in_string("one\ntwo 3") == 3


def test_recovery_key_is_stored_as_hash_not_plain_text(utils_module):
    code = "test-recovery-code"
    utils_module.set_recovery_key(code)
    stored = utils_module.RECOVERY_FILE.read_text()
    assert stored == hashlib.sha256(code.encode("utf-8")).hexdigest()
    assert code not in stored


def test_recovery_key_verification_success_and_failure(utils_module):
    utils_module.set_recovery_key("correct-code")
    assert utils_module.verify_recovery_key("correct-code") is True
    assert utils_module.verify_recovery_key("wrong-code") is False


def test_missing_recovery_file_is_not_valid(utils_module):
    assert utils_module.verify_recovery_key("anything") is False


def test_connected_to_server_handles_http_status_without_real_network(utils_module, monkeypatch):
    class Response:
        status_code = 204
    monkeypatch.setattr(utils_module.requests, "get", lambda *a, **k: Response())
    assert utils_module.connected_to_server("https://example.invalid") is True

    Response.status_code = 503
    assert utils_module.connected_to_server("https://example.invalid") is False


def test_connected_to_server_handles_connection_error(utils_module, monkeypatch):
    def fail(*args, **kwargs):
        raise utils_module.requests.ConnectionError("offline")
    monkeypatch.setattr(utils_module.requests, "get", fail)
    assert utils_module.connected_to_server("https://example.invalid") is False

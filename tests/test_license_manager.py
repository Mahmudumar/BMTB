"""Offline license parsing and signature-validation tests."""
import base64

import pytest

pytest.importorskip("PyQt5")
pytest.importorskip("cryptography")

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from scripts.license_manager import LicenseManager
import scripts.license_manager as license_module


def make_manager(public_key=None):
    manager = LicenseManager.__new__(LicenseManager)
    manager.public_key = public_key or "not a valid public key"
    manager.is_premium = False
    return manager


def test_license_format_and_parse_round_trip():
    manager = make_manager()
    payload = '{"device_id":"test-device"}'
    signature = "test-signature"
    formatted = manager.format_license(payload, signature)
    assert formatted == {
        "license_data": payload,
        "license_key": signature,
    }
    assert manager.parse_license(formatted) == (payload, signature)


@pytest.mark.parametrize("value", [None, "", "not-json", [], 42, {}])
def test_invalid_license_payload_is_rejected(value):
    manager = make_manager()
    with pytest.raises((ValueError, TypeError, KeyError)):
        manager.parse_license(value)


def test_invalid_signature_is_rejected_without_network_access():
    manager = make_manager()
    assert manager.verify_signature('{"device_id":"test-device"}', "invalid") is False
    assert manager.is_premium is False


def test_valid_signature_for_another_device_is_rejected(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    manager = make_manager(public_key)
    monkeypatch.setattr(license_module, "USER_APP_ID", "this-device")

    payload = '{"device_id":"another-device"}'
    signature = private_key.sign(
        payload.encode(), padding.PKCS1v15(), hashes.SHA256()
    )
    assert manager.verify_signature(payload, base64.b64encode(signature).decode()) is False
    assert manager.is_premium is False


def test_valid_signature_for_this_device_is_accepted(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    manager = make_manager(public_key)
    monkeypatch.setattr(license_module, "USER_APP_ID", "this-device")

    payload = '{"device_id":"this-device"}'
    signature = private_key.sign(
        payload.encode(), padding.PKCS1v15(), hashes.SHA256()
    )
    assert manager.verify_signature(payload, base64.b64encode(signature).decode()) is True
    assert manager.is_premium is True

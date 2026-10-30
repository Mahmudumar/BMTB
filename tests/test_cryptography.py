"""Tests for the vault encryption primitives; no real user data is used."""
import pytest

pytest.importorskip("cryptography")
pytest.importorskip("Crypto")
pytest.importorskip("PyQt5")

from scripts.password_manager import Cryptography, SimpleCipher, SimpleSubstitution


def test_dek_and_note_round_trip():
    crypto = Cryptography()
    dek = crypto.generate_new_DEK()
    encrypted = crypto.encrypt_note(dek, "A private thought\nwith a second line")
    assert encrypted != b"A private thought\nwith a second line"
    assert crypto.decrypt_note(dek, encrypted) == "A private thought\nwith a second line"


def test_password_derived_key_wraps_and_recovers_dek():
    crypto = Cryptography()
    salt = crypto.generate_salt()
    dek = crypto.generate_new_DEK()
    kek = crypto.derive_KEK("test-password", salt)
    wrapped = crypto.encrypt_DEK(kek, dek)
    assert crypto.decrypt_DEK(kek, wrapped) == dek


def test_wrong_password_cannot_unwrap_dek():
    from cryptography.fernet import InvalidToken

    crypto = Cryptography()
    salt = crypto.generate_salt()
    dek = crypto.generate_new_DEK()
    wrapped = crypto.encrypt_DEK(crypto.derive_KEK("correct", salt), dek)
    wrong_key = crypto.derive_KEK("incorrect", salt)
    with pytest.raises(InvalidToken):
        crypto.decrypt_DEK(wrong_key, wrapped)


def test_lock_discards_in_memory_keys():
    crypto = Cryptography()
    crypto.kek = b"temporary-kek"
    crypto.dek = b"temporary-dek"
    crypto.lock()
    assert crypto.kek is None
    assert crypto.dek is None


def test_password_hash_is_stable_sha256_hex():
    crypto = Cryptography()
    digest = crypto.pass_hash("example")
    assert len(digest) == 64
    assert digest == crypto.pass_hash("example")
    assert digest != crypto.pass_hash("different")


@pytest.mark.parametrize("text", ["", "plain text", "123", "Mixed Case!"])
def test_simple_cipher_round_trip(text):
    cipher = SimpleCipher(key=7)
    assert cipher.decrypt(cipher.encrypt(text)) == text


@pytest.mark.parametrize("text", ["", "abcXYZ", "spaces and punctuation !"])
def test_substitution_cipher_round_trip(text):
    cipher = SimpleSubstitution()
    assert cipher.decrypt(cipher.encrypt(text)) == text

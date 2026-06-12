import pytest

from cryptography.fernet import Fernet

from rfe.security.crypto import FieldCipher, cipher_from_env


def test_roundtrip():
    c = FieldCipher(Fernet.generate_key())
    blob = c.encrypt("alice@example.com")
    assert blob != "alice@example.com"        # actually ciphertext
    assert c.decrypt(blob) == "alice@example.com"


def test_ciphertext_is_nondeterministic():
    c = FieldCipher(Fernet.generate_key())
    assert c.encrypt("same") != c.encrypt("same")   # Fernet embeds a random IV


def test_wrong_key_cannot_decrypt():
    blob = FieldCipher(Fernet.generate_key()).encrypt("secret")
    with pytest.raises(Exception):
        FieldCipher(Fernet.generate_key()).decrypt(blob)


def test_cipher_from_env_reads_key(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("RFE_ENCRYPTION_KEY", key)
    c = cipher_from_env()
    assert c is not None
    assert c.decrypt(c.encrypt("x")) == "x"


def test_cipher_from_env_absent_returns_none(monkeypatch):
    monkeypatch.delenv("RFE_ENCRYPTION_KEY", raising=False)
    assert cipher_from_env() is None


def test_cipher_from_env_rejects_bad_key(monkeypatch):
    monkeypatch.setenv("RFE_ENCRYPTION_KEY", "not-a-valid-fernet-key")
    with pytest.raises(ValueError):
        cipher_from_env()

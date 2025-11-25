# tests/test_crypto.py

from medbox.core.utils.crypto import encrypt_str, decrypt_str


def test_encrypt_decrypt_str():
    secret = "bonjour le monde"

    encrypted = encrypt_str(secret)
    assert encrypted != secret
    assert isinstance(encrypted, str)

    decrypted = decrypt_str(encrypted)
    assert decrypted == secret


def test_encrypt_none():
    assert encrypt_str(None) is None
    assert decrypt_str(None) is None

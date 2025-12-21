# tests/test_crypto.py

from medbox.core.utils.crypto import decrypt_str, encrypt_str


def test_encrypt_decrypt_str() -> None:
    """Test encryption and decryption of strings."""
    secret = "bonjour le monde"  # noqa: S105

    encrypted = encrypt_str(secret)
    assert encrypted != secret
    assert isinstance(encrypted, str)

    decrypted = decrypt_str(encrypted)
    assert decrypted == secret


def test_encrypt_none():
    assert encrypt_str(None) is None
    assert decrypt_str(None) is None

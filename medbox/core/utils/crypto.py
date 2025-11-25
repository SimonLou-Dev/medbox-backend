# medbox/core/utils/crypto.py

from __future__ import annotations

import base64
import hashlib
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from medbox.core.config.settings import settings


def _build_fernet() -> Fernet:
    """
    Construit une clé Fernet à partir de la clé d'application.
    On dérive settings.encryption_key en clé 32 bytes base64.
    """
    raw = settings.encryption_key.encode("utf-8")
    digest = hashlib.sha256(raw).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


fernet = _build_fernet()


def encrypt_str(value: Optional[str]) -> Optional[str]:
    """
    Chiffre une chaîne en utilisant Fernet.
    Retourne None si value est None.
    """
    if value is None:
        return None
    token = fernet.encrypt(value.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_str(value: Optional[str]) -> Optional[str]:
    """
    Déchiffre une chaîne chiffrée Fernet.
    Retourne None si value est None.
    Si le déchiffrement échoue, lève InvalidToken.
    """
    if value is None:
        return None
    try:
        data = fernet.decrypt(value.encode("utf-8"))
        return data.decode("utf-8")
    except InvalidToken:
        # Ici tu peux décider : lever, log, ou retourner une valeur spéciale
        raise

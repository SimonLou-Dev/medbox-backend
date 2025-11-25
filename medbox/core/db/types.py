# medbox/core/db/types.py

from __future__ import annotations

from typing import Optional, Any

from sqlalchemy.types import TypeDecorator, String
from sqlalchemy.dialects.postgresql import VARCHAR

from medbox.core.utils.crypto import encrypt_str, decrypt_str


class EncryptedString(TypeDecorator):
    """
    Type SQLAlchemy pour stocker une string chiffrée.
    En DB : string chiffrée (VARCHAR)
    En Python : string en clair.
    """

    impl = String

    cache_ok = True  # important pour SQLAlchemy 2.0

    def load_dialect_impl(self, dialect):
        # PostgreSQL : VARCHAR
        return dialect.type_descriptor(VARCHAR())

    def process_bind_param(self, value: Optional[str], dialect) -> Optional[str]:
        """
        Appelé avant l'écriture en DB.
        On reçoit une valeur en clair -> on retourne une valeur chiffrée.
        """
        return encrypt_str(value)

    def process_result_value(self, value: Optional[str], dialect) -> Optional[str]:
        """
        Appelé lors de la lecture DB.
        On reçoit une valeur chiffrée -> on retourne du clair.
        """
        return decrypt_str(value)

    def process_literal_param(self, value: Any, dialect) -> Any:
        # Pas utilisé pour les requêtes paramétrées classiques, on laisse tomber.
        return value

# medbox/core/db/types.py

from __future__ import annotations

from typing import Any

from sqlalchemy.dialects.postgresql import VARCHAR
from sqlalchemy.types import String, TypeDecorator

from medbox.core.utils.crypto import decrypt_str, encrypt_str


class EncryptedString(TypeDecorator):
    """Type SQLAlchemy pour stocker une string chiffrée."""

    impl = String

    cache_ok = True  # important pour SQLAlchemy 2.0

    def load_dialect_impl(self, dialect) -> Any:
        """Choix du type de  champ en DB."""
        # PostgreSQL : VARCHAR
        return dialect.type_descriptor(VARCHAR())

    def process_bind_param(self, value: str | None, _) -> str | None:
        """Chiffre la valeure."""
        return encrypt_str(value)

    def process_result_value(self, value: str | None, dialect) -> str | None:
        """Déchiffre Value."""
        return decrypt_str(value)

    def process_literal_param(self, value: Any, dialect) -> Any:
        """IDK."""
        # Pas utilisé pour les requêtes paramétrées classiques, on laisse tomber.
        return value

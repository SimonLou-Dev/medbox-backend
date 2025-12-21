"""Configuration sensible pour production."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings


class SecuritySettings(BaseSettings):
    """Configuration de sécurité (TOUTES les variables DOIVENT être en env)."""

    # DANGER: Ne jamais commiter encryption_key en dur!
    # DOIT venir d'une variable d'environnement en production
    encryption_key: SecretStr = Field(
        ...,  # Obligatoire
        alias="ENCRYPTION_KEY",
        description="""
        Clé de chiffrement Fernet (base64-encoded).
        PRODUCTION: Utiliser Vault/AWS Secrets Manager, JAMAIS en dur dans code.

        Générer une clé:
            from cryptography.fernet import Fernet
            key = Fernet.generate_key()  # b'...'
            print(key.decode())
        """,
    )

    # Autres settings sensibles
    database_password: SecretStr = Field(alias="DATABASE_PASSWORD")
    keycloak_client_secret: SecretStr = Field(alias="KEYCLOAK_CLIENT_SECRET")
    redis_password: SecretStr | None = Field(default=None, alias="REDIS_PASSWORD")

    class Config:
        """Configuration Pydantic."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        # IMPORTANT: Récupérer des variables env uniquement
        case_sensitive = True


# ============================================================================
# PATTERN D'USAGE EN PRODUCTION
# ============================================================================

# .env.example (NE JAMAIS COMMITER LES VRAIS SECRETS)
"""
# Production - récupérer de Vault/AWS Secrets Manager
ENCRYPTION_KEY=gAAAAABm...  # Fernet key
DATABASE_PASSWORD=prod_db_password
KEYCLOAK_CLIENT_SECRET=prod_kc_secret
"""

# Code FastAPI
"""
from medbox.core.config.security import SecuritySettings

settings = SecuritySettings()
encryption_key = settings.encryption_key.get_secret_value()  # Déchiffrer SecretStr
"""

# TESTS
"""
En test, utiliser une clé de test dédiée:
TEST_ENCRYPTION_KEY=gAAAAABm_test_key_only_for_tests...
"""

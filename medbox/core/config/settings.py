from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # --- Database ---
    database_host: str = Field(alias="DATABASE_HOST")
    database_port: int = Field(default=5432, alias="DATABASE_PORT")
    database_user: str = Field(alias="DATABASE_USER")
    database_password: str = Field(alias="DATABASE_PASSWORD")
    database_name: str = Field(alias="DATABASE_NAME")

    def get_async_db_url(self):
        return f"postgresql+asyncpg://{str(self.database_user)}:{str(self.database_password)}@{self.database_host}:{self.database_port}/{self.database_name}"

    def get_sync_db_url(self):
        return f"postgresql+psycopg2://{str(self.database_user)}:{str(self.database_password)}@{self.database_host}:{self.database_port}/{self.database_name}"

    # --- Redis (for task queue, cache…) ---
    redis_url: str = Field(
        default="redis://redis:6379/0",
        alias="REDIS_URL"
    )

    # --- Keycloak / Auth ---
    keycloak_url: str = Field(default="http://keycloak:8080/", alias="KEYCLOAK_URL")
    keycloak_realm: str = Field(alias="KEYCLOAK_REALM")
    keycloak_client_id: str = Field(alias="KEYCLOAK_CLIENT_ID")
    keycloak_client_secret: str = Field(alias="KEYCLOAK_CLIENT_SECRET")

    # --- S3 / Object storage ---
    s3_endpoint: str = Field(alias="S3_ENDPOINT")
    s3_region: str = Field(alias="S3_REGION")
    s3_bucket: str = Field(alias="S3_BUCKET")
    s3_access_key: str = Field(alias="S3_ACCESS_KEY")
    s3_secret_key: str = Field(alias="S3_SECRET_KEY")

    # --- Security ---
    encryption_key: str = Field(
        default="changeme-super-secret-key-32bytes",  # doit faire 32 bytes
        alias="ENCRYPTION_KEY"
    )

    app_url: str = Field(alias="APP_URL", default="http://localhost:8000")
    url_prefix: str = Field(alias="URL_PREFIX", default="/api")

    # --- Misc ---
    environment: str = "development"

settings = Settings()

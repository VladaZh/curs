from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IDENTITY_")

    database_url: str = "postgresql+asyncpg://booking:booking@localhost:5432/identity"
    rabbitmq_url: str | None = None

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "identity"

    access_ttl_minutes: int = 15
    refresh_ttl_days: int = 30
    max_failed_attempts: int = 5
    lockout_minutes: int = 15

    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: str | None = None


settings = Settings()

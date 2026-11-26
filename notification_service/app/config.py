from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NOTIFICATION_")

    database_url: str = "postgresql+asyncpg://booking:booking@localhost:5432/notification"
    rabbitmq_url: str | None = None
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"

    reminder_hours_before: int = 3
    sms_enabled: bool = False

    dispatch_batch: int = 20
    dispatch_poll_seconds: float = 2.0
    lease_seconds: int = 120
    max_attempts: int = 8
    retry_base_seconds: int = 30
    retry_cap_seconds: int = 3600
    inbox_retention_days: int = 7

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_starttls: bool = True
    smtp_from: str = "Рестораны <no-reply@example.com>"


settings = Settings()

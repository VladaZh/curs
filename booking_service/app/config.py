from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BOOKING_")

    database_url: str = "postgresql+asyncpg://booking:booking@localhost:5435/booking"
    rabbitmq_url: str | None = None
    auto_create_schema: bool = False
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    hold_ttl_minutes: int = 10
    slot_minutes: int = 90


settings = Settings()

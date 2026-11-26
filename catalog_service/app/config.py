from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CATALOG_")

    database_url: str = "postgresql+asyncpg://booking:booking@localhost:5435/catalog"
    rabbitmq_url: str | None = None
    redis_url: str | None = None
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    cache_ttl_seconds: int = 300
    list_cache_ttl_seconds: int = 60
    seed_demo: bool = False


settings = Settings()

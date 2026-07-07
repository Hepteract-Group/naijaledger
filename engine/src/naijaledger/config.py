from pydantic_settings import BaseSettings, SettingsConfigDict


def load_settings() -> "Settings":
    return Settings()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://naijaledger:naijaledger@localhost:5432/naijaledger"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

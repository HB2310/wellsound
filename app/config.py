from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql://wellsound:wellsound@localhost:5432/wellsound"

    # Security
    secret_key: str = "dev_secret_change_in_production"
    session_expire_seconds: int = 28800  # 8 hours

    # Microsoft OAuth
    azure_client_id: str = ""
    azure_client_secret: str = ""
    azure_tenant_id: str = ""
    azure_redirect_uri: str = "http://localhost:8000/auth/callback"

    # App
    app_name: str = "WellSound"
    debug: bool = False
    load_seed_data: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Database ---
    database_url: str

    # --- Reddit API ---
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = ""

    # --- Google Search Console ---
    google_search_console_credentials_path: str = ""
    raw_retention_days: int = 7

    gemini_api_key: str = ""

    # --- App ---
    environment: str = "development"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """Cached so we only read/parse .env once per process."""
    return Settings()


settings = get_settings()
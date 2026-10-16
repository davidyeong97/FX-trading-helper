from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    LLM_API_KEY: str = ""
    LLM_PROVIDER: str = "openrouter"
    OPENROUTER_MODEL: str = "google/gemini-2.0-flash-001"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_SITE_URL: str = ""
    OPENROUTER_APP_NAME: str = "FX Trading Helper"
    SEARCH_API_KEY: str = ""
    SEARCH_TIMEOUT_SECONDS: float = 2.0
    SEARCH_MAX_RESULTS: int = 6
    SEARCH_CACHE_TTL_SECONDS: int = 120
    DB_URL: str = "sqlite:///./fx_helper.db"
    CORS_ALLOW_ORIGINS: str = "*"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ALLOW_ORIGINS.split(",") if o.strip()]


settings = Settings()

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    LLM_API_KEY: str = ""
    LLM_PROVIDER: str = "gemini"
    SEARCH_API_KEY: str = ""
    DB_URL: str = "sqlite:///./fx_helper.db"
    CORS_ALLOW_ORIGINS: str = "*"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ALLOW_ORIGINS.split(",") if o.strip()]


settings = Settings()

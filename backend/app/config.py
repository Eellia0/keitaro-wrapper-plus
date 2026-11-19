from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./keitaro.db"
    keitaro_base_url: str = ""
    keitaro_api_key: str = ""
    campaign_prefix: str = "test_surname_"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

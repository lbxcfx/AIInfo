from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_name: str = "ai-intel-radar"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    log_level: str = "INFO"

    database_url: str
    database_sync_url: str | None = None
    redis_url: str = "redis://127.0.0.1:6379/0"
    meilisearch_url: str = "http://127.0.0.1:7700"
    meilisearch_master_key: str = "change_me_in_production"
    github_token: str = Field(default="", repr=False)
    x_bearer_token: str = Field(default="", repr=False)

    llm_provider: str = "bigmodel"
    zai_api_key: str = Field(default="", repr=False)
    bigmodel_base_url: str = "https://open.bigmodel.cn/api/paas/v4/"
    bigmodel_timeout_seconds: int = 60
    bigmodel_max_retries: int = 3

    llm_model_relevance: str = "glm-4.5-air"
    llm_model_translation: str = "glm-4.5-air"
    llm_model_summary: str = "glm-5-turbo"
    llm_model_classification: str = "glm-5-turbo"
    llm_model_entity: str = "glm-5-turbo"
    llm_model_scoring: str = "glm-5-turbo"
    llm_model_audit: str = "glm-5.1"
    llm_temperature_classification: float = 0.2
    llm_temperature_summary: float = 0.3
    llm_temperature_scoring: float = 0.2
    llm_max_tokens_relevance: int = 1024
    llm_max_tokens_summary: int = 3000
    llm_max_tokens_scoring: int = 3000

    embedding_provider: str = "bigmodel"
    embedding_model: str = "embedding-3"
    embedding_dimensions: int = 1024
    embedding_batch_size: int = 64
    embedding_max_input_tokens: int = 3072


@lru_cache
def get_settings() -> Settings:
    return Settings()

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"
    public_base_url: str = "http://localhost:8000"

    # Twilio
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_whatsapp_from: str | None = None
    twilio_validate_signature: bool = False

    # Hugging Face (hosted inference via HuggingFaceEndpoint + ChatHuggingFace)
    # Requires a token (free tier works with rate limits).
    hf_token: str | None = Field(default=None, validation_alias="HUGGINGFACEHUB_API_TOKEN")
    hf_endpoint_model: str = "Qwen/Qwen2.5-1.5B-Instruct"
    hf_temperature: float = 0.2
    hf_max_new_tokens: int = 200

    # Storage
    database_url: str = "postgresql+psycopg://innovation:innovation@localhost:5432/innovation_hunt"
    redis_url: str = "redis://localhost:6379/0"
    leaderboard_key: str = "innovation_hunt:leaderboard"

    # Game
    connect_points: int = 10
    join_keyword: str = "join"


settings = Settings()

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration boundary for model integration."""

    model_config = SettingsConfigDict(env_prefix="INCIDENTLENS_", env_file=".env")

    gemini_model: str = Field(
        default="gemini-3-flash-preview", description="Configurable Gemini model."
    )
    google_api_key: str | None = Field(
        default=None,
        description="Gemini API key, never hard-coded.",
        validation_alias=AliasChoices("INCIDENTLENS_GOOGLE_API_KEY"),
    )
    max_agent_steps: int = Field(default=4, ge=1, le=20)
    max_model_retries: int = Field(default=1, ge=0, le=3)
    retry_backoff_base_ms: int = Field(default=100, ge=0, le=2000)
    max_retry_delay_ms: int = Field(default=2000, ge=0, le=10000)

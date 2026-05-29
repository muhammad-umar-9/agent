"""
Application configuration via environment variables.
Uses pydantic-settings for validation and type safety.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    groq_api_key: str = Field(
        ...,
        description="Groq API key",
    )
    groq_model: str = Field(
        default="llama-3.3-70b-versatile",
        description="Groq model identifier",
    )
    max_transcript_length: int = Field(
        default=100_000,
        description="Maximum transcript character length accepted",
    )
    min_transcript_length: int = Field(
        default=50,
        description="Minimum transcript character length to attempt processing",
    )
    confidence_threshold: float = Field(
        default=0.6,
        description="Items below this confidence score get escalated",
    )
    app_title: str = "Meeting-to-Action Pipeline"
    app_version: str = "2.0.0"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

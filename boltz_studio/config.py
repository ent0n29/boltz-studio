"""Configuration settings using Pydantic."""

from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_prefix="BOLTZ_STUDIO_",
        case_sensitive=False,
    )

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Paths
    db_path: str = "boltz_studio.db"

    # Job settings
    max_sequence_length: int = 2000
    min_sequence_length: int = 5
    job_retention_hours: int = 24
    cleanup_interval_hours: int = 1

    # Prediction defaults
    default_recycling_steps: int = 1
    default_sampling_steps: int = 50
    default_diffusion_samples: int = 1

    # Rate limiting
    requests_per_minute: int = 10


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience exports
settings = get_settings()
PACKAGE_ROOT = Path(__file__).parent

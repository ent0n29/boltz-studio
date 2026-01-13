"""Configuration settings using Pydantic."""

from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_prefix="BOLTZ_STUDIO_",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False  # Enable dev features like dev login (set True for local dev)

    # Paths
    db_path: str = "boltz_studio.db"
    data_dir: str = "data"  # Directory for job outputs, uploads, etc.

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

    # OAuth - Google
    google_client_id: str = ""
    google_client_secret: str = ""

    # OAuth - GitHub
    github_client_id: str = ""
    github_client_secret: str = ""

    # Session settings
    session_secret: str = ""  # Required for cookie signing
    session_duration_hours: int = 168  # 1 week default

    # App URL (for OAuth callbacks)
    app_url: str = "http://localhost:8000"

    # Modal.com cloud GPU settings
    use_modal_gpu: bool = True  # Enable cloud GPU via Modal when local GPU not available
    modal_max_designs: int = 100  # Max designs per job on Modal (cost control)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience exports
settings = get_settings()
PACKAGE_ROOT = Path(__file__).parent

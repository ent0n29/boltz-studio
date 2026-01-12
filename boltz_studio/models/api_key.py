"""API key models."""

from datetime import datetime

from pydantic import BaseModel, Field


class APIKeyCreate(BaseModel):
    """Create an API key."""

    name: str = Field(..., min_length=1, max_length=100)
    scopes: str = Field(default="read", pattern=r"^(read|write|read,write)$")
    expires_in_days: int | None = Field(None, ge=1, le=365)


class APIKeyPublic(BaseModel):
    """Public API key data (without the actual key)."""

    id: str
    name: str
    key_prefix: str  # First 8 chars of key for identification
    scopes: str
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime


class APIKeyCreated(BaseModel):
    """Response when creating a new API key (includes full key once)."""

    id: str
    name: str
    key: str  # Full key - only shown once!
    key_prefix: str
    scopes: str
    expires_at: datetime | None = None
    created_at: datetime


class APIKeyList(BaseModel):
    """List of API keys."""

    keys: list[APIKeyPublic]
    total: int

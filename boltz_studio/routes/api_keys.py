"""API key management routes."""

from fastapi import APIRouter, Depends, HTTPException

from ..logger import get_logger
from ..middleware import RequiredUser
from ..models.api_key import (
    APIKeyCreate,
    APIKeyCreated,
    APIKeyList,
)
from ..services.api_key_store import APIKeyStore, get_api_key_store

logger = get_logger("routes.api_keys")

router = APIRouter(prefix="/api/keys", tags=["api-keys"])


@router.post("", response_model=APIKeyCreated)
async def create_api_key(
    data: APIKeyCreate,
    user: RequiredUser,
    store: APIKeyStore = Depends(get_api_key_store),
) -> APIKeyCreated:
    """Create a new API key.

    The full key is only returned once in this response.
    Store it securely - it cannot be retrieved later.

    Args:
        data: Key configuration
        user: Authenticated user
        store: API key store

    Returns:
        Created key info including the full key
    """
    return store.create(user.id, data)


@router.get("", response_model=APIKeyList)
async def list_api_keys(
    user: RequiredUser,
    store: APIKeyStore = Depends(get_api_key_store),
) -> APIKeyList:
    """List all API keys for the current user.

    Args:
        user: Authenticated user
        store: API key store

    Returns:
        List of keys (without actual key values)
    """
    return store.list_user_keys(user.id)


@router.delete("/{key_id}")
async def delete_api_key(
    key_id: str,
    user: RequiredUser,
    store: APIKeyStore = Depends(get_api_key_store),
) -> dict:
    """Delete an API key.

    Args:
        key_id: Key ID
        user: Authenticated user
        store: API key store

    Returns:
        Success message

    Raises:
        404 if key not found or not owned by user
    """
    if not store.delete(key_id, user.id):
        raise HTTPException(status_code=404, detail="API key not found")

    return {"message": "API key deleted"}


@router.delete("")
async def revoke_all_keys(
    user: RequiredUser,
    store: APIKeyStore = Depends(get_api_key_store),
) -> dict:
    """Revoke all API keys for the current user.

    Args:
        user: Authenticated user
        store: API key store

    Returns:
        Number of keys revoked
    """
    count = store.revoke_all(user.id)
    return {"message": f"Revoked {count} API keys", "count": count}

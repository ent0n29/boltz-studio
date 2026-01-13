"""Authentication middleware and dependencies."""

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request

from ..logger import get_logger
from ..models import UserProfile
from ..services.session_store import SessionStore, get_session_store
from ..services.user_store import UserStore, get_user_store

logger = get_logger("auth")


async def get_current_user(
    request: Request,
    session_id: Annotated[str | None, Cookie()] = None,
    session_store: SessionStore = Depends(get_session_store),
    user_store: UserStore = Depends(get_user_store),
) -> UserProfile | None:
    """Get current authenticated user from session cookie.

    This dependency returns None if no valid session exists,
    allowing endpoints to work for both authenticated and anonymous users.

    Args:
        request: FastAPI request
        session_id: Session ID from cookie
        session_store: Session store dependency
        user_store: User store dependency

    Returns:
        UserProfile if authenticated, None otherwise
    """
    if not session_id:
        logger.info(f"Auth: No session_id cookie. Available cookies: {list(request.cookies.keys())}")
        return None

    session = session_store.get_valid_session(session_id)
    if not session:
        logger.info(f"Auth: Invalid/expired session: {session_id[:8]}...")
        return None

    user = user_store.get_full_profile(session["user_id"])
    if not user:
        # Session exists but user doesn't - clean up
        logger.warning(f"Auth: Session {session_id[:8]}... has no valid user, cleaning up")
        session_store.delete(session_id)
        return None

    return user


async def require_auth(
    user: Annotated[UserProfile | None, Depends(get_current_user)],
) -> UserProfile:
    """Dependency that requires authentication.

    Use this for endpoints that should only be accessible to logged-in users.

    Args:
        user: Current user from get_current_user

    Returns:
        UserProfile of authenticated user

    Raises:
        HTTPException: 401 if not authenticated
    """
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Cookie"},
        )
    return user


# Type aliases for cleaner route signatures
OptionalUser = Annotated[UserProfile | None, Depends(get_current_user)]
RequiredUser = Annotated[UserProfile, Depends(require_auth)]

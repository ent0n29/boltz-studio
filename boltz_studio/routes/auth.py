"""OAuth authentication routes."""

import secrets
from typing import Literal

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from ..config import settings
from ..logger import get_logger
from ..middleware import RequiredUser
from ..models import UserCreate, UserProfile
from ..services.session_store import get_session_store
from ..services.user_store import get_user_store

logger = get_logger("routes.auth")

router = APIRouter(prefix="/auth", tags=["auth"])

# Initialize OAuth
oauth = OAuth()

# Register Google OAuth
if settings.google_client_id:
    oauth.register(
        name="google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

# Register GitHub OAuth
if settings.github_client_id:
    oauth.register(
        name="github",
        client_id=settings.github_client_id,
        client_secret=settings.github_client_secret,
        access_token_url="https://github.com/login/oauth/access_token",
        authorize_url="https://github.com/login/oauth/authorize",
        api_base_url="https://api.github.com/",
        client_kwargs={"scope": "read:user user:email"},
    )


def _get_callback_url(provider: str) -> str:
    """Get OAuth callback URL for provider."""
    return f"{settings.app_url}/auth/callback/{provider}"


@router.get("/login/{provider}")
async def login(
    request: Request,
    provider: Literal["google", "github"],
) -> RedirectResponse:
    """Initiate OAuth login flow.

    Redirects user to the OAuth provider for authentication.

    Args:
        request: FastAPI request
        provider: OAuth provider (google or github)

    Returns:
        Redirect to OAuth provider
    """
    # Check if provider is configured
    if provider == "google" and not settings.google_client_id:
        raise HTTPException(400, "Google OAuth not configured")
    if provider == "github" and not settings.github_client_id:
        raise HTTPException(400, "GitHub OAuth not configured")

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)

    # Store state in session cookie
    redirect_uri = _get_callback_url(provider)
    client = getattr(oauth, provider)

    response = await client.authorize_redirect(request, redirect_uri, state=state)

    # Set state cookie for verification
    response.set_cookie(
        key="oauth_state",
        value=state,
        max_age=600,  # 10 minutes
        httponly=True,
        samesite="lax",
    )

    return response


@router.get("/callback/{provider}")
async def callback(
    request: Request,
    provider: Literal["google", "github"],
) -> RedirectResponse:
    """Handle OAuth callback.

    Exchanges authorization code for tokens, fetches user info,
    creates/updates user, and establishes session.

    Args:
        request: FastAPI request with OAuth callback params
        provider: OAuth provider (google or github)

    Returns:
        Redirect to app with session cookie set
    """
    # Verify state matches cookie
    state_cookie = request.cookies.get("oauth_state")
    state_param = request.query_params.get("state")

    if not state_cookie or state_cookie != state_param:
        raise HTTPException(400, "Invalid OAuth state - possible CSRF attack")

    try:
        client = getattr(oauth, provider)
        token = await client.authorize_access_token(request)
    except OAuthError as e:
        logger.error(f"OAuth error for {provider}: {e}")
        raise HTTPException(400, f"OAuth authentication failed: {e}")

    # Get user info based on provider
    if provider == "google":
        user_info = token.get("userinfo")
        if not user_info:
            user_info = await client.userinfo(token=token)

        user_data = UserCreate(
            provider="google",
            provider_user_id=user_info["sub"],
            email=user_info.get("email"),
            display_name=user_info.get("name", user_info.get("email", "User")),
            avatar_url=user_info.get("picture"),
        )

    elif provider == "github":
        # Fetch user profile
        resp = await client.get("user", token=token)
        profile = resp.json()

        # Fetch email (might be private)
        email = profile.get("email")
        if not email:
            email_resp = await client.get("user/emails", token=token)
            emails = email_resp.json()
            primary = next((e for e in emails if e.get("primary")), None)
            if primary:
                email = primary.get("email")

        user_data = UserCreate(
            provider="github",
            provider_user_id=str(profile["id"]),
            email=email,
            display_name=profile.get("name") or profile.get("login", "User"),
            avatar_url=profile.get("avatar_url"),
        )

    # Create or update user
    user_store = get_user_store()
    user = user_store.create_or_update(user_data)

    # Create session
    session_store = get_session_store()
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    session_id = session_store.create(
        user_id=user["id"],
        ip_address=client_ip,
        user_agent=user_agent,
    )

    # Redirect to app with session cookie
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key="session_id",
        value=session_id,
        max_age=settings.session_duration_hours * 3600,
        httponly=True,
        samesite="lax",
        secure=not settings.app_url.startswith("http://localhost"),
    )

    # Clear OAuth state cookie
    response.delete_cookie("oauth_state")

    logger.info(f"User logged in: {user['id']} via {provider}")
    return response


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict:
    """Logout and invalidate session.

    Args:
        request: FastAPI request
        response: FastAPI response

    Returns:
        Success message
    """
    session_id = request.cookies.get("session_id")

    if session_id:
        session_store = get_session_store()
        session_store.delete(session_id)

    response.delete_cookie("session_id")
    return {"message": "Logged out successfully"}


@router.get("/me")
async def get_current_user_profile(user: RequiredUser) -> UserProfile:
    """Get current authenticated user's profile.

    Args:
        user: Authenticated user from middleware

    Returns:
        User profile
    """
    return user


@router.get("/status")
async def get_auth_status(request: Request) -> dict:
    """Check authentication status without requiring auth.

    Useful for frontend to check if user is logged in.

    Args:
        request: FastAPI request

    Returns:
        Auth status with user info if authenticated
    """
    session_id = request.cookies.get("session_id")

    if not session_id:
        return {"authenticated": False}

    session_store = get_session_store()
    session = session_store.get_valid_session(session_id)

    if not session:
        return {"authenticated": False}

    user_store = get_user_store()
    user = user_store.get_full_profile(session["user_id"])

    if not user:
        return {"authenticated": False}

    return {
        "authenticated": True,
        "user": user.model_dump(),
    }


@router.get("/dev-login")
async def dev_login(request: Request) -> RedirectResponse:
    """Development-only login that bypasses OAuth.

    Creates a test user and session for local development testing.
    Only works when debug mode is enabled.

    Args:
        request: FastAPI request

    Returns:
        Redirect to app with session cookie set
    """
    if not settings.debug:
        raise HTTPException(403, "Dev login only available in debug mode")

    # Create or get test user
    user_store = get_user_store()
    user_data = UserCreate(
        provider="dev",
        provider_user_id="dev-user-001",
        email=None,
        display_name="Dev User",
        avatar_url=None,
    )
    user = user_store.create_or_update(user_data)

    # Create session
    session_store = get_session_store()
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    session_id = session_store.create(
        user_id=user["id"],
        ip_address=client_ip,
        user_agent=user_agent,
    )

    # Redirect to app with session cookie
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key="session_id",
        value=session_id,
        max_age=settings.session_duration_hours * 3600,
        httponly=True,
        samesite="lax",
        secure=False,  # Allow HTTP for local dev
    )

    logger.info(f"Dev user logged in: {user['id']}")
    return response

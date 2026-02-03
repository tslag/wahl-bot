"""Authentication routes with refresh token support.

Exposes endpoints for issuing and rotating access/refresh tokens and
for revoking refresh tokens per-session or for all user sessions.

Endpoints:
    - POST /auth/token: Login (returns access + refresh tokens)
    - POST /auth/refresh: Exchange refresh token for new access token
    - POST /auth/logout: Revoke a single refresh token
    - POST /auth/logout-all: Revoke all user's refresh tokens
"""

from datetime import timedelta
from typing import Annotated

import jwt
from config.config import settings
from core.auth_helper import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    get_client_ip,
    get_current_active_user,
    get_device_info,
    revoke_all_user_tokens,
    revoke_refresh_token,
    store_refresh_token,
    verify_refresh_token,
)
from core.logging import logger
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from schemas.auth import AccessToken, User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", response_model=AccessToken)
async def login_for_access_token(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
):
    """Authenticate user and issue access + refresh tokens.

    Args:
        request: FastAPI request object used to determine cookie/secure flags.
        form_data: OAuth2 form containing `username` and `password`.

    Returns:
        JSONResponse: Access token in response body and refresh token set
            as an HttpOnly cookie.

    Raises:
        HTTPException: If authentication fails.
    """
    # NOTE: Verify credentials and load user from the DB for authentication.
    user = await authenticate_user(form_data.username, form_data.password)
    if not user:
        logger.warning("Failed login attempt for username=%s", form_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # NOTE: Access token lifetime is configured via settings.ACCESS_TOKEN_EXPIRE_MINUTES
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    # NOTE: Refresh tokens are longer lived (configured via settings)
    refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token, jti, expires_at = create_refresh_token(
        data={"sub": user.username}, expires_delta=refresh_token_expires
    )

    # NOTE: Storing refresh tokens server-side (or their JTI) enables revocation
    await store_refresh_token(
        user_id=user.id,
        token=refresh_token,
        jti=jti,
        expires_at=expires_at,
        device_info=get_device_info(request),
        ip_address=get_client_ip(request),
    )
    # NOTE: Return access token in body and set refresh token as HttpOnly cookie
    secure_flag = request.url.scheme == "https"
    body = {"access_token": access_token, "token_type": "bearer"}
    resp = JSONResponse(content=body)
    resp.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=secure_flag,
        samesite="lax",
        max_age=int(refresh_token_expires.total_seconds()),
        path="/",
    )
    logger.info("User %s logged in", user.username)
    return resp


@router.post("/refresh", response_model=AccessToken)
async def refresh_access_token(
    request: Request,
):
    """Exchange a refresh token (from cookie) for a new access token.

    Token rotation is performed: the old refresh token's JTI is revoked and
    a new refresh token is issued and stored.

    Args:
        request: FastAPI request object (expects refresh token in cookies).

    Returns:
        JSONResponse: New access token with rotated refresh token set as cookie.

    Raises:
        HTTPException: If no refresh token is provided or verification fails.
    """
    # NOTE: Refresh tokens are expected to be provided in an HttpOnly cookie
    # to reduce XSS exposure.
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token provided"
        )

    # Verify refresh token and get user
    user = await verify_refresh_token(refresh_token)
    logger.info("Refresh token used for user %s", getattr(user, "username", None))

    # Create new access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    # NOTE: Perform token rotation to mitigate refresh token reuse if stolen.
    # Decode old refresh token to get JTI and revoke it.
    try:
        payload = jwt.decode(
            refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        old_jti = payload.get("jti")
        if old_jti:
            await revoke_refresh_token(old_jti)
    except Exception:
        logger.exception("Failed to decode old refresh token during rotation")

    # Create new refresh token and persist for revocation tracking
    refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    new_refresh_token, jti, expires_at = create_refresh_token(
        data={"sub": user.username}, expires_delta=refresh_token_expires
    )

    # NOTE: Persist the rotated refresh token (JTI) to enable future revocation
    await store_refresh_token(
        user_id=user.id,
        token=new_refresh_token,
        jti=jti,
        expires_at=expires_at,
        device_info=get_device_info(request),
        ip_address=get_client_ip(request),
    )

    # NOTE: Return new access token and set rotated refresh token as cookie
    secure_flag = request.url.scheme == "https"
    body = {"access_token": access_token, "token_type": "bearer"}
    resp = JSONResponse(content=body)
    resp.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=secure_flag,
        samesite="lax",
        max_age=int(refresh_token_expires.total_seconds()),
        path="/",
    )
    logger.info("Issued new refresh token for user %s", user.username)
    return resp


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
):
    """Revoke a refresh token (logout).

    Args:
        request: FastAPI request object (reads refresh token from cookie).
        response: FastAPI response used to clear the refresh token cookie.

    Returns:
        dict: Success message on successful revoke.

    Raises:
        HTTPException: If refresh token is missing or invalid.
    """
    # NOTE: Expect refresh token in HttpOnly cookie; revoke by JTI lookup.
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        logger.warning("Logout attempted without refresh token")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No refresh token provided"
        )

    try:
        payload = jwt.decode(
            refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        jti = payload.get("jti")
        if jti:
            await revoke_refresh_token(jti)
            # Clear cookie
            response.delete_cookie("refresh_token", path="/")
            logger.info("User logged out, revoked jti=%s", jti)
            return {"message": "Successfully logged out"}
    except Exception:
        logger.exception("Error decoding refresh token during logout")

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid refresh token"
    )


@router.post("/logout-all")
async def logout_all_devices(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Revoke all refresh tokens for the current user (logout everywhere).

    Useful when a user suspects account compromise or wants to force
    re-authentication on all devices.
    """

    await revoke_all_user_tokens(current_user.id)
    logger.info("Revoked all refresh tokens for user id=%s", current_user.id)
    return {"message": "Successfully logged out from all devices"}


@router.get("/users/me/", response_model=User)
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Return the current authenticated user's information.

    Requires a valid access token (provided via Authorization header).
    """

    return current_user


@router.get("/users/me/sessions")
async def get_active_sessions(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Return active (non-revoked, unexpired) refresh token sessions.

    Returns a list of sessions including device info, IP and expiry.
    """
    from datetime import datetime, timezone

    from db.session import AsyncSessionLocal
    from models.auth import RefreshToken as RefreshTokenModel
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(RefreshTokenModel).filter(
                RefreshTokenModel.user_id == current_user.id,
                RefreshTokenModel.revoked == False,  # noqa: E712
                RefreshTokenModel.expires_at > datetime.now(timezone.utc),
            )
        )
        sessions = result.scalars().all()

        return {
            "active_sessions": [
                {
                    "id": session.id,
                    "device_info": session.device_info,
                    "ip_address": session.ip_address,
                    "created_at": session.created_at,
                    "expires_at": session.expires_at,
                }
                for session in sessions
            ]
        }

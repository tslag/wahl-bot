"""
Authentication routes with refresh token support.

ENDPOINTS:
1. POST /auth/token - Login (get access + refresh tokens)
2. POST /auth/refresh - Get new access token using refresh token
3. POST /auth/logout - Revoke refresh token
4. POST /auth/logout-all - Revoke all user's refresh tokens
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
    """
    Login endpoint - returns both access and refresh tokens.

    Flow:
    1. Validate username and password
    2. Create access token (short-lived)
    3. Create refresh token (long-lived)
    4. Store refresh token in database
    5. Return both tokens to client

    Client should:
    - Store access token in memory (or sessionStorage)
    - Store refresh token securely (httpOnly cookie or secure storage)
    - Use access token for API requests
    - Use refresh token when access token expires
    """
    # Authenticate user
    user = await authenticate_user(form_data.username, form_data.password)
    if not user:
        logger.warning("Failed login attempt for username=%s", form_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token (15-30 minutes)
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    # Create refresh token (7-30 days)
    refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token, jti, expires_at = create_refresh_token(
        data={"sub": user.username}, expires_delta=refresh_token_expires
    )

    # Store refresh token in database for revocation tracking
    await store_refresh_token(
        user_id=user.id,
        token=refresh_token,
        jti=jti,
        expires_at=expires_at,
        device_info=get_device_info(request),
        ip_address=get_client_ip(request),
    )
    # Return tokens - set refresh token as HttpOnly cookie
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
    """
    Refresh endpoint - get new access token using refresh token.

    Flow:
    1. Client sends refresh token
    2. Server validates refresh token (JWT valid, not revoked, not expired)
    3. Server issues new access token
    4. Optionally: issue new refresh token (token rotation)

    Token Rotation (optional but recommended):
    - Issue new refresh token with each refresh
    - Revoke old refresh token
    - Prevents refresh token reuse if stolen
    - Limits damage window
    """
    # Read refresh token from HttpOnly cookie
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

    # Token Rotation - issue new refresh token (more secure)
    # Decode old refresh token to get JTI and revoke it
    try:
        payload = jwt.decode(
            refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        old_jti = payload.get("jti")
        if old_jti:
            await revoke_refresh_token(old_jti)
    except Exception:
        logger.exception("Failed to decode old refresh token during rotation")

    # Create new refresh token
    refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    new_refresh_token, jti, expires_at = create_refresh_token(
        data={"sub": user.username}, expires_delta=refresh_token_expires
    )

    # Store new refresh token
    await store_refresh_token(
        user_id=user.id,
        token=new_refresh_token,
        jti=jti,
        expires_at=expires_at,
        device_info=get_device_info(request),
        ip_address=get_client_ip(request),
    )

    # Return new tokens - set new refresh token as HttpOnly cookie
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
    """
    Logout endpoint - revoke refresh token.

    Flow:
    1. Client sends refresh token
    2. Server marks it as revoked in database
    3. Client discards both tokens

    Note: Access tokens cannot be revoked (they're stateless JWTs)
    They'll remain valid until expiration (which is why they're short-lived)
    """
    # Read refresh token from cookie
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
    """
    Logout from all devices - revoke all user's refresh tokens.

    Use case:
    - User suspects account compromise
    - User wants to logout from all devices at once
    - Password change (force re-login everywhere)
    """
    await revoke_all_user_tokens(current_user.id)
    logger.info("Revoked all refresh tokens for user id=%s", current_user.id)
    return {"message": "Successfully logged out from all devices"}


@router.get("/users/me/", response_model=User)
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Get current user info (requires valid access token)."""
    return current_user


@router.get("/users/me/sessions")
async def get_active_sessions(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Get user's active sessions (non-revoked refresh tokens).

    Shows where user is logged in (device, IP, time).
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

"""
Enhanced authentication helper with refresh token support.

REFRESH TOKEN FLOW EXPLAINED:

1. LOGIN (/auth/token):
   - User provides username + password
   - Server validates credentials
   - Server creates:
     * Access Token (JWT, 15-30 min) - for API requests
     * Refresh Token (JWT, 7-30 days) - stored in DB, for getting new access tokens
   - Both tokens returned to client

2. API REQUESTS:
   - Client sends access token in Authorization header
   - Server validates access token
   - If valid: request succeeds
   - If expired: client must refresh

3. REFRESH (/auth/refresh):
   - Client sends refresh token
   - Server checks:
     * Is token valid JWT?
     * Does it exist in database?
     * Is it not revoked?
     * Has it not expired?
   - If all checks pass: issue new access token (and optionally new refresh token)
   - Return new token(s) to client

4. LOGOUT (/auth/logout):
   - Mark refresh token as revoked in database
   - Client discards tokens

5. SECURITY BENEFITS:
   - Access tokens are short-lived (less damage if stolen)
   - Refresh tokens can be revoked (logout, security breach)
   - Can track active sessions per user
   - Can implement "logout all devices"
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from config.config import settings
from core.logging import logger
from db.session import AsyncSessionLocal
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from models.auth import RefreshToken as RefreshTokenModel
from models.auth import User as UserModel
from pwdlib import PasswordHash
from schemas.auth import TokenData, User, UserInDB
from sqlalchemy import select

password_hash = PasswordHash.recommended()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def verify_password(plain_password, hashed_password):
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password):
    return password_hash.hash(password)


async def get_user(username: str):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(UserModel).filter(UserModel.username == username)
        )
        user = result.scalars().first()
        if user:
            logger.debug(
                "Loaded user from DB username=%s id=%s",
                username,
                getattr(user, "id", None),
            )
            return UserInDB.model_validate(user)


async def authenticate_user(username: str, password: str) -> UserInDB | bool:
    user = await get_user(username)
    if not user:
        logger.debug("Authentication failed: user not found username=%s", username)
        return False
    if not verify_password(password, user.hashed_password):
        logger.warning("Authentication failed: invalid password username=%s", username)
        return False
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    Create short-lived access token for API requests.

    Token contains:
    - sub: username (subject)
    - exp: expiration timestamp
    - token_type: "access" (to differentiate from refresh tokens)
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)

    to_encode.update({"exp": expire, "token_type": "access"})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def create_refresh_token(
    data: dict, expires_delta: timedelta | None = None
) -> tuple[str, str, datetime]:
    """
    Create long-lived refresh token.

    Token contains:
    - sub: username
    - exp: expiration timestamp (longer than access token)
    - token_type: "refresh" (to prevent using refresh token as access token)
    - jti: unique token ID (for database storage and revocation)
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

    # Generate unique token ID for revocation
    jti = secrets.token_urlsafe(32)

    to_encode.update({"exp": expire, "token_type": "refresh", "jti": jti})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt, jti, expire


async def store_refresh_token(
    user_id: int,
    token: str,
    jti: str,
    expires_at: datetime,
    device_info: str = None,
    ip_address: str = None,
):
    """
    Store refresh token in database for tracking and revocation.

    Why store in database?
    - Enables revocation (can't revoke stateless JWTs without storage)
    - Track active sessions per user
    - See login history
    - Implement "logout from all devices"
    """
    async with AsyncSessionLocal() as db:
        refresh_token = RefreshTokenModel(
            token=jti,  # Store JTI, not full token (saves space)
            user_id=user_id,
            expires_at=expires_at,
            device_info=device_info,
            ip_address=ip_address,
        )
        db.add(refresh_token)
        await db.commit()
    logger.info("Stored refresh token jti=%s for user_id=%s", jti, user_id)


async def verify_refresh_token(token: str) -> UserInDB | None:
    """
    Verify refresh token and return user if valid.

    Checks:
    1. Is token a valid JWT?
    2. Is token type "refresh"?
    3. Does token exist in database (via JTI)?
    4. Is token not revoked?
    5. Has token not expired?
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Decode JWT
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        username = payload.get("sub")
        token_type = payload.get("token_type")
        jti = payload.get("jti")

        # Verify token type
        if token_type != "refresh":
            raise credentials_exception

        if username is None or jti is None:
            raise credentials_exception

    except InvalidTokenError:
        raise credentials_exception

    # Check database
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(RefreshTokenModel).filter(
                RefreshTokenModel.token == jti,
                RefreshTokenModel.revoked == False,  # noqa: E712
            )
        )
        db_token = result.scalars().first()

        if not db_token:
            raise credentials_exception

        # Check expiration (redundant with JWT exp, but good practice)
        if db_token.expires_at < datetime.now(timezone.utc):
            raise credentials_exception

    # Get user
    user = await get_user(username)
    if user is None:
        raise credentials_exception
    logger.debug("Refresh token verified for username=%s", username)
    return user


async def revoke_refresh_token(jti: str):
    """
    Revoke a refresh token (logout).

    Marks token as revoked in database so it can't be used again.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(RefreshTokenModel).filter(RefreshTokenModel.token == jti)
        )
        token = result.scalars().first()
        if token:
            token.revoked = True
            await db.commit()
            logger.info("Revoked refresh token jti=%s", jti)


async def revoke_all_user_tokens(user_id: int):
    """
    Revoke all refresh tokens for a user (logout from all devices).
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(RefreshTokenModel).filter(
                RefreshTokenModel.user_id == user_id,
                RefreshTokenModel.revoked == False,  # noqa: E712
            )
        )
        tokens = result.scalars().all()
        for token in tokens:
            token.revoked = True
        await db.commit()
    logger.info(
        "Revoked all refresh tokens for user_id=%s (count=%d)", user_id, len(tokens)
    )


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    """
    Validate access token and return current user.

    Only accepts access tokens (token_type="access").
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        username = payload.get("sub")
        token_type = payload.get("token_type")

        # Ensure this is an access token, not a refresh token
        if token_type != "access":
            raise credentials_exception

        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username, token_type=token_type)
    except InvalidTokenError:
        logger.warning("Invalid access token provided")
        raise credentials_exception
    user = await get_user(username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def get_device_info(request: Request) -> str:
    """
    Extract device information from request headers.
    """
    user_agent = request.headers.get("user-agent", "Unknown")
    return user_agent[:255]  # Limit length


def get_client_ip(request: Request) -> str:
    """
    Extract client IP address from request.
    """
    # Check for proxy headers first
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "Unknown"

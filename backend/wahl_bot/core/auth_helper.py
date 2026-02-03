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
    """Verify a plain password against a stored hash.

    Args:
        plain_password: The clear-text password provided by the user.
        hashed_password: The stored password hash to verify against.

    Returns:
        bool: True if the password matches, False otherwise.
    """
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password):
    """Hash a plain password using the recommended algorithm.

    Args:
        password: Plain-text password to hash.

    Returns:
        str: The resulting password hash.
    """
    return password_hash.hash(password)


async def get_user(username: str):
    """Load a user record from the database by username.

    Args:
        username: The username to look up.

    Returns:
        UserInDB | None: Validated user model when found, otherwise None.
    """
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
    """Authenticate a user by username and password.

    Args:
        username: The username to authenticate.
        password: The plain-text password to verify.

    Returns:
        UserInDB | bool: The validated user object on success, or False.
    """
    user = await get_user(username)
    if not user:
        logger.debug("Authentication failed: user not found username=%s", username)
        return False
    if not verify_password(password, user.hashed_password):
        logger.warning("Authentication failed: invalid password username=%s", username)
        return False
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a short-lived access token for API requests.

    Args:
        data: Payload to include in the token (e.g. {"sub": username}).
        expires_delta: Optional timedelta to override the default expiry.

    Returns:
        str: Encoded JWT access token.
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
    """Create a long-lived refresh token and return its JTI and expiry.

    Args:
        data: Payload to include in the token (e.g. {"sub": username}).
        expires_delta: Optional timedelta to override the default expiry.

    Returns:
        tuple[str, str, datetime]: (encoded_token, jti, expires_at)
            where `jti` is a token identifier used for revocation tracking.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

    # NOTE: Generate unique token ID (JTI) for revocation tracking.
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
    """Persist refresh token metadata (JTI) for revocation and auditing.

    Args:
        user_id: ID of the user the token belongs to.
        token: The encoded refresh token (not stored; JTI stored instead).
        jti: Token identifier used to look up/revoke the token.
        expires_at: Expiration datetime of the refresh token.
        device_info: Optional device descriptor (browser/OS).
        ip_address: Optional client IP address.

    Notes:
        We store the JTI rather than full token to reduce storage of
        sensitive data while still allowing revocation and session tracking.
    """
    async with AsyncSessionLocal() as db:
        # NOTE: Store the JTI rather than the full token to reduce storage
        # of sensitive data and still allow revocation lookups.
        refresh_token = RefreshTokenModel(
            token=jti,
            user_id=user_id,
            expires_at=expires_at,
            device_info=device_info,
            ip_address=ip_address,
        )
        db.add(refresh_token)
        await db.commit()
    logger.info("Stored refresh token jti=%s for user_id=%s", jti, user_id)


async def verify_refresh_token(token: str) -> UserInDB | None:
    """Verify a refresh token and return the associated user if valid.

    This performs several checks: the token must be a valid JWT, have
    token_type "refresh", its JTI must exist in the database and not be
    revoked, and the stored expiry must not have passed.

    Args:
        token: The encoded refresh token provided by the client.

    Returns:
        UserInDB | None: The validated user when token is valid.

    Raises:
        HTTPException: If the token is invalid, revoked, expired, or not found.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # NOTE: Decode and validate JWT payload (will raise on invalid token)
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

    # NOTE: Confirm presence and non-revoked status of the JTI in DB
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
    """Mark a refresh token (identified by JTI) as revoked.

    Args:
        jti: The token identifier to revoke.

    Returns:
        None
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
    """Revoke all active refresh tokens for a user.

    This sets the `revoked` flag on all non-revoked tokens for the user,
    effectively logging the user out from all devices.

    Args:
        user_id: The ID of the user whose tokens should be revoked.

    Returns:
        None
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
    """Return the current user if active.

    Args:
        current_user: User object resolved by `get_current_user` dependency.

    Returns:
        User: The active user object.

    Raises:
        HTTPException: If the user is marked as disabled.
    """

    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def get_device_info(request: Request) -> str:
    """Extract device information (user-agent) from a request.

    Args:
        request: FastAPI request object.

    Returns:
        str: Truncated user-agent string (max 255 characters).
    """

    user_agent = request.headers.get("user-agent", "Unknown")
    return user_agent[:255]


def get_client_ip(request: Request) -> str:
    """Determine the client's IP address from the request.

    Prefers the `X-Forwarded-For` header when present (typical when
    the app is behind a proxy/load-balancer), otherwise falls back to the
    direct client address exposed by the ASGI server.

    Args:
        request: FastAPI request object.

    Returns:
        str: Client IP address or "Unknown" if it cannot be determined.
    """

    # NOTE: Check for proxy headers first to support deployments behind a
    # reverse proxy or load balancer that sets `X-Forwarded-For`.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "Unknown"

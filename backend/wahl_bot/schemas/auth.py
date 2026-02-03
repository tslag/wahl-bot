"""Pydantic schemas for authentication endpoints.

Includes token response/request shapes and user models used by the
authentication routes.
"""

from datetime import datetime

from pydantic import BaseModel


class AccessToken(BaseModel):
    """Response containing an access token.

    This response is used when the refresh token is stored in a secure
    cookie and should not be returned to JavaScript.
    """

    access_token: str
    token_type: str


class TokenRefresh(BaseModel):
    """Request body for refreshing the access token using a refresh token."""

    refresh_token: str


class TokenData(BaseModel):
    """Data extracted from a decoded JWT.

    Attributes:
        username: Subject (username) from the token.
        token_type: Either "access" or "refresh" indicating token purpose.
    """

    username: str | None = None
    token_type: str = "access"  # "access" or "refresh"


class User(BaseModel):
    """Public user representation returned by the API."""

    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None


class UserCreate(User):
    """Request body for creating a new user."""

    pass


class UserInDB(User):
    """Internal user model including DB-only fields."""

    id: int
    hashed_password: str
    created_at: datetime

    class Config:
        from_attributes = True

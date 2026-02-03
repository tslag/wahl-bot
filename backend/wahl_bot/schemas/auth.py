from datetime import datetime

from pydantic import BaseModel


class AccessToken(BaseModel):
    """
    Response containing only the access token. Used when refresh token
    is stored in an HttpOnly cookie and should not be returned to JS.
    """

    access_token: str
    token_type: str


class TokenRefresh(BaseModel):
    """Request body for refreshing access token."""

    refresh_token: str


class TokenData(BaseModel):
    """Data extracted from JWT token."""

    username: str | None = None
    token_type: str = "access"  # "access" or "refresh"


class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None


class UserCreate(User):
    pass


class UserInDB(User):
    id: int
    hashed_password: str
    created_at: datetime

    class Config:
        from_attributes = True

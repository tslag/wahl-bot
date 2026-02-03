"""Authentication models: users and refresh token tracking.

Models used for storing user accounts and refresh token JTIs for
revocation and session tracking.
"""

from db.session import Base
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


class User(Base):
    """Database model representing an application user.

    Attributes:
        id: Primary key.
        username: Unique login name.
        email: User email.
        full_name: Full display name.
        disabled: Whether the account is disabled.
        hashed_password: Password hash.
        created_at: Account creation timestamp.
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False, unique=True)
    email = Column(String, nullable=False, unique=True)
    full_name = Column(String, nullable=False)
    disabled = Column(Boolean, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RefreshToken(Base):
    """Refresh token metadata used for revocation and session tracking.

    We store the token `jti` and metadata so tokens may be revoked and
    active sessions can be enumerated.

    Attributes:
        id: Primary key.
        token: Stored JTI for the refresh token.
        user_id: Foreign key to `users.id`.
        expires_at: Expiration timestamp.
        created_at: Record creation timestamp.
        revoked: Boolean flag indicating revocation status.
        device_info: Optional device description (browser/OS).
        ip_address: Optional originating IP address.
    """

    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    revoked = Column(Boolean, default=False, nullable=False)

    # NOTE: Device/session tracking (optional but useful for audits)
    device_info = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)

    # Relationship to user
    user = relationship("User", backref="refresh_tokens")

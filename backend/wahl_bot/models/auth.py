from db.session import Base
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False, unique=True)
    email = Column(String, nullable=False, unique=True)
    full_name = Column(String, nullable=False)
    disabled = Column(Boolean, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RefreshToken(Base):
    """
    Refresh tokens stored in database for tracking and revocation.

    Why store refresh tokens?
    - Allows revoking tokens (logout, security breach)
    - Tracks user sessions across devices
    - Prevents token reuse after revocation
    """

    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    revoked = Column(Boolean, default=False, nullable=False)

    # Device/session tracking (optional but recommended)
    device_info = Column(String, nullable=True)  # Browser, OS, etc.
    ip_address = Column(String, nullable=True)

    # Relationship to user
    user = relationship("User", backref="refresh_tokens")

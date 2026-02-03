"""Database models for programs and their document pages.

This module defines the `Program` and `Document` SQLAlchemy models used to
store uploaded program metadata and per-page document content with
embeddings for retrieval.
"""

from db.session import Base
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


class Program(Base):
    """Database model for a program.

    Attributes:
        id: Primary key.
        name: Unique program name.
        created_at: Record creation timestamp.
    """

    __tablename__ = "programs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document", back_populates="program")


class Document(Base):
    """Database model for a program document page and its embedding.

    Attributes:
        id: Primary key.
        program_name: Foreign key referencing `Program.name`.
        page: Page number within the program PDF.
        content: Text content extracted from the page.
        embedding: Vector embedding (pgvector) for retrieval.
        created_at: Record creation timestamp.
    """

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    program_name = Column(String, ForeignKey("programs.name"), index=True)
    page = Column(Integer, index=True)
    content = Column(Text, nullable=False)
    # NOTE: Store 384-dimensional embeddings produced by the embedding model
    embedding = Column(Vector(384))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    program = relationship("Program", back_populates="document")

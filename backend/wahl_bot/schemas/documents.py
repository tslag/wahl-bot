"""Schemas for program documents and their embeddings."""

from datetime import datetime

from pydantic import BaseModel


class DocumentBase(BaseModel):
    """Base representation of a document page belonging to a program."""

    program_name: str
    page: int
    content: str


class DocumentCreate(DocumentBase):
    """Request body for creating a new document record."""

    pass


class DocumentResponse(DocumentBase):
    """Response returned for a stored document record."""

    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentWithEmbedding(DocumentResponse):
    """Document response including its embedding vector."""

    embedding: list[float]

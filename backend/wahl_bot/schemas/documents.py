from datetime import datetime

from pydantic import BaseModel


class DocumentBase(BaseModel):
    program_name: str
    page: int
    content: str


class DocumentCreate(DocumentBase):
    pass


class DocumentResponse(DocumentBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentWithEmbedding(DocumentResponse):
    embedding: list[float]

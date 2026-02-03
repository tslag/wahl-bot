"""Schemas for program requests and responses."""

from datetime import datetime

from pydantic import BaseModel


class ProgramBase(BaseModel):
    """Base representation of a program."""

    name: str

    class Config:
        from_attributes = True


class ProgramCreate(ProgramBase):
    """Schema for creating a new program."""

    pass


class ProgramResponse(ProgramBase):
    """Response returned for a stored program."""

    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ProgramListResponse(BaseModel):
    """Response containing a list of programs."""

    programs: list[ProgramResponse]

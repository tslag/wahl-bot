"""Schemas for program task requests and responses."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ProgramTaskBase(BaseModel):
    """Base representation of a program task."""
    program_name: str


class ProgramTaskRequest(ProgramTaskBase):
    """Request body for creating a new program task."""
    pass


class ProgramTaskResponse(ProgramTaskBase):
    """Response returned for a program task."""
    task_id: str
    program_action: str
    status: str
    created_at: datetime
    program_id: Optional[int] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    class Config:
        from_attributes = True

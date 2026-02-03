from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ProgramTaskBase(BaseModel):
    program_name: str


class ProgramTaskRequest(ProgramTaskBase):
    pass


class ProgramTaskResponse(ProgramTaskBase):
    task_id: str
    program_action: str
    status: str
    created_at: datetime
    program_id: Optional[int] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    class Config:
        from_attributes = True

from datetime import datetime

from pydantic import BaseModel


class ProgramBase(BaseModel):
    name: str

    class Config:
        from_attributes = True


class ProgramCreate(ProgramBase):
    pass


class ProgramResponse(ProgramBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ProgramListResponse(BaseModel):
    programs: list[ProgramResponse]

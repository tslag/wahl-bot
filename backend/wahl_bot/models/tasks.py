from db.session import Base
from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func


class ProgramTask(Base):
    __tablename__ = "program_tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String, index=True, unique=True)
    session_id = Column(String, index=True)
    program_name = Column(String)
    program_id = Column(Integer, nullable=True)
    program_action = Column(String)
    status = Column(String)
    error = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

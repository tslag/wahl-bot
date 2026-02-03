"""Models for tracking background program tasks.

`ProgramTask` is used to record ingestion/delete job status for programs.
"""

from db.session import Base
from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func


class ProgramTask(Base):
    """Represents a background task processing a program.

    Attributes:
        id: Primary key.
        task_id: UUID for tracking the background job.
        session_id: Session identifier for the client that created the job.
        program_name: Name of the program being processed.
        program_id: Optional DB id of the program.
        program_action: Action being performed (e.g., 'ingest', 'delete').
        status: Current state (pending, running, completed, failed).
        error: Optional error message if job failed.
        created_at: Job creation timestamp.
        completed_at: Optional completion timestamp.
    """

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

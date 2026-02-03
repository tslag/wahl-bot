"""Background ingestion helpers for program document indexing.

This module contains tasks that run in background workers to ingest and
delete program documents and to list available programs. Operations update
`ProgramTask` rows to reflect progress so the API can report task status.
"""

from datetime import datetime

from core.logging import logger
from db.session import AsyncSessionLocal
from models.tasks import ProgramTask
from services.doc_ingestion.program_store import ProgramStore
from services.doc_ingestion.vector_store import VectorStore
from sqlalchemy import select


async def ingest_program(task_id: str, program_name: str, session_id: str) -> None:
    """Ingest a program's documents into the vector index.

    This function updates the corresponding `ProgramTask` status as it runs
    so callers can monitor progress.

    Args:
        task_id: Unique identifier for the background task.
        program_name: The program to ingest documents for.
        session_id: Optional session identifier for tracing/logging.

    Returns:
        None

    Notes:
        Any exception is caught, recorded on the task row, and the task is
        marked as `failed` so the system can surface errors to operators.
    """
    async with AsyncSessionLocal() as db:

        result = await db.execute(
            select(ProgramTask).filter(ProgramTask.task_id == task_id)
        )
        task = result.scalars().first()

        if not task:
            return

        try:
            # NOTE: Persist the processing state early so callers see immediate progress.
            task.status = "processing"
            await db.commit()

            logger.info(
                "Starting ingestion for task %s program=%s", task_id, program_name
            )

            program_store = ProgramStore()
            program = await program_store.get_program(program_name=program_name)
            vector_store = VectorStore(program_name=program_name)
            await vector_store.create_index_for_program()

            logger.info(
                "Completed ingestion for task %s program=%s, updating task status",
                task_id,
                program_name,
            )
            task.program_id = program.id
            task.status = "completed"
            task.completed_at = datetime.now()
            await db.commit()

        except Exception as e:
            logger.exception("Error during ingestion processing for task %s", task_id)
            task.status = "failed"
            task.completed_at = datetime.now()
            task.error = str(e)
            await db.commit()


async def list_programs() -> dict:
    """Return a mapping of available programs.

    Returns:
        A dict with a `programs` key containing the list of programs.
    """
    program_store = ProgramStore()
    programs = await program_store.list_programs()
    return dict(programs=programs)


async def delete_program(task_id: str, program_name: str, session_id: str) -> None:
    """Delete a program and its vector index, updating the task status.

    Args:
        task_id: Unique identifier for the background task.
        program_name: The program to delete.
        session_id: Optional session identifier for tracing/logging.

    Returns:
        None
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ProgramTask).filter(ProgramTask.task_id == task_id)
        )
        task = result.scalars().first()

        if not task:
            return

        try:
            # NOTE: Persist processing state so the API can show the task is running.
            task.status = "processing"
            await db.commit()

            logger.info(
                "Starting deletion for task %s program=%s", task_id, program_name
            )

            vector_store = VectorStore(program_name=program_name)

            await vector_store.delete_index_for_program()
            program_store = ProgramStore()
            await program_store.delete_program(program_name=program_name)

            logger.info(
                "Completed deletion for task %s program=%s, updating task status",
                task_id,
                program_name,
            )
            task.status = "completed"
            task.completed_at = datetime.now()
            await db.commit()

        except Exception as e:
            logger.exception("Error during deletion processing for task %s", task_id)
            task.status = "failed"
            task.completed_at = datetime.now()
            task.error = str(e)
            await db.commit()

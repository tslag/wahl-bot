from datetime import datetime

from core.logging import logger
from db.session import AsyncSessionLocal
from models.tasks import ProgramTask
from services.doc_ingestion.program_store import ProgramStore
from services.doc_ingestion.vector_store import VectorStore
from sqlalchemy import select


async def ingest_program(task_id: str, program_name: str, session_id: str):
    async with AsyncSessionLocal() as db:

        result = await db.execute(
            select(ProgramTask).filter(ProgramTask.task_id == task_id)
        )
        task = result.scalars().first()

        if not task:
            return

        try:
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


async def list_programs():
    program_store = ProgramStore()
    programs = await program_store.list_programs()
    return dict(programs=programs)


async def delete_program(task_id: str, program_name: str, session_id: str):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ProgramTask).filter(ProgramTask.task_id == task_id)
        )
        task = result.scalars().first()

        if not task:
            return

        try:
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

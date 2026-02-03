"""Program management routes: upload, ingest and delete programs.

Routes create `ProgramTask` jobs for background ingestion/deletion and
expose listing of ingested programs.
"""

import uuid
from typing import Annotated, Optional

# NOTE: models and schemas are adapted to support task tracking for long
# running ingestion jobs.
from core.auth_helper import get_current_active_user
from core.logging import logger
from db.session import get_db
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Cookie,
    Depends,
    File,
    Form,
    Response,
    UploadFile,
)
from fastapi.responses import JSONResponse
from models.tasks import ProgramTask
from schemas.auth import User
from schemas.programs import ProgramListResponse
from schemas.tasks import ProgramTaskRequest, ProgramTaskResponse
from services.doc_ingestion.ingest import delete_program, ingest_program, list_programs
from services.doc_ingestion.program_store import ProgramStore
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/program", tags=["program"])


def get_session_id(session_id: Optional[str] = Cookie(None)):
    """Return or create a `session_id` cookie used to group background jobs.

    This function centralizes session cookie generation for endpoints that
    spawn background tasks.
    """

    if not session_id:
        session_id = str(uuid.uuid4())
    return session_id


@router.post("/upload")
async def upload_program(
    current_user: Annotated[User, Depends(get_current_active_user)],
    program_name: str = Form(...),
    file: UploadFile = File(...),
):
    """Upload a program file and persist it to the program store.

    Args:
        current_user: Authenticated user performing the upload.
        program_name: Name of the program being uploaded.
        file: Uploaded file object.

    Returns:
        JSONResponse: Success or error payload with saved file path on success.
    """

    try:
        program_store = ProgramStore()
        file_path = await program_store.safe_program(program_name, file)
        logger.info(
            "Uploaded program %s by user %s",
            program_name,
            getattr(current_user, "username", None),
        )
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": f"Program '{program_name}' uploaded successfully",
                "file_path": str(file_path),
            },
        )
    except Exception as error:
        # NOTE: surface a generic error to clients and log details server-side
        logger.exception("Error uploading program %s", program_name)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Error uploading file: {str(error)}",
            },
        )


@router.post("/ingest", response_model=ProgramTaskResponse)
async def ingest_documents(
    current_user: Annotated[User, Depends(get_current_active_user)],
    request: ProgramTaskRequest,
    background_tasks: BackgroundTasks,
    response: Response,
    session_id: str = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
):
    """Queue an ingestion background task and return the created `ProgramTask`.

    The endpoint sets a session cookie to correlate background jobs with a
    client session and persists a tracking `ProgramTask` record.
    """

    response.set_cookie(key="session_id", value=session_id, httponly=True)

    task_id = str(uuid.uuid4())

    task = ProgramTask(
        task_id=task_id,
        session_id=session_id,
        program_name=request.program_name,
        program_action="ingest",
        status="pending",
    )

    db.add(task)
    await db.commit()

    background_tasks.add_task(
        ingest_program,
        task_id=task_id,
        program_name=request.program_name,
        session_id=session_id,
    )

    return task


@router.get("/list", response_model=ProgramListResponse)
async def list_ingested_programs(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Return the list of ingested programs available in the store."""

    response = await list_programs()
    return response


@router.delete("/delete/{program_name}")
async def delete_ingested_program(
    program_name: str,
    background_tasks: BackgroundTasks,
    response: Response,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session_id: str = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
):
    """Queue a background job to delete a program and its vector index.

    Args:
        program_name: Name of the program to delete.
    Returns:
        ProgramTask: Tracking record for the deletion job.
    """
    response.set_cookie(key="session_id", value=session_id, httponly=True)

    task_id = str(uuid.uuid4())

    task = ProgramTask(
        task_id=task_id,
        session_id=session_id,
        program_name=program_name,
        program_action="delete",
        status="pending",
    )

    db.add(task)
    await db.commit()

    background_tasks.add_task(
        delete_program,
        task_id=task_id,
        program_name=program_name,
        session_id=session_id,
    )

    return task

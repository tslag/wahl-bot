import uuid
from typing import Annotated, Optional

# refactored models and schemas for task tracking
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
    if not session_id:
        session_id = str(uuid.uuid4())
    return session_id


@router.post("/upload")
async def upload_program(
    current_user: Annotated[User, Depends(get_current_active_user)],
    program_name: str = Form(...),
    file: UploadFile = File(...),
):
    """
    Description
    -----------
        API route to upload a program file
    Parameters
    ----------
        programName: str - Name of the program
        file: UploadFile - The uploaded file
    Returns
    --------
        result: JSON object with upload status and file path
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
    # session_id: str = Depends(get_session_id),
    # db: AsyncSession = Depends(get_db)
):
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
    """
    Description
    -----------
        API route to delete a program and its associated index within the vector store
    Parameters
    ----------
        program_name: str - Name of the program to delete
    Returns
    --------
        result: JSON object with deletion status
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

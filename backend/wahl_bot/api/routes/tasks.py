"""Task status routes used to check background job progress."""

from typing import Annotated

from core.auth_helper import get_current_active_user
from core.logging import logger
from db.session import get_db
from fastapi import APIRouter, Depends, HTTPException
from models.tasks import ProgramTask
from schemas.auth import User
from schemas.tasks import ProgramTaskResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}", response_model=ProgramTaskResponse)
async def get_task_status(
    task_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Return the status of a background `ProgramTask` by `task_id`.

    Args:
        task_id: UUID of the background task to query.
        current_user: Authenticated user making the request.
        db: Async database session (dependency-injected).

    Returns:
        ProgramTask: The matching task record.

    Raises:
        HTTPException: 404 if task is not found.
    """

    logger.debug(
        "Fetching task status task_id=%s requested by user=%s",
        task_id,
        getattr(current_user, "username", None),
    )
    result = await db.execute(
        select(ProgramTask).filter(ProgramTask.task_id == task_id)
    )
    task = result.scalars().first()

    if not task:
        logger.warning("Task not found task_id=%s", task_id)
        raise HTTPException(status_code=404, detail="Task not found")
    return task

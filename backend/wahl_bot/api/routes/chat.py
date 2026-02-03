"""Chat API routes.

Handles chat requests routed to a program-specific document index.
"""

from typing import Annotated

from core.auth_helper import get_current_active_user
from core.logging import logger
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from schemas.auth import User
from schemas.chat import ChatRequest, ChatResponse
from services.chat_bot import ChatBot

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/{program_name}", response_model=ChatResponse)
async def chat(
    jason_data: ChatRequest,
    program_name: str,
    current_user: Annotated[
        User,
        Depends(get_current_active_user),
    ],
):
    """Process a chat request for a given program.

    Args:
        jason_data: Request body containing `messages`.
        program_name: Program identifier used to scope the vector store.
        current_user: Authenticated user performing the request.

    Returns:
        dict: Assistant message envelope on success.

    Notes:
        Errors during processing are returned as a 500 JSON response.
    """

    try:
        logger.info(
            "Chat request for program=%s by user=%s",
            program_name,
            getattr(current_user, "username", None),
        )
        chat_bot_obj = ChatBot(program_name=program_name)
        response_obj = await chat_bot_obj.chat_without_streaming(jason_data.messages)
        logger.debug("Chat response generated for program=%s", program_name)
        return response_obj
    except Exception as error:
        # NOTE: Convert unexpected errors into a generic 500 response to avoid
        # leaking internal details to clients.
        logger.exception("Error during chat processing for program=%s", program_name)
        error_message = f"Error during chat processing: {str(error)}"
        return JSONResponse(status_code=500, content={"detail": error_message})

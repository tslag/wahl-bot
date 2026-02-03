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
    """
    Description
    -----------
        API route to post a chat request
    Parameters
    ----------
        request_body: dict
    Returns
    --------
        result: JSON object which contains chatbot answer
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
        logger.exception("Error during chat processing for program=%s", program_name)
        error_message = f"Error during chat processing: {str(error)}"
        return JSONResponse(status_code=500, content={"detail": error_message})

"""Schemas for chat requests and responses."""

from typing import List

from fastapi import Query
from pydantic import BaseModel


class Message(BaseModel):
    """A single chat message with content and role (user/assistant)."""

    content: str
    role: str


class ChatRequest(BaseModel):
    """Request body containing chat messages to be processed."""

    messages: List[Message] = Query(
        title="Messages",
        default=[Message(content="Hi, wie kannst du mir helfen?", role="user")],
        description="Message which will be processed",
    )


class ChatResponse(BaseModel):
    """Response envelope containing the assistant message."""

    message: Message = Query(
        title="Message",
        default=Message(content="This is an example response", role="assistant"),
        description="Chat response message",
    )

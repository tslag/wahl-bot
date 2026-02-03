from typing import List

from fastapi import Query
from pydantic import BaseModel


class Message(BaseModel):
    content: str
    role: str


class ChatRequest(BaseModel):
    messages: List[Message] = Query(
        title="Messages",
        default=[Message(content="Hi, wie kannst du mir helfen?", role="user")],
        description="Message which will be processed",
    )


class ChatResponse(BaseModel):
    message: Message = Query(
        title="Message",
        default=Message(content="This is an example response", role="assistant"),
        description="Chat response message",
    )

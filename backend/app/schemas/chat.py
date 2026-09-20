from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(
        description="The message sent by the user to the chatbot."
    )

    thread_id: str | None = Field(
        default=None,
        description=(
            "Identifier of the conversation thread to continue. Omit to "
            "start a new conversation, or pass trip_id instead to resume "
            "an existing trip's conversation without knowing its "
            "thread_id."
        )
    )

    trip_id: str | None = Field(
        default=None,
        description=(
            "Identifier of an existing trip whose conversation to "
            "continue. Alternative to thread_id — typically what a "
            "client has after calling GET /trips/{trip_id}/resume. If "
            "both are given, trip_id takes precedence."
        )
    )

    user_id: str = Field(
        default="anonymous",
        description="Unique identifier for the user sending the message."
    )


class ChatResponse(BaseModel):
    reply: str = Field(
        description="The chatbot's response to the user's message."
    )

    thread_id: str = Field(
        description="Unique identifier of the conversation thread."
    )

    trip_id: str = Field(
        description="Unique identifier of the trip associated with this conversation."
    )

    awaiting_confirmation: bool = Field(
        default=False,
        description="Indicates whether the chatbot is waiting for the user's confirmation."
    )
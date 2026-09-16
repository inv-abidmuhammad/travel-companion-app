from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(
        description="The message sent by the user to the chatbot."
    )

    thread_id: str = Field(
        default="default",
        description="Unique identifier for the conversation thread."
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

    awaiting_confirmation: bool = Field(
        default=False,
        description="Indicates whether the chatbot is waiting for the user's confirmation."
    )
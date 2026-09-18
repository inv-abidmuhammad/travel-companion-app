from pydantic import BaseModel, ConfigDict, Field

from app.enums import TripStatus


class TripCreate(BaseModel):
    user_id: str = Field(
        description="Unique identifier of the user creating the trip."
    )

    thread_id: str | None = Field(
        default=None,
        description="Identifier of the conversation thread associated with the trip."
    )

    origin: str | None = Field(
        default=None,
        description="Starting location of the trip."
    )

    destination: str | None = Field(
        default=None,
        description="Destination of the trip."
    )

    departure_date: str | None = Field(
        default=None,
        description="Planned departure date of the trip, as YYYY-MM-DD."
    )

    budget: float | None = Field(
        default=None,
        description="Maximum or planned budget for the trip."
    )

    duration_days: int | None = Field(
        default=None,
        description="Planned duration of the trip in days."
    )


class TripUpdate(BaseModel):
    origin: str | None = Field(
        default=None,
        description="Updated starting location of the trip."
    )

    destination: str | None = Field(
        default=None,
        description="Updated destination of the trip."
    )

    departure_date: str | None = Field(
        default=None,
        description="Updated planned departure date of the trip, as YYYY-MM-DD."
    )

    budget: float | None = Field(
        default=None,
        description="Updated maximum or planned budget for the trip."
    )

    duration_days: int | None = Field(
        default=None,
        description="Updated duration of the trip in days."
    )

    status: TripStatus | None = Field(
        default=None,
        description="Current status of the trip (draft, planned, completed, cancelled)."
    )

    itinerary_text: str | None = Field(
        default=None,
        description="Updated text containing the trip itinerary."
    )


class TripOut(BaseModel):
    id: str = Field(
        description="Unique identifier of the trip."
    )

    user_id: str = Field(
        description="Unique identifier of the user who owns the trip."
    )

    thread_id: str = Field(
        description="Identifier of the conversation thread associated with the trip."
    )

    origin: str | None = Field(
        default=None,
        description="Starting location of the trip."
    )

    destination: str | None = Field(
        default=None,
        description="Destination of the trip."
    )

    departure_date: str | None = Field(
        default=None,
        description="Planned departure date of the trip, as YYYY-MM-DD."
    )

    budget: float | None = Field(
        default=None,
        description="Maximum or planned budget for the trip."
    )

    duration_days: int | None = Field(
        default=None,
        description="Duration of the trip in days."
    )

    status: TripStatus = Field(
        description="Current status of the trip (draft, planned, completed, cancelled)."
    )

    itinerary_text: str | None = Field(
        default=None,
        description="Text containing the generated or saved trip itinerary."
    )

    model_config = ConfigDict(from_attributes=True)
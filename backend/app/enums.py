"""
Domain enums shared between the database layer and the API schemas.

Defined here (not in schemas/ or db/) so neither layer depends on the
other. Both import from this module.
"""
import enum


class TripStatus(str, enum.Enum):
    DRAFT = "draft"
    PLANNED = "planned"
    CANCELLED = "cancelled"

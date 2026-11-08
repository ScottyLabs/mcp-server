from pydantic import BaseModel


class DiningLocation(BaseModel):
    """Represents a CMU dining location with relevant information for users."""

    concept_id: int
    name: str
    short_description: str
    description: str
    location: str
    accepts_online_orders: bool
    url: str | None = None
    menu_url: str | None = None
    current_status: str = "unknown"  # open, closed, unknown


class TimeSlot(BaseModel):
    """Represents operating hours for a location."""

    day: int  # 0=Sunday, 1=Monday, etc.
    start_hour: int
    start_minute: int
    end_hour: int
    end_minute: int

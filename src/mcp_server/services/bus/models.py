"""Validated models for the bus-sign backend response."""

from pydantic import BaseModel, ConfigDict, RootModel


class Arrival(BaseModel):
    """One bus-sign arrival prediction."""

    model_config = ConfigDict(strict=True)

    bus_id: str
    seconds: int
    capacity: str


class RouteGroup(BaseModel):
    """Arrivals sharing a route and destination at one stop."""

    model_config = ConfigDict(strict=True)

    route: str
    destination: str
    arrivals: list[Arrival]


class PredictionResponse(RootModel[dict[str, list[RouteGroup]]]):
    """The bus-sign mapping from stop IDs to route groups."""

    model_config = ConfigDict(strict=True)

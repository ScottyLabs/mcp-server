"""Validated backend models and typed internal bus data shapes."""

from typing import Literal, NotRequired, TypedDict

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


class KnownStop(TypedDict):
    """Configured metadata for one supported boarding stop."""

    name: str
    direction: Literal["inbound", "outbound"]
    landmarks: list[str]
    typical_destinations: list[str]


class StopMetadata(KnownStop):
    """Public stop metadata including its opaque PRT stop ID."""

    stop_id: str


class DestinationArea(TypedDict):
    """A rider-relevant area within a broader neighborhood."""

    key: str
    name: str
    target_stop_ids: list[str]
    routes: list[str]


class NeighborhoodDestinationRule(TypedDict):
    """Temporary mapping from a campus origin to neighborhood areas."""

    stop_id: str
    areas: list[DestinationArea]
    source: str


class DestinationAreaReference(TypedDict):
    """Destination-area identity without its alternative routes."""

    key: str
    name: str
    target_stop_ids: list[str]


class RouteContext(TypedDict):
    """Where one requested route serves a neighborhood."""

    route: str
    serves_destination_area: DestinationArea | None
    does_not_serve_destination_areas: list[DestinationAreaReference]
    alternatives: list[DestinationArea]


class NeighborhoodResolution(TypedDict):
    """Structured provenance for a resolved neighborhood request."""

    type: Literal["neighborhood"]
    input: str
    neighborhood: str
    stop_id: str
    routes: list[str]
    destination_areas: list[DestinationArea]
    source: str
    route_context: NotRequired[RouteContext]


class LiveDestinationResolution(TypedDict):
    """A place interpreted as a live route destination."""

    type: Literal["live_destination"]
    input: str
    destination: str
    note: str


class RetrievalMetadata(TypedDict):
    """When the MCP received a validated prediction response."""

    utc: str
    local: str
    local_display: str
    timezone: str
    meaning: str


class SerializedArrival(TypedDict):
    """One backend arrival enriched with ceiling-rounded minutes."""

    bus_id: str
    seconds: int
    minutes: int
    capacity: str


class SerializedRouteGroup(TypedDict):
    """One serialized route/destination group."""

    route: str
    destination: str
    arrivals: list[SerializedArrival]


class NextBusMatch(TypedDict):
    """The earliest arrival satisfying a set of filters."""

    route: str
    destination: str
    bus_id: str
    seconds: int
    minutes: int
    capacity: str


class AvailableRoute(TypedDict):
    """A currently predicted route and its displayed destination."""

    route: str
    destination: str


class Availability(TypedDict):
    """Current routes/destinations and the configured boarding stops."""

    stops: list[StopMetadata]
    routes_and_destinations_by_stop: dict[str, list[AvailableRoute]]
    predictions: dict[str, list[SerializedRouteGroup]]


class SearchMatch(NextBusMatch):
    """A literal-search match with its boarding-stop context."""

    stop_id: str
    stop_name: str
    direction: Literal["inbound", "outbound"]


class DestinationAreaResult(TypedDict):
    """One live next-bus result for a neighborhood destination area."""

    status: Literal["ok", "no_match"]
    destination_area: DestinationArea
    stop: StopMetadata
    match: NextBusMatch | None
    message: NotRequired[str]

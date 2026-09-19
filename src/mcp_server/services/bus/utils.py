"""HTTP, validation, and pure transformation helpers for bus predictions."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import math
import re
from zoneinfo import ZoneInfo

import httpx
from pydantic import ValidationError

from mcp_server.services.bus.constants import (
    API_BASE_URL,
    KNOWN_STOPS,
    LOCAL_TIMEZONE,
    PREDICTIONS_PATH,
    REQUEST_TIMEOUT_SECONDS,
)
from mcp_server.services.bus.models import (
    Arrival,
    AvailableRoute,
    KnownStop,
    NextBusMatch,
    PredictionResponse,
    RetrievalMetadata,
    RouteGroup,
    SearchMatch,
    SerializedRouteGroup,
    StopMetadata,
)


class BusBackendError(RuntimeError):
    """Raised when the bus-sign backend cannot provide a valid response."""


@dataclass(frozen=True)
class FetchedPredictions:
    """One validated backend response and its MCP retrieval timestamp."""

    predictions: dict[str, list[RouteGroup]]
    retrieved_at: RetrievalMetadata


def predictions_url() -> str:
    """Return the configured predictions endpoint."""

    return f"{API_BASE_URL}{PREDICTIONS_PATH}"


def retrieval_metadata(instant: datetime | None = None) -> RetrievalMetadata:
    """Build UTC-canonical and Pittsburgh-local retrieval metadata."""

    retrieved = instant or datetime.now(timezone.utc)
    if retrieved.tzinfo is None:
        retrieved = retrieved.replace(tzinfo=timezone.utc)
    retrieved_utc = retrieved.astimezone(timezone.utc)
    retrieved_local = retrieved_utc.astimezone(ZoneInfo(LOCAL_TIMEZONE))
    hour = retrieved_local.strftime("%I").lstrip("0") or "12"
    local_display = (
        f"{retrieved_local.strftime('%b')} {retrieved_local.day}, "
        f"{retrieved_local.year} at {hour}:{retrieved_local.strftime('%M %p %Z')}"
    )
    return {
        "utc": retrieved_utc.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "local": retrieved_local.isoformat(timespec="seconds"),
        "local_display": local_display,
        "timezone": LOCAL_TIMEZONE,
        "meaning": (
            "Time the MCP received and validated the bus-sign response; "
            "not the upstream PRT generation time."
        ),
    }


async def fetch_predictions(
    client: httpx.AsyncClient | None = None,
) -> FetchedPredictions:
    """Fetch and validate the configured bus-sign predictions endpoint."""

    endpoint = predictions_url()
    owns_client = client is None
    http_client = client or httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS)
    try:
        response = await http_client.get(endpoint)
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError as exc:
            raise BusBackendError(
                f"Bus backend {endpoint} returned malformed JSON: {exc}"
            ) from exc
        try:
            validated = PredictionResponse.model_validate(payload)
        except ValidationError as exc:
            raise BusBackendError(
                f"Bus backend {endpoint} returned an invalid prediction response: {exc}"
            ) from exc
        return FetchedPredictions(
            predictions=validated.root,
            retrieved_at=retrieval_metadata(),
        )
    except httpx.HTTPStatusError as exc:
        raise BusBackendError(
            f"Bus backend {endpoint} returned HTTP {exc.response.status_code}."
        ) from exc
    except httpx.RequestError as exc:
        raise BusBackendError(f"Failed to reach bus backend {endpoint}: {exc}") from exc
    finally:
        if owns_client:
            await http_client.aclose()


def stop_metadata(stop_id: str) -> StopMetadata:
    """Return an independent, human-readable known-stop record."""

    return {"stop_id": stop_id, **deepcopy(KNOWN_STOPS[stop_id])}


def known_stops_by_id() -> dict[str, KnownStop]:
    """Return all known-stop metadata keyed by stop ID."""

    return deepcopy(KNOWN_STOPS)


def known_stops_list() -> list[StopMetadata]:
    """Return known-stop metadata as a stable list."""

    return [stop_metadata(stop_id) for stop_id in KNOWN_STOPS]


def minutes_until(seconds: int) -> int:
    """Convert exact seconds to non-negative, ceiling-rounded minutes."""

    return max(0, math.ceil(seconds / 60))


def normalize_route_identifier(route: str) -> str:
    """Normalize harmless route casing, whitespace, and hyphen variations."""

    return re.sub(r"[\s-]+", "", route).upper()


def serialize_route_group(group: RouteGroup) -> SerializedRouteGroup:
    """Serialize a validated group and add human-friendly minutes."""

    return {
        "route": group.route,
        "destination": group.destination,
        "arrivals": [
            {
                "bus_id": arrival.bus_id,
                "seconds": arrival.seconds,
                "minutes": minutes_until(arrival.seconds),
                "capacity": arrival.capacity,
            }
            for arrival in group.arrivals
        ],
    }


def serialize_predictions(
    predictions: dict[str, list[RouteGroup]],
) -> dict[str, list[SerializedRouteGroup]]:
    """Serialize predictions while always including both configured stops."""

    serialized = {
        stop_id: [serialize_route_group(group) for group in groups]
        for stop_id, groups in predictions.items()
    }
    for stop_id in KNOWN_STOPS:
        serialized.setdefault(stop_id, [])
    return serialized


def has_arrivals(predictions: dict[str, list[RouteGroup]]) -> bool:
    """Return whether any predicted bus arrivals are available."""

    return any(
        group.arrivals
        for groups in predictions.values()
        for group in groups
    )


def available_predictions(
    predictions: dict[str, list[RouteGroup]],
) -> dict[str, list[AvailableRoute]]:
    """Summarize currently available routes and destinations by known stop."""

    return {
        stop_id: [
            {"route": group.route, "destination": group.destination}
            for group in predictions.get(stop_id, [])
            if group.arrivals
        ]
        for stop_id in KNOWN_STOPS
    }


def earliest_match(
    groups: list[RouteGroup],
    *,
    route: str | None = None,
    destination: str | None = None,
    allowed_routes: set[str] | None = None,
) -> NextBusMatch | None:
    """Return the earliest arrival matching route/destination constraints."""

    normalized_route = normalize_route_identifier(route) if route else None
    destination_folded = destination.casefold() if destination else None
    normalized_allowed = {
        normalize_route_identifier(item) for item in allowed_routes or set()
    }
    candidates: list[tuple[int, RouteGroup, Arrival]] = []

    for group in groups:
        group_route = normalize_route_identifier(group.route)
        if normalized_route and group_route != normalized_route:
            continue
        if destination_folded and destination_folded not in group.destination.casefold():
            continue
        if normalized_allowed and group_route not in normalized_allowed:
            continue
        for arrival in group.arrivals:
            candidates.append((arrival.seconds, group, arrival))

    if not candidates:
        return None
    _, group, arrival = min(candidates, key=lambda candidate: candidate[0])
    return {
        "route": group.route,
        "destination": group.destination,
        "bus_id": arrival.bus_id,
        "seconds": arrival.seconds,
        "minutes": minutes_until(arrival.seconds),
        "capacity": arrival.capacity,
    }


def literal_search(
    predictions: dict[str, list[RouteGroup]], query: str
) -> list[SearchMatch]:
    """Search stop, route, destination, or exact capacity fields."""

    needle = query.casefold()
    normalized_route_query = normalize_route_identifier(query)
    matches: list[SearchMatch] = []
    for stop_id, groups in predictions.items():
        if stop_id not in KNOWN_STOPS:
            continue
        for group in groups:
            group_matches = (
                needle in stop_id.casefold()
                or needle in group.route.casefold()
                or normalized_route_query == normalize_route_identifier(group.route)
                or needle in group.destination.casefold()
            )
            for arrival in group.arrivals:
                if not group_matches and needle != arrival.capacity.casefold():
                    continue
                matches.append(
                    {
                        "stop_id": stop_id,
                        "stop_name": KNOWN_STOPS[stop_id]["name"],
                        "direction": KNOWN_STOPS[stop_id]["direction"],
                        "route": group.route,
                        "destination": group.destination,
                        "bus_id": arrival.bus_id,
                        "seconds": arrival.seconds,
                        "minutes": minutes_until(arrival.seconds),
                        "capacity": arrival.capacity,
                    }
                )
    return sorted(matches, key=lambda match: match["seconds"])

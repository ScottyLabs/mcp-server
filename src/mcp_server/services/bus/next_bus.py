"""Next-bus query normalization, resolution, and response construction."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from mcp_server.services.bus.constants import (
    COVERAGE_NOTE,
    KNOWN_STOPS,
    NEIGHBORHOOD_DESTINATION_AREAS,
)
from mcp_server.services.bus.destination_areas import (
    build_destination_area_results,
    build_neighborhood_resolution,
    destination_area_for_route,
    neighborhood_routes,
    serialize_destination_area,
)
from mcp_server.services.bus.models import (
    Availability,
    LiveDestinationResolution,
    NeighborhoodDestinationRule,
    NeighborhoodResolution,
)
from mcp_server.services.bus.utils import (
    FetchedPredictions,
    available_predictions,
    earliest_match,
    has_arrivals,
    known_stops_list,
    normalize_route_identifier,
    serialize_predictions,
    stop_metadata,
)


@dataclass(frozen=True)
class NextBusQuery:
    """Normalized filters supplied to the next-bus use case."""

    stop_id: str | None
    route: str | None
    place: str | None
    direction: str | None

    def filters(self) -> dict[str, str | None]:
        """Return the normalized filters for the public response."""

        return {
            "stop_id": self.stop_id,
            "route": self.route,
            "place": self.place,
            "direction": self.direction,
        }


@dataclass(frozen=True)
class ResolvedPlace:
    """Destination/neighborhood interpretation used for prediction matching."""

    rule: NeighborhoodDestinationRule | None
    effective_destination: str | None
    resolution: NeighborhoodResolution | LiveDestinationResolution | None

    @property
    def resolved_stop_id(self) -> str | None:
        """Return the boarding stop selected by a neighborhood rule."""

        return self.rule["stop_id"] if self.rule else None


@dataclass(frozen=True)
class QueryError:
    """An input error that app.py can wrap in the shared MCP envelope."""

    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


def normalize_next_bus_query(
    *,
    stop_id: str | None,
    route: str | None,
    place: str | None,
    direction: str | None,
) -> NextBusQuery:
    """Normalize harmless formatting differences in next-bus filters."""

    return NextBusQuery(
        stop_id=stop_id.strip() if stop_id is not None else None,
        route=normalize_route_identifier(route) if route is not None else None,
        place=place.strip() if place and place.strip() else None,
        direction=direction.strip().casefold() if direction is not None else None,
    )


def validate_next_bus_query(query: NextBusQuery) -> QueryError | None:
    """Validate filters that do not depend on place resolution."""

    if query.stop_id is not None and query.stop_id not in KNOWN_STOPS:
        return QueryError(
            code="unknown_stop",
            message=f"Stop {query.stop_id or 'empty value'} is not configured.",
            details={"known_stops": known_stops_list()},
        )
    if query.route is not None and not any(
        character.isalnum() for character in query.route
    ):
        return QueryError(
            code="invalid_route",
            message="Route must contain at least one letter or number.",
        )
    if query.direction not in {None, "inbound", "outbound"}:
        return QueryError(
            code="invalid_direction",
            message="Direction must be either inbound or outbound.",
            details={"allowed_directions": ["inbound", "outbound"]},
        )
    return None


def resolve_place(query: NextBusQuery) -> ResolvedPlace:
    """Resolve one place as a configured neighborhood or live destination."""

    rule = None
    effective_destination = None
    resolution: NeighborhoodResolution | LiveDestinationResolution | None = None

    if query.place:
        normalized_place = query.place.casefold()
        rule = NEIGHBORHOOD_DESTINATION_AREAS.get(normalized_place)
        if rule:
            resolution = build_neighborhood_resolution(
                rule,
                neighborhood=normalized_place,
                input_value=query.place,
                route=query.route,
            )
        else:
            effective_destination = query.place
            resolution = {
                "type": "live_destination",
                "input": query.place,
                "destination": query.place,
                "note": (
                    "Searched against live route destinations."
                ),
            }

    return ResolvedPlace(
        rule=rule,
        effective_destination=effective_destination,
        resolution=resolution,
    )


def validate_resolved_place(
    query: NextBusQuery,
    resolved: ResolvedPlace,
) -> QueryError | None:
    """Validate stop and direction filters after place resolution."""

    if (
        query.stop_id
        and resolved.resolved_stop_id
        and query.stop_id != resolved.resolved_stop_id
    ):
        return QueryError(
            code="conflicting_filters",
            message=(
                f"Place {query.place!r} resolves to stop {resolved.resolved_stop_id}, "
                f"not {query.stop_id}."
            ),
            details={"known_stops": known_stops_list()},
        )

    effective_stop = query.stop_id or resolved.resolved_stop_id
    if effective_stop and query.direction:
        stop_direction = KNOWN_STOPS[effective_stop]["direction"]
        if query.direction != stop_direction:
            return QueryError(
                code="conflicting_filters",
                message=(
                    f"Stop {effective_stop} is {stop_direction}, "
                    f"not {query.direction}."
                ),
                details={"known_stops": known_stops_list()},
            )
    return None


def _availability(fetched: FetchedPredictions) -> Availability:
    """Return all current predictions and compact availability metadata."""

    return {
        "stops": known_stops_list(),
        "routes_and_destinations_by_stop": available_predictions(
            fetched.predictions
        ),
        "predictions": serialize_predictions(fetched.predictions),
    }


def _relevant_stops(
    query: NextBusQuery,
    resolved: ResolvedPlace,
) -> list[str]:
    """Select the configured boarding stops relevant to the query."""

    effective_stop = query.stop_id or resolved.resolved_stop_id
    if effective_stop:
        return [effective_stop]
    if query.direction:
        return [
            stop_id
            for stop_id, metadata in KNOWN_STOPS.items()
            if metadata["direction"] == query.direction
        ]
    return list(KNOWN_STOPS)


def _build_results(
    query: NextBusQuery,
    resolved: ResolvedPlace,
    fetched: FetchedPredictions,
) -> list[dict[str, Any]]:
    """Build directional or per-destination-area next-bus results."""

    if resolved.rule and query.route is None:
        return [
            dict(entry)
            for entry in build_destination_area_results(
                resolved.rule,
                fetched.predictions.get(resolved.rule["stop_id"], []),
            )
        ]

    allowed_routes = neighborhood_routes(resolved.rule) if resolved.rule else None
    selected_area = (
        destination_area_for_route(resolved.rule, query.route)
        if resolved.rule and query.route
        else None
    )
    results: list[dict[str, Any]] = []
    for stop_id in _relevant_stops(query, resolved):
        match = earliest_match(
            fetched.predictions.get(stop_id, []),
            route=query.route,
            destination=resolved.effective_destination,
            allowed_routes=allowed_routes,
        )
        entry: dict[str, Any] = {
            "status": "ok" if match else "no_match",
            "stop": stop_metadata(stop_id),
            "match": match,
        }
        if selected_area:
            entry["destination_area"] = serialize_destination_area(selected_area)
        if match is None:
            requested = query.route or resolved.effective_destination or "bus"
            entry["message"] = (
                f"No current {requested} prediction is available in this direction."
            )
        results.append(entry)

    effective_stop = query.stop_id or resolved.resolved_stop_id
    explicit_direction = bool(effective_stop or query.direction)
    if resolved.effective_destination and not explicit_direction:
        matches_only = [entry for entry in results if entry["match"]]
        if matches_only:
            return matches_only
    return results


def _selection(
    query: NextBusQuery,
    resolved: ResolvedPlace,
    results: list[dict[str, Any]],
) -> Literal["per_destination_area", "per_direction", "single_direction", "none"]:
    """Describe how the result list was partitioned."""

    if resolved.rule and query.route is None:
        return "per_destination_area"
    if len(results) > 1:
        return "per_direction"
    if results:
        return "single_direction"
    return "none"


def build_next_bus_response(
    query: NextBusQuery,
    resolved: ResolvedPlace,
    fetched: FetchedPredictions,
) -> dict[str, Any]:
    """Build the complete MCP response for a validated next-bus query."""

    results = _build_results(query, resolved, fetched)
    matching_count = sum(1 for entry in results if entry["match"])
    if matching_count:
        status = "ok"
    elif not has_arrivals(fetched.predictions):
        status = "empty"
    else:
        status = "no_match"

    result: dict[str, Any] = {
        "status": status,
        "selection": _selection(query, resolved, results),
        "filters": query.filters(),
        "resolution": resolved.resolution,
        "results": results,
        "retrieved_at": fetched.retrieved_at,
        "coverage_note": COVERAGE_NOTE,
    }
    if status in {"empty", "no_match"}:
        if status == "no_match":
            if (
                resolved.resolution
                and resolved.resolution["type"] == "live_destination"
            ):
                result["message"] = (
                    "No live destination matched the supplied place. "
                    "All current predictions are included under "
                    "available.predictions as alternatives."
                )
            else:
                result["message"] = (
                    "No bus predictions currently match the supplied filters."
                )
        else:
            result["message"] = (
                "No bus predictions are currently available for the configured stops."
            )
        result["available"] = _availability(fetched)
    return result

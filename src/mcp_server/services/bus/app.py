"""FastMCP tools for live bus predictions and CMU PRT rider guidance."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from mcp_server.services.bus.constants import (
    CMU_PRT_RIDER_GUIDE,
    CMU_PRT_SOURCE_URL,
    COVERAGE_NOTE,
    KNOWN_STOPS,
    NEIGHBORHOOD_ROUTES,
)
from mcp_server.services.bus.utils import (
    available_predictions,
    earliest_match,
    fetch_predictions,
    has_arrivals,
    known_stops_by_id,
    known_stops_list,
    literal_search,
    normalize_route_identifier,
    serialize_predictions,
    serialize_route_group,
    stop_metadata,
)


mcp = FastMCP("CMU Bus Sign", version="0.1.0")


def _input_error(code: str, message: str, **details: Any) -> dict[str, Any]:
    error = {"code": code, "message": message, **details}
    return {"status": "input_error", "error": error, "coverage_note": COVERAGE_NOTE}


def _availability(predictions: dict) -> dict[str, Any]:
    return {
        "stops": known_stops_list(),
        "routes_and_destinations_by_stop": available_predictions(predictions),
    }


@mcp.tool()
async def get_bus_predictions() -> dict[str, Any]:
    """Get live predictions for both configured Forbes/Morewood bus stops.

    Stop 4407 is inbound toward Downtown/Oakland near Tepper Quad. Stop 7117
    is outbound near CUC. ``seconds`` is time until the bus reaches the listed
    boarding stop; results may reflect caching in the bus-sign backend.
    """

    fetched = await fetch_predictions()
    status = "ok" if has_arrivals(fetched.predictions) else "empty"
    result: dict[str, Any] = {
        "status": status,
        "predictions": serialize_predictions(fetched.predictions),
        "stops": known_stops_by_id(),
        "retrieved_at": fetched.retrieved_at,
        "coverage_note": COVERAGE_NOTE,
    }
    if status == "empty":
        result["message"] = (
            "No bus predictions are currently available for the configured stops."
        )
    return result


@mcp.tool()
async def get_stop_predictions(stop_id: str) -> dict[str, Any]:
    """Get predictions for one configured stop ID.

    Use 4407 for the inbound/Downtown side near Tepper Quad. Use 7117 for the
    outbound side near CUC. ``seconds`` is time until arrival at that stop.
    """

    normalized_stop = stop_id.strip()
    if normalized_stop not in KNOWN_STOPS:
        return _input_error(
            "unknown_stop",
            f"Stop {normalized_stop or repr(stop_id)} is not configured.",
            known_stops=known_stops_list(),
        )

    fetched = await fetch_predictions()
    groups = fetched.predictions.get(normalized_stop, [])
    status = "ok" if any(group.arrivals for group in groups) else "empty"
    result: dict[str, Any] = {
        "status": status,
        "stop": stop_metadata(normalized_stop),
        "predictions": [serialize_route_group(group) for group in groups],
        "retrieved_at": fetched.retrieved_at,
        "coverage_note": COVERAGE_NOTE,
    }
    if status == "empty":
        result["message"] = (
            f"No bus predictions are currently available for stop {normalized_stop}."
        )
    return result


@mcp.tool()
async def get_next_bus(
    stop_id: str | None = None,
    route: str | None = None,
    destination: str | None = None,
    neighborhood: str | None = None,
    direction: str | None = None,
) -> dict[str, Any]:
    """Get the earliest matching bus for each relevant direction.

    Stop 4407 is inbound/Downtown near Tepper; 7117 is outbound near CUC.
    A route-only or unfiltered request returns separate inbound and outbound
    results. ``destination`` is a case-insensitive substring. ``neighborhood``
    is a curated waypoint lookup currently limited to Squirrel Hill, which
    resolves to outbound stop 7117 and routes 61A/61B/61C/61D. Arrival seconds
    and minutes are countdowns to the named boarding stop, not ride time to the
    destination or neighborhood.
    """

    normalized_stop = stop_id.strip() if stop_id is not None else None
    normalized_route = normalize_route_identifier(route) if route is not None else None
    normalized_destination = (
        destination.strip() if destination and destination.strip() else None
    )
    normalized_neighborhood = (
        neighborhood.strip().casefold()
        if neighborhood and neighborhood.strip()
        else None
    )
    normalized_direction = (
        direction.strip().casefold() if direction is not None else None
    )

    filters = {
        "stop_id": normalized_stop,
        "route": normalized_route,
        "destination": normalized_destination,
        "neighborhood": normalized_neighborhood,
        "direction": normalized_direction,
    }

    if normalized_stop is not None and normalized_stop not in KNOWN_STOPS:
        return _input_error(
            "unknown_stop",
            f"Stop {normalized_stop or repr(stop_id)} is not configured.",
            known_stops=known_stops_list(),
        )
    if normalized_route is not None and not any(
        character.isalnum() for character in normalized_route
    ):
        return _input_error(
            "invalid_route",
            "Route must contain at least one letter or number.",
        )
    if normalized_direction not in {None, "inbound", "outbound"}:
        return _input_error(
            "invalid_direction",
            "Direction must be either inbound or outbound.",
            allowed_directions=["inbound", "outbound"],
        )

    neighborhood_rule = (
        NEIGHBORHOOD_ROUTES.get(normalized_neighborhood)
        if normalized_neighborhood
        else None
    )
    resolved_stop = neighborhood_rule["stop_id"] if neighborhood_rule else None
    if normalized_stop and resolved_stop and normalized_stop != resolved_stop:
        return _input_error(
            "conflicting_filters",
            f"Neighborhood {neighborhood!r} resolves to stop {resolved_stop}, not {normalized_stop}.",
            known_stops=known_stops_list(),
        )

    effective_stop = normalized_stop or resolved_stop
    if effective_stop and normalized_direction:
        stop_direction = KNOWN_STOPS[effective_stop]["direction"]
        if normalized_direction != stop_direction:
            return _input_error(
                "conflicting_filters",
                f"Stop {effective_stop} is {stop_direction}, not {normalized_direction}.",
                known_stops=known_stops_list(),
            )

    fetched = await fetch_predictions()
    if normalized_neighborhood and neighborhood_rule is None:
        return {
            "status": "no_match",
            "selection": "none",
            "filters": filters,
            "resolution": None,
            "results": [],
            "message": (
                "That neighborhood is not in the curated bus waypoint directory; "
                "no route was inferred."
            ),
            "available": _availability(fetched.predictions),
            "retrieved_at": fetched.retrieved_at,
            "coverage_note": COVERAGE_NOTE,
        }

    explicit_direction = bool(
        effective_stop is not None or normalized_direction is not None
    )
    if effective_stop:
        relevant_stops = [effective_stop]
    elif normalized_direction:
        relevant_stops = [
            candidate
            for candidate, metadata in KNOWN_STOPS.items()
            if metadata["direction"] == normalized_direction
        ]
    else:
        relevant_stops = list(KNOWN_STOPS)

    allowed_routes = (
        set(neighborhood_rule["routes"]) if neighborhood_rule else None
    )
    resolution = None
    if neighborhood_rule:
        resolution = {
            "neighborhood": normalized_neighborhood,
            "stop_id": neighborhood_rule["stop_id"],
            "routes": list(neighborhood_rule["routes"]),
            "note": neighborhood_rule["note"],
        }

    directional_results = []
    for candidate_stop in relevant_stops:
        match = earliest_match(
            fetched.predictions.get(candidate_stop, []),
            route=normalized_route,
            destination=normalized_destination,
            allowed_routes=allowed_routes,
        )
        entry: dict[str, Any] = {
            "status": "ok" if match else "no_match",
            "stop": stop_metadata(candidate_stop),
            "match": match,
        }
        if match is None:
            requested = normalized_route or normalized_destination or "bus"
            entry["message"] = (
                f"No current {requested} prediction is available in this direction."
            )
        directional_results.append(entry)

    # A destination can resolve direction from live data. Route-only and
    # unfiltered requests intentionally retain both directions, including an
    # explicit no-match entry for either side.
    if normalized_destination and not explicit_direction:
        matches_only = [entry for entry in directional_results if entry["match"]]
        if matches_only:
            directional_results = matches_only

    matching_count = sum(1 for entry in directional_results if entry["match"])
    if matching_count:
        status = "ok"
    elif not has_arrivals(fetched.predictions):
        status = "empty"
    else:
        status = "no_match"

    if len(directional_results) > 1:
        selection = "per_direction"
    elif directional_results:
        selection = "single_direction"
    else:
        selection = "none"

    result: dict[str, Any] = {
        "status": status,
        "selection": selection,
        "filters": filters,
        "resolution": resolution,
        "results": directional_results,
        "retrieved_at": fetched.retrieved_at,
        "coverage_note": COVERAGE_NOTE,
    }
    if status in {"empty", "no_match"}:
        result["message"] = (
            "No bus predictions currently match the supplied filters."
            if status == "no_match"
            else "No bus predictions are currently available for the configured stops."
        )
        result["available"] = _availability(fetched.predictions)
    return result


@mcp.tool()
async def search_bus_predictions(query: str) -> dict[str, Any]:
    """Literally search current stop IDs, routes, destinations, or capacity.

    This case-insensitive search does not resolve arbitrary places or
    neighborhoods. Arrival time is the countdown to the listed boarding stop.
    """

    normalized_query = query.strip()
    if not normalized_query:
        return _input_error(
            "empty_query",
            "Search query must contain at least one non-whitespace character.",
        )

    fetched = await fetch_predictions()
    matches = literal_search(fetched.predictions, normalized_query)
    if matches:
        status = "ok"
    elif not has_arrivals(fetched.predictions):
        status = "empty"
    else:
        status = "no_match"
    result: dict[str, Any] = {
        "status": status,
        "query": normalized_query,
        "matches": matches,
        "retrieved_at": fetched.retrieved_at,
        "coverage_note": COVERAGE_NOTE,
    }
    if status == "empty":
        result["message"] = (
            "No bus predictions are currently available for the configured stops."
        )
    elif status == "no_match":
        result["message"] = (
            f"No current bus prediction literally matches {normalized_query!r}."
        )
    return result


@mcp.tool()
async def get_cmu_prt_rider_guide() -> dict[str, Any]:
    """Explain how eligible CMU students use the PRT Ready2Ride benefit."""

    return {
        "status": "ok",
        **CMU_PRT_RIDER_GUIDE,
        "source_url": CMU_PRT_SOURCE_URL,
    }


if __name__ == "__main__":
    mcp.run()

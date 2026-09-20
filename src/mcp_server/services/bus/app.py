"""FastMCP tools for live bus predictions and CMU PRT rider guidance."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from mcp_server.services.bus.constants import (
    CMU_PRT_RIDER_GUIDE,
    CMU_PRT_SOURCE_URL,
    COVERAGE_NOTE,
    KNOWN_STOPS,
)
from mcp_server.services.bus.next_bus import (
    build_next_bus_response,
    normalize_next_bus_query,
    resolve_place,
    validate_next_bus_query,
    validate_resolved_place,
)
from mcp_server.services.bus.utils import (
    fetch_predictions,
    has_arrivals,
    known_stops_by_id,
    known_stops_list,
    literal_search,
    serialize_predictions,
    serialize_route_group,
    stop_metadata,
)


mcp = FastMCP("CMU Bus Sign", version="0.1.0")


def _input_error(code: str, message: str, **details: Any) -> dict[str, Any]:
    error = {"code": code, "message": message, **details}
    return {"status": "input_error", "error": error, "coverage_note": COVERAGE_NOTE}


@mcp.tool()
async def get_bus_predictions() -> dict[str, Any]:
    """Get live predictions for both configured Forbes/Morewood bus stops.

    Stop 4407 is inbound toward Downtown/Oakland near Tepper Quad. Stop 7117
    is outbound near CUC. ``seconds`` is time until the bus reaches the listed
    boarding stop.
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
    place: str | None = None,
    direction: str | None = None,
) -> dict[str, Any]:
    """Get the earliest matching bus for each relevant direction.

    Stop 4407 is inbound/Downtown near Tepper; 7117 is outbound near CUC.
    A route-only or unfiltered request returns separate inbound and outbound
    results. ``place`` accepts either a configured neighborhood/waypoint or a
    case-insensitive live route destination. Squirrel Hill results distinguish
    Forbes & Murray (61A/61B/61C/61D) from Wilkins & Murray (67/69). Arrival
    seconds and minutes are countdowns to the named boarding stop, not ride time
    to the destination area. A no-match response includes all current
    predictions under ``available.predictions`` so the client can offer live
    alternatives without making another tool call.
    """

    query = normalize_next_bus_query(
        stop_id=stop_id,
        route=route,
        place=place,
        direction=direction,
    )
    if error := validate_next_bus_query(query):
        return _input_error(error.code, error.message, **error.details)

    resolved = resolve_place(query)
    if error := validate_resolved_place(query, resolved):
        return _input_error(error.code, error.message, **error.details)

    fetched = await fetch_predictions()
    return build_next_bus_response(query, resolved, fetched)


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

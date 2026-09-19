"""Pure helpers for resolving neighborhood destination areas."""

from __future__ import annotations

from mcp_server.services.bus.models import (
    DestinationArea,
    DestinationAreaResult,
    NeighborhoodDestinationRule,
    NeighborhoodResolution,
    RouteContext,
    RouteGroup,
)
from mcp_server.services.bus.utils import (
    earliest_match,
    normalize_route_identifier,
    stop_metadata,
)


def serialize_destination_area(area: DestinationArea) -> DestinationArea:
    """Return stable public metadata for one destination area."""

    return {
        "key": area["key"],
        "name": area["name"],
        "target_stop_ids": list(area["target_stop_ids"]),
        "routes": list(area["routes"]),
    }


def neighborhood_routes(rule: NeighborhoodDestinationRule) -> set[str]:
    """Return every normalized route included in a neighborhood rule."""

    return {
        normalize_route_identifier(route)
        for area in rule["areas"]
        for route in area["routes"]
    }


def destination_area_for_route(
    rule: NeighborhoodDestinationRule,
    route: str,
) -> DestinationArea | None:
    """Find the destination area served by a normalized route."""

    normalized_route = normalize_route_identifier(route)
    return next(
        (
            area
            for area in rule["areas"]
            if normalized_route
            in {
                normalize_route_identifier(candidate)
                for candidate in area["routes"]
            }
        ),
        None,
    )


def build_route_context(
    rule: NeighborhoodDestinationRule,
    route: str,
) -> RouteContext:
    """Describe where a route serves the neighborhood and its alternatives."""

    normalized_route = normalize_route_identifier(route)
    selected_area = destination_area_for_route(rule, normalized_route)
    other_areas = [area for area in rule["areas"] if area is not selected_area]
    return {
        "route": normalized_route,
        "serves_destination_area": (
            serialize_destination_area(selected_area) if selected_area else None
        ),
        "does_not_serve_destination_areas": [
            {
                "key": area["key"],
                "name": area["name"],
                "target_stop_ids": list(area["target_stop_ids"]),
            }
            for area in other_areas
        ],
        "alternatives": [
            serialize_destination_area(area) for area in other_areas
        ],
    }


def build_neighborhood_resolution(
    rule: NeighborhoodDestinationRule,
    *,
    neighborhood: str,
    input_value: str,
    route: str | None,
) -> NeighborhoodResolution:
    """Build public metadata explaining a neighborhood resolution."""

    resolution: NeighborhoodResolution = {
        "type": "neighborhood",
        "input": input_value,
        "neighborhood": neighborhood,
        "stop_id": rule["stop_id"],
        "routes": sorted(neighborhood_routes(rule)),
        "destination_areas": [
            serialize_destination_area(area) for area in rule["areas"]
        ],
        "source": rule["source"],
    }
    if route:
        resolution["route_context"] = build_route_context(rule, route)
    return resolution


def build_destination_area_results(
    rule: NeighborhoodDestinationRule,
    groups: list[RouteGroup],
) -> list[DestinationAreaResult]:
    """Return one next-bus result for each distinct destination area."""

    results = []
    for area in rule["areas"]:
        match = earliest_match(
            groups,
            allowed_routes={
                normalize_route_identifier(route) for route in area["routes"]
            },
        )
        entry: DestinationAreaResult = {
            "status": "ok" if match else "no_match",
            "destination_area": serialize_destination_area(area),
            "stop": stop_metadata(rule["stop_id"]),
            "match": match,
        }
        if match is None:
            entry["message"] = (
                "No current prediction is available for routes serving "
                f"{area['name']}."
            )
        results.append(entry)
    return results

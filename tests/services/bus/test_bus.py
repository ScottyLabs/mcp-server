"""Focused tests for the bus prediction service."""

import asyncio
from collections.abc import Callable
from unittest.mock import AsyncMock

import httpx
import pytest

from mcp_server.services.bus import app as bus_app
from mcp_server.services.bus.models import Arrival, RouteGroup
from mcp_server.services.bus.utils import (
    BusBackendError,
    FetchedPredictions,
    fetch_predictions,
    serialize_route_group,
)


async def fetch_with_transport(
    handler: Callable[[httpx.Request], httpx.Response],
) -> FetchedPredictions:
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        return await fetch_predictions(client)


@pytest.fixture
def fetched_predictions() -> FetchedPredictions:
    return FetchedPredictions(
        predictions={
            "4407": [
                RouteGroup(
                    route="61D",
                    destination="DOWNTOWN",
                    arrivals=[
                        Arrival(bus_id="inbound", seconds=59, capacity="EMPTY")
                    ],
                )
            ],
            "7117": [
                RouteGroup(
                    route="61D",
                    destination="WATERFRONT",
                    arrivals=[
                        Arrival(bus_id="waterfront", seconds=121, capacity="EMPTY")
                    ],
                ),
                RouteGroup(
                    route="61C",
                    destination="MCKEESPORT",
                    arrivals=[
                        Arrival(bus_id="squirrel-hill", seconds=60, capacity="EMPTY")
                    ],
                ),
                RouteGroup(
                    route="67",
                    destination="FORBES HOSPITAL",
                    arrivals=[
                        Arrival(bus_id="route-67", seconds=30, capacity="EMPTY")
                    ],
                ),
            ],
        },
        retrieved_at={
            "utc": "2026-01-15T12:00:00Z",
            "local": "2026-01-15T07:00:00-05:00",
            "local_display": "Jan 15, 2026 at 7:00 AM EST",
            "timezone": "America/New_York",
            "meaning": "Test retrieval time.",
        },
    )


def test_fetch_predictions_validates_and_enriches_response() -> None:
    """Validate a successful backend payload and its derived response metadata."""

    payload = {
        "7117": [
            {
                "route": "61D",
                "destination": "WATERFRONT",
                "arrivals": [
                    {"bus_id": "3507", "seconds": 121, "capacity": "EMPTY"}
                ],
            }
        ]
    }
    fetched = asyncio.run(
        fetch_with_transport(
            lambda request: httpx.Response(200, json=payload, request=request)
        )
    )

    group = fetched.predictions["7117"][0]
    assert serialize_route_group(group)["arrivals"][0]["minutes"] == 3
    assert group.arrivals[0].seconds == 121
    assert fetched.retrieved_at["timezone"] == "America/New_York"
    assert fetched.retrieved_at["utc"].endswith("Z")


def test_route_normalization_returns_both_directions(
    monkeypatch: pytest.MonkeyPatch,
    fetched_predictions: FetchedPredictions,
) -> None:
    """Normalize a formatted route ID and select its next bus in each direction."""

    monkeypatch.setattr(
        bus_app, "fetch_predictions", AsyncMock(return_value=fetched_predictions)
    )

    result = asyncio.run(bus_app.get_next_bus.fn(route="61 d"))

    assert result["status"] == "ok"
    assert result["selection"] == "per_direction"
    assert [entry["match"]["route"] for entry in result["results"]] == [
        "61D",
        "61D",
    ]
    assert [entry["match"]["minutes"] for entry in result["results"]] == [1, 3]
    assert result["retrieved_at"] == fetched_predictions.retrieved_at
    assert "stop 4407" in result["coverage_note"]
    assert "Routes are taken dynamically" in result["coverage_note"]


@pytest.mark.parametrize(
    ("arguments", "expected_stop", "expected_route", "resolution_type"),
    [
        ({"place": "downtown"}, "4407", "61D", "live_destination"),
        ({"place": "WATERFRONT"}, "7117", "61D", "live_destination"),
    ],
)
def test_live_destination_place_resolution(
    monkeypatch: pytest.MonkeyPatch,
    fetched_predictions: FetchedPredictions,
    arguments: dict[str, str],
    expected_stop: str,
    expected_route: str,
    resolution_type: str,
) -> None:
    """Resolve a place against live destinations."""

    monkeypatch.setattr(
        bus_app, "fetch_predictions", AsyncMock(return_value=fetched_predictions)
    )

    result = asyncio.run(bus_app.get_next_bus.fn(**arguments))

    assert result["status"] == "ok"
    assert result["selection"] == "single_direction"
    assert result["results"][0]["stop"]["stop_id"] == expected_stop
    assert result["results"][0]["match"]["route"] == expected_route
    assert result["resolution"]["type"] == resolution_type


def test_neighborhood_results_are_grouped_by_destination_area(
    monkeypatch: pytest.MonkeyPatch,
    fetched_predictions: FetchedPredictions,
) -> None:
    """Resolve a place as a neighborhood with distinct destination areas."""

    monkeypatch.setattr(
        bus_app, "fetch_predictions", AsyncMock(return_value=fetched_predictions)
    )

    result = asyncio.run(bus_app.get_next_bus.fn(place="SQUIRREL HILL"))

    assert result["status"] == "ok"
    assert result["selection"] == "per_destination_area"
    assert result["resolution"]["type"] == "neighborhood"
    assert [
        (entry["destination_area"]["name"], entry["match"]["route"])
        for entry in result["results"]
    ] == [
        ("Forbes Ave & Murray Ave", "61C"),
        ("Wilkins Ave & Murray Ave", "67"),
    ]
    assert all(
        entry["stop"]["name"] == "Forbes Ave & Morewood Ave (near CUC)"
        for entry in result["results"]
    )


def test_invalid_and_no_match_results(
    monkeypatch: pytest.MonkeyPatch,
    fetched_predictions: FetchedPredictions,
) -> None:
    """Return structured results for invalid filters and valid unmatched queries."""

    fetch = AsyncMock(return_value=fetched_predictions)
    monkeypatch.setattr(bus_app, "fetch_predictions", fetch)

    unknown_stop = asyncio.run(bus_app.get_next_bus.fn(stop_id="9999"))
    conflict = asyncio.run(
        bus_app.get_next_bus.fn(stop_id="4407", direction="outbound")
    )
    assert unknown_stop["status"] == conflict["status"] == "input_error"
    assert fetch.await_count == 0

    unknown_place = asyncio.run(bus_app.get_next_bus.fn(place="greenfield"))
    no_route = asyncio.run(bus_app.get_next_bus.fn(route="999"))
    assert unknown_place["status"] == no_route["status"] == "no_match"
    assert unknown_place["resolution"]["type"] == "live_destination"
    assert len(unknown_place["results"]) == 2
    assert "available.predictions" in unknown_place["message"]
    fallback_predictions = unknown_place["available"]["predictions"]
    assert fallback_predictions["4407"][0]["route"] == "61D"
    assert {group["route"] for group in fallback_predictions["7117"]} == {
        "61C",
        "61D",
        "67",
    }
    assert len(no_route["results"]) == 2
    assert all(entry["match"] is None for entry in no_route["results"])


def test_route_and_neighborhood_match_uses_verified_baseline(
    monkeypatch: pytest.MonkeyPatch,
    fetched_predictions: FetchedPredictions,
) -> None:
    """Allow a live route verified to reach the requested neighborhood."""

    monkeypatch.setattr(
        bus_app, "fetch_predictions", AsyncMock(return_value=fetched_predictions)
    )

    result = asyncio.run(
        bus_app.get_next_bus.fn(route="67", place="squirrel hill")
    )

    assert result["status"] == "ok"
    assert result["selection"] == "single_direction"
    assert result["results"][0]["match"]["route"] == "67"
    assert result["results"][0]["match"]["minutes"] == 1
    assert result["results"][0]["stop"]["name"].endswith("(near CUC)")
    assert result["results"][0]["destination_area"]["name"] == (
        "Wilkins Ave & Murray Ave"
    )
    context = result["resolution"]["route_context"]
    assert context["serves_destination_area"]["name"] == "Wilkins Ave & Murray Ave"
    assert context["does_not_serve_destination_areas"][0]["name"] == (
        "Forbes Ave & Murray Ave"
    )
    assert context["alternatives"][0]["routes"] == ["61A", "61B", "61C", "61D"]


@pytest.mark.parametrize("failure", ["http", "json", "schema", "network"])
def test_backend_errors(failure: str) -> None:
    """Translate backend HTTP, JSON, schema, and network failures consistently."""

    def handler(request: httpx.Request) -> httpx.Response:
        if failure == "http":
            return httpx.Response(500, request=request)
        if failure == "json":
            return httpx.Response(200, content=b"not-json", request=request)
        if failure == "schema":
            return httpx.Response(
                200,
                json={
                    "7117": [
                        {
                            "route": "61D",
                            "destination": "WATERFRONT",
                            "arrivals": [{"bus_id": "3507", "seconds": "soon"}],
                        }
                    ]
                },
                request=request,
            )
        raise httpx.ConnectError("unreachable", request=request)

    # To pass, production fetcher must translate each simulated failure into BusBackendError.
    with pytest.raises(BusBackendError):
        asyncio.run(fetch_with_transport(handler))


def test_tools_are_registered_and_rider_guide_is_sourced() -> None:
    """Register the public bus tools and preserve the rider guide's official source."""

    tools = asyncio.run(bus_app.mcp.get_tools())

    assert set(tools) == {
        "get_bus_predictions",
        "get_cmu_prt_rider_guide",
        "get_next_bus",
        "get_stop_predictions",
        "search_bus_predictions",
    }
    guide = asyncio.run(tools["get_cmu_prt_rider_guide"].fn())
    assert guide["source_url"] == "https://www.cmu.edu/transportation/transport/prt.html"

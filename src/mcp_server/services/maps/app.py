import aiohttp
from fastmcp import FastMCP

BASE_URL = "https://rust.api.maps.scottylabs.org"
TIMEOUT = aiohttp.ClientTimeout(total=10)  # 10 second timeout

app = FastMCP("rust-maps-proxy")


# --- Internal HTTP functions ---

async def _search_buildings_http(query: str) -> list[dict]:
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        async with session.get(f"{BASE_URL}/search", params={"query": query}, ssl=False) as resp:
            resp.raise_for_status()
            data = await resp.json()
            # Normalize to always return a list
            if isinstance(data, dict):
                return data.get("results", []) or []
            elif isinstance(data, list):
                return data
            else:
                return []


async def _get_path_http(start_id: str, end_id: str) -> dict:
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        async with session.get(
            f"{BASE_URL}/path",
            params={"start": start_id, "end": end_id},
            ssl=False
        ) as resp:
            resp.raise_for_status()
            return await resp.json()


# --- Tools ---

@app.tool()
async def search_buildings(query: str) -> dict:
    """Search buildings/floorplans by query string (e.g., 'morewood')."""
    results = await _search_buildings_http(query)
    return {"results": results}


@app.tool()
async def get_path(start_id: str, end_id: str) -> dict:
    """Get a path between two locations by ID/coordinates."""
    return await _get_path_http(start_id, end_id)


@app.tool()
async def list_possible_locations(query: str) -> list[str]:
    """List possible location names matched by a query."""
    results = await _search_buildings_http(query)
    return [r.get("name") for r in results if isinstance(r, dict) and "name" in r]


@app.tool()
async def distance_between(start_id: str, end_id: str) -> float:
    """Compute distance in meters between two locations."""
    try:
        path = await _get_path_http(start_id, end_id)
        return float(path.get("distance", -1))
    except Exception:
        return -1


# @app.tool()
# async def time_between(start_id: str, end_id: str, speed_m_per_s: float = 1.4) -> float:
#     """Estimate travel time in seconds between two locations (default walking speed 1.4 m/s)."""
#     dist = await distance_between(start_id, end_id)
#     if dist < 0:
#         return -1
#     return dist / speed_m_per_s


# --- Run the FastMCP server ---
if __name__ == "__main__":
    app.run()

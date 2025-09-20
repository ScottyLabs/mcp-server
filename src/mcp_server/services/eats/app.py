#!/usr/bin/env python3
"""
FastMCP Server for CMU Dining Locations
Provides tools to query Carnegie Mellon University dining locations, hours, and availability.
"""

import asyncio
import httpx
from typing import List, Dict, Any
from fastmcp import FastMCP

from mcp_server.services.eats.constants import API_BASE_URL
from mcp_server.services.eats.models import DiningLocation
from mcp_server.services.eats.utils import (
    fetch_locations, parse_location_data, is_location_open_now,
    get_current_day_and_time, format_times_for_display,
    format_locations_list_markdown, format_location_markdown
)

# Initialize FastMCP server
mcp = FastMCP("CMU Dining", version="0.1.0")

@mcp.tool()
async def get_all_dining_locations() -> str:
    """
    Get all CMU dining locations with their basic information formatted as clean markdown.

    Returns a formatted list of all dining locations on campus including name, cuisine type,
    location, hours, status, and whether they accept online orders. Locations are grouped
    by cuisine type for easy browsing.
    """
    raw_locations = await fetch_locations()
    return format_locations_list_markdown(raw_locations, "All CMU Dining Locations")

@mcp.tool()
async def search_dining_locations(name_query: str) -> str:
    """
    Search for dining locations by name and return formatted results.

    Args:
        name_query: The name or partial name to search for (case-insensitive)

    Returns locations that match the search query formatted as clean markdown.
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_BASE_URL}/location/{name_query}")
            response.raise_for_status()
            data = response.json()

            raw_locations = data.get("locations", [])
            if not raw_locations:
                return f"# Search Results for '{name_query}'\n\nNo dining locations found matching '{name_query}'."

            return format_locations_list_markdown(raw_locations, f"Search Results for '{name_query}'")
        except Exception as e:
            raise Exception(f"Failed to search dining locations: {str(e)}")

@mcp.tool()
async def get_locations_open_now() -> str:
    """
    Get all dining locations that are currently open formatted as clean markdown.

    Returns a formatted list of locations that are open right now based on current day and time.
    Locations are grouped by cuisine type for easy browsing.
    """
    day, hour, minute = get_current_day_and_time()

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_BASE_URL}/locations/time/{day}/{hour}/{minute}")
            response.raise_for_status()
            data = response.json()

            raw_locations = data.get("locations", [])
            if not raw_locations:
                return "# Currently Open Locations\n\nNo dining locations are currently open."

            return format_locations_list_markdown(raw_locations, "Currently Open Locations")
        except Exception as e:
            raise Exception(f"Failed to get currently open locations: {str(e)}")

@mcp.tool()
async def get_locations_open_at_time(day: int, hour: int, minute: int = 0) -> str:
    """
    Get dining locations open at a specific day and time formatted as clean markdown.

    Args:
        day: Day of week (0=Sunday, 1=Monday, 2=Tuesday, 3=Wednesday, 4=Thursday, 5=Friday, 6=Saturday)
        hour: Hour in 24-hour format (0-23)
        minute: Minute (0-59), defaults to 0

    Returns locations that are open at the specified time formatted as clean markdown,
    grouped by cuisine type for easy browsing.
    """
    if not (0 <= day <= 6):
        raise ValueError("Day must be between 0 (Sunday) and 6 (Saturday)")
    if not (0 <= hour <= 23):
        raise ValueError("Hour must be between 0 and 23")
    if not (0 <= minute <= 59):
        raise ValueError("Minute must be between 0 and 59")

    days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    time_str = f"{hour:02d}:{minute:02d}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_BASE_URL}/locations/time/{day}/{hour}/{minute}")
            response.raise_for_status()
            data = response.json()

            raw_locations = data.get("locations", [])
            if not raw_locations:
                return f"# Locations Open on {days[day]} at {time_str}\n\nNo dining locations are open at this time."

            return format_locations_list_markdown(raw_locations, f"Locations Open on {days[day]} at {time_str}")
        except Exception as e:
            raise Exception(f"Failed to get locations open at specified time: {str(e)}")

@mcp.tool()
async def get_location_hours(location_name: str) -> str:
    """
    Get detailed information for a specific dining location formatted as clean markdown.

    Args:
        location_name: Name or partial name of the location

    Returns detailed information including hours, current status, and specials for the location.
    """
    raw_locations = await fetch_locations()

    # Find matching location
    matching_location = None
    for location in raw_locations:
        if location_name.lower() in location.get("name", "").lower():
            matching_location = location
            break

    if not matching_location:
        return f"# Location Search\n\nNo location found matching '{location_name}'. Please check the name and try again."

    is_open = is_location_open_now(matching_location.get("times", []))
    status = "open" if is_open else "closed"

    # Format the single location
    location_md = format_location_markdown(matching_location, status)

    # Add today's specials if available
    specials = matching_location.get("todaysSpecials", [])
    if specials:
        specials_text = "\n**Today's Specials:**\n"
        for special in specials:
            title = special.get("title", "")
            description = special.get("description", "")
            specials_text += f"- **{title}**: {description}\n"
        location_md += specials_text

    # Add detailed hours
    detailed_hours = format_times_for_display(matching_location.get("times", []))
    if detailed_hours:
        location_md += "\n**Detailed Hours:**\n"
        for hour_info in detailed_hours:
            location_md += f"- {hour_info}\n"

    return f"# Location Details\n\n{location_md}"

@mcp.tool()
async def get_locations_by_cuisine(cuisine_query: str) -> str:
    """
    Find dining locations by cuisine type or food description formatted as clean markdown.

    Args:
        cuisine_query: Type of cuisine or food to search for (e.g., "pizza", "asian", "coffee", "mexican")

    Returns locations that serve the specified type of cuisine formatted as clean markdown.
    """
    raw_locations = await fetch_locations()
    matching_locations = []

    cuisine_lower = cuisine_query.lower()

    for raw_location in raw_locations:
        name = raw_location.get("name", "").lower()
        short_desc = raw_location.get("shortDescription", "").lower()
        description = raw_location.get("description", "").lower()

        # Search in name, short description, and full description
        if (cuisine_lower in name or
            cuisine_lower in short_desc or
            cuisine_lower in description):
            matching_locations.append(raw_location)

    if not matching_locations:
        return f"# Cuisine Search for '{cuisine_query}'\n\nNo dining locations found serving '{cuisine_query}' cuisine."

    return format_locations_list_markdown(matching_locations, f"Locations Serving '{cuisine_query.title()}' Cuisine")

if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
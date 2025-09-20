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
from mcp_server.services.eats.utils import fetch_locations, parse_location_data, is_location_open_now, get_current_day_and_time, format_times_for_display

# Initialize FastMCP server
mcp = FastMCP("CMU Dining", version="0.1.0")

@mcp.tool()
async def get_all_dining_locations() -> List[DiningLocation]:
    """
    Get all CMU dining locations with their basic information.
    
    Returns a list of all dining locations on campus including name, description, 
    location, and whether they accept online orders.
    """
    raw_locations = await fetch_locations()
    locations = []
    
    for raw_location in raw_locations:
        location = parse_location_data(raw_location)
        # Add current open/closed status
        is_open = is_location_open_now(raw_location.get("times", []))
        location.current_status = "open" if is_open else "closed"
        locations.append(location)
    
    return locations

@mcp.tool()
async def search_dining_locations(name_query: str) -> List[DiningLocation]:
    """
    Search for dining locations by name.
    
    Args:
        name_query: The name or partial name to search for (case-insensitive)
    
    Returns locations that match the search query.
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_BASE_URL}/location/{name_query}")
            response.raise_for_status()
            data = response.json()
            
            locations = []
            for raw_location in data.get("locations", []):
                location = parse_location_data(raw_location)
                is_open = is_location_open_now(raw_location.get("times", []))
                location.current_status = "open" if is_open else "closed"
                locations.append(location)
            
            return locations
        except Exception as e:
            raise Exception(f"Failed to search dining locations: {str(e)}")

@mcp.tool()
async def get_locations_open_now() -> List[DiningLocation]:
    """
    Get all dining locations that are currently open.
    
    Returns a list of locations that are open right now based on current day and time.
    """
    day, hour, minute = get_current_day_and_time()
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_BASE_URL}/locations/time/{day}/{hour}/{minute}")
            response.raise_for_status()
            data = response.json()
            
            locations = []
            for raw_location in data.get("locations", []):
                location = parse_location_data(raw_location)
                location.current_status = "open"  # These are all open
                locations.append(location)
            
            return locations
        except Exception as e:
            raise Exception(f"Failed to get currently open locations: {str(e)}")

@mcp.tool()
async def get_locations_open_at_time(day: int, hour: int, minute: int = 0) -> List[DiningLocation]:
    """
    Get dining locations open at a specific day and time.
    
    Args:
        day: Day of week (0=Sunday, 1=Monday, 2=Tuesday, 3=Wednesday, 4=Thursday, 5=Friday, 6=Saturday)
        hour: Hour in 24-hour format (0-23)
        minute: Minute (0-59), defaults to 0
    
    Returns locations that are open at the specified time.
    """
    if not (0 <= day <= 6):
        raise ValueError("Day must be between 0 (Sunday) and 6 (Saturday)")
    if not (0 <= hour <= 23):
        raise ValueError("Hour must be between 0 and 23")
    if not (0 <= minute <= 59):
        raise ValueError("Minute must be between 0 and 59")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_BASE_URL}/locations/time/{day}/{hour}/{minute}")
            response.raise_for_status()
            data = response.json()
            
            locations = []
            for raw_location in data.get("locations", []):
                location = parse_location_data(raw_location)
                location.current_status = "open"  # These are all open at the specified time
                locations.append(location)
            
            return locations
        except Exception as e:
            raise Exception(f"Failed to get locations open at specified time: {str(e)}")

@mcp.tool()
async def get_location_hours(location_name: str) -> Dict[str, Any]:
    """
    Get detailed hours for a specific dining location.
    
    Args:
        location_name: Name or partial name of the location
    
    Returns detailed information including all operating hours for the location.
    """
    raw_locations = await fetch_locations()
    
    # Find matching location
    matching_location = None
    for location in raw_locations:
        if location_name.lower() in location.get("name", "").lower():
            matching_location = location
            break
    
    if not matching_location:
        raise ValueError(f"No location found matching '{location_name}'")
    
    location_info = parse_location_data(matching_location)
    is_open = is_location_open_now(matching_location.get("times", []))
    
    return {
        "location": location_info,
        "current_status": "open" if is_open else "closed",
        "hours": format_times_for_display(matching_location.get("times", [])),
        "today_specials": matching_location.get("todaysSpecials", [])
    }

@mcp.tool()
async def get_locations_by_cuisine(cuisine_query: str) -> List[DiningLocation]:
    """
    Find dining locations by cuisine type or food description.
    
    Args:
        cuisine_query: Type of cuisine or food to search for (e.g., "pizza", "asian", "coffee", "mexican")
    
    Returns locations that serve the specified type of cuisine.
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
            
            location = parse_location_data(raw_location)
            is_open = is_location_open_now(raw_location.get("times", []))
            location.current_status = "open" if is_open else "closed"
            matching_locations.append(location)
    
    return matching_locations

if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
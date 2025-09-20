import httpx
from typing import List, Dict, Any
from datetime import datetime

from mcp_server.services.eats.constants import API_BASE_URL
from mcp_server.services.eats.models import DiningLocation

async def fetch_locations() -> List[Dict[str, Any]]:
    """Fetch all dining locations from the API."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_BASE_URL}/locations")
            response.raise_for_status()
            data = response.json()
            return data.get("locations", [])
        except Exception as e:
            raise Exception(f"Failed to fetch dining locations: {str(e)}")

def parse_location_data(raw_location: Dict[str, Any]) -> DiningLocation:
    """Convert raw API location data to DiningLocation model."""
    return DiningLocation(
        concept_id=raw_location.get("conceptId", 0),
        name=raw_location.get("name", ""),
        short_description=raw_location.get("shortDescription", ""),
        description=raw_location.get("description", ""),
        location=raw_location.get("location", ""),
        accepts_online_orders=raw_location.get("acceptsOnlineOrders", False),
        url=raw_location.get("url"),
        menu_url=raw_location.get("menu")
    )

def get_current_day_and_time() -> tuple[int, int, int]:
    """Get current day (0=Sunday) and time (hour, minute)."""
    now = datetime.now()
    # Convert Python weekday (0=Monday) to API format (0=Sunday)
    day = (now.weekday() + 1) % 7
    return day, now.hour, now.minute

def is_location_open_now(location_times: List[Dict[str, Any]]) -> bool:
    """Check if a location is currently open based on its times."""
    day, hour, minute = get_current_day_and_time()
    current_minutes = day * 1440 + hour * 60 + minute
    
    for time_slot in location_times:
        start = time_slot.get("start", {})
        end = time_slot.get("end", {})
        
        start_minutes = (start.get("day", 0) * 1440 + 
                        start.get("hour", 0) * 60 + 
                        start.get("minute", 0))
        end_minutes = (end.get("day", 0) * 1440 + 
                      end.get("hour", 0) * 60 + 
                      end.get("minute", 0))
        
        if start_minutes <= current_minutes < end_minutes:
            return True
    
    return False

def format_times_for_display(location_times: List[Dict[str, Any]]) -> List[str]:
    """Format location times for human-readable display."""
    days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    formatted_times = []
    
    for time_slot in location_times:
        start = time_slot.get("start", {})
        end = time_slot.get("end", {})
        
        day_name = days[start.get("day", 0)]
        start_time = f"{start.get('hour', 0):02d}:{start.get('minute', 0):02d}"
        end_time = f"{end.get('hour', 0):02d}:{end.get('minute', 0):02d}"
        
        formatted_times.append(f"{day_name}: {start_time} - {end_time}")
    
    return formatted_times

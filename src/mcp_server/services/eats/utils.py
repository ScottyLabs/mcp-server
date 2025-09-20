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

def format_time_12_hour(hour: int, minute: int) -> str:
    """Convert 24-hour time to 12-hour format with AM/PM."""
    if hour == 0:
        return f"12:{minute:02d} AM"
    elif hour < 12:
        return f"{hour}:{minute:02d} AM"
    elif hour == 12:
        return f"12:{minute:02d} PM"
    else:
        return f"{hour - 12}:{minute:02d} PM"

def group_consecutive_days(location_times: List[Dict[str, Any]]) -> str:
    """Group consecutive days with same hours for compact display."""
    if not location_times:
        return "Hours not available"

    days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    day_groups = {}

    # Group times by their start-end pattern
    for time_slot in location_times:
        start = time_slot.get("start", {})
        end = time_slot.get("end", {})

        start_time = format_time_12_hour(start.get('hour', 0), start.get('minute', 0))
        end_time = format_time_12_hour(end.get('hour', 0), end.get('minute', 0))
        time_range = f"{start_time} - {end_time}"

        day_idx = start.get("day", 0)

        if time_range not in day_groups:
            day_groups[time_range] = []
        day_groups[time_range].append(day_idx)

    # Format grouped days
    formatted_groups = []
    for time_range, day_indices in day_groups.items():
        day_indices.sort()
        day_names = [days[i] for i in day_indices]

        # Group consecutive days
        if len(day_names) == 1:
            days_str = day_names[0]
        elif len(day_names) == 7:
            days_str = "Daily"
        elif day_indices == [1, 2, 3, 4, 5]:  # Monday-Friday
            days_str = "Monday - Friday"
        elif day_indices == [0, 6]:  # Weekend
            days_str = "Saturday - Sunday"
        else:
            # Handle other groupings
            consecutive_groups = []
            current_group = [day_names[0]]

            for i in range(1, len(day_names)):
                if day_indices[i] == day_indices[i-1] + 1:
                    current_group.append(day_names[i])
                else:
                    if len(current_group) > 1:
                        consecutive_groups.append(f"{current_group[0]} - {current_group[-1]}")
                    else:
                        consecutive_groups.append(current_group[0])
                    current_group = [day_names[i]]

            if len(current_group) > 1:
                consecutive_groups.append(f"{current_group[0]} - {current_group[-1]}")
            else:
                consecutive_groups.append(current_group[0])

            days_str = ", ".join(consecutive_groups)

        formatted_groups.append(f"{days_str}: {time_range}")

    return " | ".join(formatted_groups)

def extract_cuisine_type(name: str, description: str) -> str:
    """Extract cuisine type from location name and description."""
    name_lower = name.lower()
    desc_lower = description.lower()

    cuisine_keywords = {
        "coffee": ["coffee", "espresso", "latte", "cappuccino", "cafe", "prima"],
        "asian": ["asian", "chinese", "hunan", "sushi", "noodle", "rice bowl", "boba", "tea"],
        "mexican": ["mexican", "taco", "burrito", "quesadilla", "gallo", "taqueria"],
        "mediterranean": ["mediterranean", "tahini", "shawarma", "falafel", "hummus", "gyros"],
        "italian": ["italian", "pasta", "pizza", "ciao bella"],
        "indian": ["india", "curry", "tandoori"],
        "american": ["burger", "grill", "deli", "sandwich", "fries"],
        "hawaiian": ["hawaiian", "poke", "ola ola", "loco moco"],
        "dessert": ["ice cream", "dessert", "milkshake", "creamery"],
        "healthy": ["salad", "smoothie", "acai", "protein", "nourish"]
    }

    for cuisine, keywords in cuisine_keywords.items():
        if any(keyword in name_lower or keyword in desc_lower for keyword in keywords):
            return cuisine.title()

    return "Dining"

def format_location_markdown(location_data: Dict[str, Any], current_status: str = "unknown") -> str:
    """Format a single location as clean markdown."""
    name = location_data.get("name", "Unknown")
    short_desc = location_data.get("shortDescription", "")
    description = location_data.get("description", "")
    location = location_data.get("location", "Location not specified")
    accepts_online = location_data.get("acceptsOnlineOrders", False)
    times = location_data.get("times", [])

    # Extract cuisine type
    cuisine = extract_cuisine_type(name, description)

    # Format hours
    hours = group_consecutive_days(times)

    # Status indicator
    status_emoji = "🟢" if current_status == "open" else "🔴" if current_status == "closed" else "⚪"

    # Online ordering indicator
    online_emoji = "📱" if accepts_online else ""

    # Clean up description - use short description if available, otherwise truncate long description
    clean_desc = short_desc if short_desc else description
    if len(clean_desc) > 150:
        clean_desc = clean_desc[:147] + "..."

    markdown = f"""### {status_emoji} {name} {online_emoji}
**Cuisine:** {cuisine}
**Location:** {location}
**Hours:** {hours}
**Description:** {clean_desc}
"""

    return markdown

def format_locations_list_markdown(locations_data: List[Dict[str, Any]], title: str = "Dining Locations") -> str:
    """Format multiple locations as a clean markdown list grouped by cuisine."""
    if not locations_data:
        return f"# {title}\n\nNo locations found."

    # Group locations by cuisine type
    cuisine_groups = {}
    for location in locations_data:
        name = location.get("name", "Unknown")
        description = location.get("description", "")
        cuisine = extract_cuisine_type(name, description)

        if cuisine not in cuisine_groups:
            cuisine_groups[cuisine] = []
        cuisine_groups[cuisine].append(location)

    # Build markdown
    markdown_parts = [f"# {title}\n"]

    # Add summary
    total_locations = len(locations_data)
    open_locations = sum(1 for loc in locations_data if is_location_open_now(loc.get("times", [])))

    markdown_parts.append(f"**{total_locations} locations found** • **{open_locations} currently open**\n")

    # Sort cuisine groups
    sorted_cuisines = sorted(cuisine_groups.keys())

    for cuisine in sorted_cuisines:
        locations = cuisine_groups[cuisine]
        markdown_parts.append(f"## {cuisine} ({len(locations)})\n")

        for location in locations:
            # Determine current status
            is_open = is_location_open_now(location.get("times", []))
            status = "open" if is_open else "closed"

            location_md = format_location_markdown(location, status)
            markdown_parts.append(location_md)
            markdown_parts.append("")  # Add spacing

    return "\n".join(markdown_parts)

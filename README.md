# ScottyLabs MCPs

A unified Model Context Protocol (MCP) server providing access to ScottyLabs's Projects for CMU Students services through FastMCP. This server combines multiple CMU-related services into a single, composable MCP interface.

## Overview

This project provides MCP tools for:
- **CMU Dining (Eats)**: Query dining locations, hours, menus, and real-time availability
- **CMU Maps**: Search buildings, get directions, and calculate distances on campus

Built with [FastMCP](https://github.com/jlowin/fastmcp), this server uses a modular architecture that allows mounting multiple sub-services with namespace prefixes.

## Features

### CMU Dining Service (`eats`)
- Get all dining locations with details (cuisine, hours, location)
- Search locations by name
- Find locations currently open
- Check locations open at specific times
- Query locations by cuisine type
- Get detailed hours and specials for specific locations
- Real-time open/closed status
- Online ordering availability indicators

### CMU Maps Service (`maps`)
- Search buildings and locations by name
- Get paths between two locations
- Calculate distances between locations
- List possible location matches for queries

## Installation

### Prerequisites
- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) or [Poetry](https://python-poetry.org/) package manager

### Using UV (recommended)
```bash
# Install dependencies
uv sync

# Activate virtual environment
source .venv/bin/activate
```

### Using Poetry
```bash
# Install dependencies
poetry install

# Activate virtual environment
poetry shell
```

## Usage

### Running the Server

The server runs on HTTP transport by default on `0.0.0.0:8000`:

```bash
# Run as module
python -m mcp_server

# Or run directly
python src/mcp_server/__init__.py
```

### Using Individual Services

Each service can also be run independently:

```bash
# Run only the dining service
python src/mcp_server/services/eats/app.py

# Run only the maps service
python src/mcp_server/services/maps/app.py
```

### Available Tools

#### Dining Tools (prefix: `eats`)
- `get_all_dining_locations()`: List all CMU dining locations
- `search_dining_locations(name_query)`: Search by name
- `get_locations_open_now()`: Find currently open locations
- `get_locations_open_at_time(day, hour, minute)`: Check availability at specific time
- `get_location_hours(location_name)`: Get detailed info for a location
- `get_locations_by_cuisine(cuisine_query)`: Find locations by cuisine type

#### Maps Tools (prefix: `maps`)
- `search_buildings(query)`: Search for buildings/locations
- `get_path(start_id, end_id)`: Get path between two locations
- `list_possible_locations(query)`: List location name matches
- `distance_between(start_id, end_id)`: Calculate distance in meters

## Configuration

### API Endpoints
- **Dining API**: `https://dining.apis.scottylabs.org`
- **Maps API**: `https://rust.api.maps.scottylabs.org`

Endpoints are configured in:
- `src/mcp_server/services/eats/constants.py`
- `src/mcp_server/services/maps/app.py`

### Server Configuration
The main server configuration is in `src/mcp_server/__init__.py`:
- Host: `0.0.0.0`
- Port: `8000`
- Transport: `http` (streamable HTTP transport)

## Development

### Architecture

The project uses a compositional architecture:
1. **Base App** (`core/app.py`): Defines the main FastMCP instance
2. **Services** (`services/`): Individual MCP services with their own tools
3. **Main Composition** (`main.py`): Mounts services with prefixes to avoid conflicts

This allows:
- Independent development and testing of services
- Namespace isolation via prefixes
- Easy addition of new services
- Running services independently or combined

### Adding a New Service

1. Create a new directory under `src/mcp_server/services/`
2. Implement your service with FastMCP tools
3. Mount it in `src/mcp_server/main.py`:

```python
from mcp_server.services.your_service.app import mcp as your_mcp

main_mcp.mount(your_mcp, prefix="your_service")
```

### Dependencies

Core dependencies:
- `fastmcp>=2.12.3`: MCP framework
- `aiohttp>=3.12.15`: Async HTTP client
- `httpx`: HTTP client for async requests
- `pydantic`: Data validation and models

## Data Models

### DiningLocation
- `concept_id`: Unique identifier
- `name`: Location name
- `short_description`: Brief description
- `description`: Full description
- `location`: Physical location on campus
- `accepts_online_orders`: Online ordering availability
- `url`: Location website
- `menu_url`: Menu link
- `current_status`: Open/closed status

### TimeSlot
- `day`: Day of week (0=Sunday, 6=Saturday)
- `start_hour`: Opening hour (24-hour format)
- `start_minute`: Opening minute
- `end_hour`: Closing hour
- `end_minute`: Closing minute

## Output Format

All dining tools return formatted Markdown with:
- Status indicators (=� open, =4 closed)
- Online ordering indicators (=�)
- Grouped by cuisine type
- 12-hour time format
- Consecutive day grouping for hours

## Author
AI Team at ScottyLabs

## Version

Current version: `0.1.0`
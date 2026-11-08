#!/usr/bin/env python3
"""
Main MCP Server - Composed FastMCP Server
Combines the CMU Dining, Maps, Courses, Guide, and Bus services into a single runnable MCP server.
"""

import os
from http import HTTPStatus

from starlette.responses import JSONResponse

from mcp_server.core.app import main_mcp
from mcp_server.services.bus.app import mcp as bus_mcp
from mcp_server.services.courses.app import app as courses_mcp
from mcp_server.services.eats.app import mcp as eats_mcp
from mcp_server.services.guide.app import app as guide_mcp
from mcp_server.services.maps.app import app as maps_mcp


@main_mcp.custom_route("/api/health", methods=["GET"])
async def health(request) -> JSONResponse:
    return JSONResponse(content={"status": "ok"}, status_code=HTTPStatus.OK)


def main():
    # Mount the subservers with prefixes to avoid naming conflicts
    main_mcp.mount(eats_mcp, namespace="eats")
    main_mcp.mount(maps_mcp, namespace="maps")
    main_mcp.mount(courses_mcp, namespace="courses")
    main_mcp.mount(guide_mcp, namespace="guide")
    main_mcp.mount(bus_mcp, namespace="bus")

    # Run the composed MCP server
    # main_mcp.run() - attempt deployment
    port = int(os.environ.get("PORT", "5050"))
    main_mcp.run(transport="http", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()

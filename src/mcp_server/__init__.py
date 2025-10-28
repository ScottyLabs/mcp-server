#!/usr/bin/env python3
"""
Main MCP Server - Composed FastMCP Server
Combines CMU Dining and Maps services into a single runnable MCP server.
"""
from mcp_server.core.app import main_mcp
from mcp_server.services.eats.app import mcp as eats_mcp
from mcp_server.services.maps.app import app as maps_mcp

def main():
    # Mount the subservers with prefixes to avoid naming conflicts
    main_mcp.mount(eats_mcp, prefix="eats")
    main_mcp.mount(maps_mcp, prefix="maps")

    # Run the composed MCP server
    main_mcp.run(transport="http", host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()

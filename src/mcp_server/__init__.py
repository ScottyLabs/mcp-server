from mcp_server.main import main_mcp

if __name__ == "__main__":
    main_mcp.run(transport="http", host="0.0.0.0", port=8000)
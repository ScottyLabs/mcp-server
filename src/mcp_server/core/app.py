from fastmcp import FastMCP
from fastmcp.client.transports import StreamableHttpTransport
from starlette.middleware.cors import CORSMiddleware

main_mcp = FastMCP(name="Scotty Labs MCPs for CMU", version="0.1.0")

# Add CORS middleware to support OPTIONS requests and cross-origin access
main_mcp.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins - adjust for production as needed
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods including OPTIONS
    allow_headers=["*"],  # Allow all headers
)
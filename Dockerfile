# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies using uv
RUN uv sync --frozen --no-cache

# Copy source code
COPY src/ ./src/
COPY README.md ./

# Expose port 8000 (the default port the MCP server runs on)
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Run the MCP server using uv
CMD ["uv", "run", "python", "-m", "mcp_server"]

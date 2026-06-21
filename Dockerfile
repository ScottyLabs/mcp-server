# Use an official slim Python base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency files
COPY pyproject.toml uv.lock README.md ./

# Copy source code
COPY src ./src

# Install dependencies using uv
RUN uv sync --frozen --no-dev

# Set PYTHONPATH (optional, for clarity)
ENV PYTHONPATH=/app/src

EXPOSE 8000

# Run your MCP server using uv
CMD ["uv", "run", "src/mcp_server/__init__.py"]
